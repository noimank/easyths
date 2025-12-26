"""操作队列 - 后台线程串行执行所有操作

Author: noimank
Email: noimank@163.com
"""

import queue
import threading
import time
import uuid
from typing import Dict, Optional

import structlog

from easyths.core.base_operation import operation_registry
from easyths.models.operations import Operation, OperationStatus, OperationResult
from easyths.utils import project_config_instance

logger = structlog.get_logger(__name__)


class OperationQueue:
    """操作队列 - 后台线程串行执行所有操作

    设计原则：
        - 单一后台线程：所有操作按顺序串行执行
        - 同步接口：API提交任务后立即返回（异步体验）
        - 优先级队列：高优先级操作优先执行
        - 状态查询：通过操作ID查询执行状态和结果
    """

    def __init__(self, automator=None):
        """初始化操作队列

        Args:
            automator: 自动化器实例
        """
        self.automator = automator
        self.max_size = project_config_instance.queue_max_size

        # 优先级队列：存储 (-priority, timestamp, operation) 元组
        # -priority 实现降序（高优先级先执行）
        # timestamp 保证相同优先级按时间顺序执行（FIFO）
        self._queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=self.max_size)
        self._operations: Dict[str, Operation] = {}  # 所有操作
        self._running_operations: Dict[str, Operation] = {}  # 正在运行的操作
        self._completed_operations: Dict[str, Operation] = {}  # 已完成的操作
        self._queue_counter = 0  # 用于保证相同优先级的顺序

        # 控制标志
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()  # 用于保护 queue_counter
        self._stats = {
            'total_processed': 0,
            'total_failed': 0,
            'total_success': 0,
            'queue_size': 0
        }

        self.logger = structlog.get_logger(__name__)

    def start(self) -> None:
        """启动队列处理线程"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._process_loop, name="OperationQueue", daemon=False)
        self._thread.start()
        self.logger.info("操作队列已启动")

    def _process_loop(self) -> None:
        """队列处理主循环 - 在后台线程运行"""
        self.logger.info("开始处理操作队列")

        while self._running:
            try:
                # 从优先级队列获取操作（超时0.1秒以便检查running状态）
                try:
                    priority_item = self._queue.get(timeout=0.1)
                    # priority_item 是 (-priority, counter, operation) 元组
                    operation = priority_item[2]
                except queue.Empty:
                    continue

                # 检查操作是否已取消（失败且error为"操作已取消"）
                if operation.status == OperationStatus.FAILED and operation.error == "操作已取消":
                    self._completed_operations[operation.id] = operation
                    self._stats['total_processed'] += 1
                    continue

                # 更新状态为运行中
                operation.update_status(OperationStatus.RUNNING)
                self._running_operations[operation.id] = operation
                self._stats['queue_size'] = self._queue.qsize()

                # 执行操作（同步调用）
                try:
                    result = self._execute_sync(operation)

                    # 更新操作状态
                    if result.success:
                        operation.update_status(OperationStatus.COMPLETED)
                        self._stats['total_success'] += 1
                    else:
                        operation.update_status(OperationStatus.FAILED, result.error)
                        self._stats['total_failed'] += 1

                    operation.result = result

                except Exception as e:
                    error_msg = f"执行操作异常: {str(e)}"
                    self.logger.exception(error_msg, operation_id=operation.id)
                    operation.update_status(OperationStatus.FAILED, error_msg)
                    operation.result = OperationResult(success=False, error=error_msg)
                    self._stats['total_failed'] += 1

                finally:
                    # 从运行中列表移到已完成列表
                    self._running_operations.pop(operation.id, None)
                    self._completed_operations[operation.id] = operation
                    self._stats['total_processed'] += 1

            except Exception as e:
                self.logger.exception("处理队列时发生异常", error=str(e))
                time.sleep(1)

        self._running = False
        self.logger.info("停止处理操作队列")

    def _execute_sync(self, operation: Operation) -> OperationResult:
        """同步执行操作

        Args:
            operation: 要执行的操作

        Returns:
            OperationResult: 执行结果
        """
        self.logger.info(
            "开始执行操作",
            operation_id=operation.id,
            operation_name=operation.name,
            params=operation.params
        )

        # 获取操作实例
        operation_instance = operation_registry.get_operation_instance(
            operation.name, self.automator
        )

        if not operation_instance:
            raise ValueError(f"未找到操作: {operation.name}")

        # 同步执行
        return operation_instance.run(operation.params)

    def submit(self, operation: Operation) -> str:
        """提交操作到队列

        Args:
            operation: 操作对象

        Returns:
            str: 操作ID

        Raises:
            ValueError: 队列已满或操作已存在
        """
        # 检查队列是否已满
        if self._queue.qsize() >= self.max_size:
            raise ValueError("队列已满，无法添加操作")

        # 生成操作ID
        if not operation.id:
            operation.id = str(uuid.uuid4())

        # 检查操作是否已存在
        if operation.id in self._operations:
            raise ValueError(f"操作已存在: {operation.id}")

        # 获取递增计数器（保证相同优先级的顺序）
        with self._lock:
            counter = self._queue_counter
            self._queue_counter += 1

        # 添加到优先级队列（使用 -priority 实现降序）
        priority_item = (-operation.priority, counter, operation)
        try:
            self._queue.put(priority_item, block=False)
        except queue.Full:
            raise ValueError("队列已满，无法添加操作")

        # 更新状态
        self._operations[operation.id] = operation
        operation.update_status(OperationStatus.QUEUED)

        self._stats['queue_size'] = self._queue.qsize()
        self.logger.info(
            "操作已添加到队列",
            operation_id=operation.id,
            operation_name=operation.name,
            priority=operation.priority,
            queue_size=self._stats['queue_size']
        )

        return operation.id

    def get_result(self, operation_id: str, timeout: Optional[float] = None) -> Optional[OperationResult]:
        """获取操作结果（阻塞等待）

        Args:
            operation_id: 操作ID
            timeout: 超时时间（秒），None表示无限等待

        Returns:
            OperationResult: 操作结果，如果超时返回None
        """
        start_time = time.perf_counter()

        while True:
            # 检查是否已完成
            operation = self._completed_operations.get(operation_id)
            if operation and operation.status in [OperationStatus.COMPLETED, OperationStatus.FAILED]:
                return operation.result

            # 检查超时
            if timeout is not None:
                elapsed = time.perf_counter() - start_time
                if elapsed >= timeout:
                    return None

            time.sleep(0.1)

    def get_status(self, operation_id: str) -> Optional[OperationStatus]:
        """获取操作状态

        Args:
            operation_id: 操作ID

        Returns:
            OperationStatus: 操作状态
        """
        operation = self._operations.get(operation_id)
        return operation.status if operation else None

    def get_operation(self, operation_id: str) -> Optional[Operation]:
        """获取操作

        Args:
            operation_id: 操作ID

        Returns:
            Operation: 操作对象
        """
        return self._operations.get(operation_id)

    def get_queue_stats(self) -> Dict[str, any]:
        """获取队列统计信息

        Returns:
            Dict[str, any]: 统计信息
        """
        return {
            **self._stats,
            'processing': self._running,
            'running_count': len(self._running_operations),
            'completed_count': len(self._completed_operations),
            'queued_count': self._queue.qsize()
        }

    def cancel_operation(self, operation_id: str) -> bool:
        """取消操作（仅支持取消已入队但未执行的操作）

        注意：由于使用优先级队列，已入队的操作无法从队列中移除。
        当操作被标记为取消后，执行时会跳过。

        Args:
            operation_id: 操作ID

        Returns:
            bool: 是否成功标记取消
        """
        operation = self._operations.get(operation_id)
        if not operation:
            return False

        # 只能标记未执行的操作为取消状态
        if operation.status == OperationStatus.QUEUED:
            operation.update_status(OperationStatus.FAILED, "操作已取消")
            self.logger.info("操作已标记为取消", operation_id=operation_id)
            return True

        return False

    def stop(self) -> None:
        """停止队列处理"""
        if not self._running:
            return

        self.logger.info("正在停止操作队列...")
        self._running = False

        # 等待当前操作完成
        while self._thread and self._thread.is_alive() and self._running_operations:
            time.sleep(0.1)

        # 等待线程结束
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self.logger.info("操作队列已停止")

    def clear(self) -> None:
        """清空队列"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._stats['queue_size'] = 0
        self.logger.info("操作队列已清空")
