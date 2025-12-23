import asyncio
import heapq
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set

import structlog

from easyths.core.base_operation import operation_registry
from easyths.models.operations import Operation, OperationStatus, OperationResult
from easyths.utils import project_config_instance
logger = structlog.get_logger(__name__)


class DependencyError(Exception):
    """依赖错误"""
    pass


class OperationQueue:
    """操作队列

    负责管理操作的队列、依赖关系和执行顺序
    """

    def __init__(self, automator=None):
        self.automator = automator
        self.max_size = project_config_instance.queue_max_size
        self.priority_levels = project_config_instance.queue_priority_levels

        # 队列和状态管理
        self._queue: List[tuple] = []  # 优先级队列 (priority, timestamp, operation)
        self._operations: Dict[str, Operation] = {}  # 所有操作
        self._running_operations: Dict[str, Operation] = {}  # 正在运行的操作
        self._completed_operations: Dict[str, Operation] = {}  # 已完成的操作
        self._dependencies: Dict[str, Set[str]] = defaultdict(set)  # 操作依赖关系
        self._dependents: Dict[str, Set[str]] = defaultdict(set)  # 被依赖关系

        # 控制标志
        self._processing = False
        self._stopped = False
        self._queue_lock = asyncio.Lock()
        self._executor_lock = asyncio.Lock()

        self.logger = structlog.get_logger(__name__)
        self._stats = {
            'total_processed': 0,
            'total_failed': 0,
            'total_success': 0,
            'queue_size': 0
        }

    async def put(self, operation: Operation) -> bool:
        """添加操作到队列

        Args:
            operation: 操作对象

        Returns:
            bool: 是否成功添加
        """
        async with self._queue_lock:
            if len(self._queue) >= self.max_size:
                self.logger.error("队列已满，无法添加操作", operation_id=operation.id)
                return False

            # 检查操作是否已存在
            if operation.id in self._operations:
                self.logger.warning("操作已存在", operation_id=operation.id)
                return False

            # 验证依赖关系
            if not await self._validate_dependencies(operation):
                self.logger.error("操作依赖验证失败", operation_id=operation.id)
                return False

            # 添加到队列
            priority_value = self._calculate_priority(operation)
            heapq.heappush(self._queue, (priority_value, datetime.now(), operation.id))

            # 更新状态
            self._operations[operation.id] = operation
            operation.update_status(OperationStatus.QUEUED)

            # 更新依赖关系
            self._update_dependencies(operation)

            self._stats['queue_size'] = len(self._queue)
            self.logger.info(
                "操作已添加到队列",
                operation_id=operation.id,
                operation_name=operation.name,
                priority=operation.priority,
                queue_size=self._stats['queue_size']
            )

            return True

    async def get(self) -> Optional[Operation]:
        """从队列获取操作

        Returns:
            Optional[Operation]: 可执行的操作
        """
        async with self._queue_lock:
            while self._queue and not self._stopped:
                priority, timestamp, operation_id = heapq.heappop(self._queue)
                operation = self._operations.get(operation_id)

                if not operation:
                    continue

                # 检查依赖是否完成
                if not self._check_dependencies_completed(operation):
                    # 依赖未完成，放回队列
                    heapq.heappush(self._queue, (priority, datetime.now(), operation_id))
                    continue

                # 检查状态
                if operation.status == OperationStatus.QUEUED:
                    operation.update_status(OperationStatus.RUNNING)
                    self._running_operations[operation_id] = operation
                    self._stats['queue_size'] = len(self._queue)
                    return operation

            return None

    async def execute(self, operation: Operation) -> OperationResult:
        """执行操作

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

        try:
            # 获取操作实例
            operation_instance = await operation_registry.get_operation_instance(
                operation.name, self.automator, self.config
            )

            if not operation_instance:
                raise ValueError(f"未找到操作: {operation.name}")

            # 执行操作
            result = await operation_instance.run(operation.params)

            # 更新操作状态
            if result.success:
                operation.update_status(OperationStatus.COMPLETED)
                self._stats['total_success'] += 1
            else:
                operation.update_status(OperationStatus.FAILED, result.error)
                self._stats['total_failed'] += 1

            operation.result = result

            # 从运行中列表移除
            self._running_operations.pop(operation.id, None)
            self._completed_operations[operation.id] = operation
            self._stats['total_processed'] += 1

            self.logger.info(
                "操作执行完成",
                operation_id=operation.id,
                success=result.success,
                error=result.error
            )

            return result

        except Exception as e:
            error_msg = f"执行操作异常: {str(e)}"
            self.logger.exception(error_msg, operation_id=operation.id)

            operation.update_status(OperationStatus.FAILED, error_msg)
            operation.result = OperationResult(success=False, error=error_msg)

            # 从运行中列表移除
            self._running_operations.pop(operation.id, None)
            self._completed_operations[operation.id] = operation
            self._stats['total_failed'] += 1
            self._stats['total_processed'] += 1

            return operation.result

    async def process_queue(self):
        """处理队列中的操作"""
        self._processing = True
        self.logger.info("开始处理操作队列")

        while not self._stopped:
            try:
                # 获取可执行的操作
                operation = await self.get()
                if not operation:
                    await asyncio.sleep(0.1)
                    continue

                # 执行操作
                await self.execute(operation)

            except Exception as e:
                self.logger.exception("处理队列时发生异常", error=str(e))
                await asyncio.sleep(1)

        self._processing = False
        self.logger.info("停止处理操作队列")

    async def _validate_dependencies(self, operation: Operation) -> bool:
        """验证操作依赖

        Args:
            operation: 操作对象

        Returns:
            bool: 依赖是否有效
        """
        for dep_id in operation.dependencies:
            if dep_id not in self._operations:
                self.logger.error(
                    "依赖的操作不存在",
                    operation_id=operation.id,
                    dependency_id=dep_id
                )
                return False

            # 检查循环依赖
            if await self._check_circular_dependency(operation.id, dep_id):
                self.logger.error(
                    "检测到循环依赖",
                    operation_id=operation.id,
                    dependency_id=dep_id
                )
                return False

        return True

    async def _check_circular_dependency(self, op_id: str, dep_id: str) -> bool:
        """检查循环依赖

        Args:
            op_id: 操作ID
            dep_id: 依赖的操作ID

        Returns:
            bool: 是否存在循环依赖
        """
        visited = set()

        def dfs(current_id: str) -> bool:
            if current_id == op_id:
                return True
            if current_id in visited:
                return False

            visited.add(current_id)

            for next_dep in self._dependencies[current_id]:
                if dfs(next_dep):
                    return True

            return False

        return dfs(dep_id)

    def _update_dependencies(self, operation: Operation):
        """更新依赖关系

        Args:
            operation: 操作对象
        """
        for dep_id in operation.dependencies:
            self._dependencies[operation.id].add(dep_id)
            self._dependents[dep_id].add(operation.id)

    def _check_dependencies_completed(self, operation: Operation) -> bool:
        """检查依赖是否完成

        Args:
            operation: 操作对象

        Returns:
            bool: 所有依赖是否已完成
        """
        for dep_id in operation.dependencies:
            dep_op = self._operations.get(dep_id)
            if not dep_op or dep_op.status != OperationStatus.COMPLETED:
                return False
        return True

    def _calculate_priority(self, operation: Operation) -> int:
        """计算优先级值（越小优先级越高）

        Args:
            operation: 操作对象

        Returns:
            int: 优先级值
        """
        # 基础优先级（反向，因为heapq是最小堆）
        base_priority = (self.priority_levels - operation.priority) * 1000

        # 根据依赖数量调整
        dep_penalty = len(operation.dependencies) * 100

        return base_priority + dep_penalty

    async def cancel_operation(self, operation_id: str) -> bool:
        """取消操作

        Args:
            operation_id: 操作ID

        Returns:
            bool: 是否成功取消
        """
        async with self._queue_lock:
            operation = self._operations.get(operation_id)
            if not operation:
                return False

            # 只能取消未开始的操作
            if operation.status in [OperationStatus.PENDING, OperationStatus.QUEUED]:
                operation.update_status(OperationStatus.CANCELLED)

                # 从队列移除
                self._queue = [item for item in self._queue if item[2] != operation_id]
                heapq.heapify(self._queue)

                self.logger.info("操作已取消", operation_id=operation_id)
                return True

            return False

    async def retry_operation(self, operation_id: str) -> bool:
        """重试失败的操作

        Args:
            operation_id: 操作ID

        Returns:
            bool: 是否成功重试
        """
        operation = self._completed_operations.get(operation_id)
        if not operation:
            return False

        if not operation.can_retry():
            return False

        # 重置操作状态
        operation.increment_retry()
        operation.update_status(OperationStatus.PENDING)
        operation.error = None
        operation.result = None

        # 移回待处理队列
        self._operations[operation_id] = operation
        self._completed_operations.pop(operation_id, None)

        # 添加到队列
        await self.put(operation)

        self.logger.info(
            "操作已重新入队",
            operation_id=operation_id,
            retry_count=operation.retry_count
        )

        return True

    def get_operation_status(self, operation_id: str) -> Optional[OperationStatus]:
        """获取操作状态

        Args:
            operation_id: 操作ID

        Returns:
            Optional[OperationStatus]: 操作状态
        """
        operation = self._operations.get(operation_id)
        return operation.status if operation else None

    def get_operation(self, operation_id: str) -> Optional[Operation]:
        """获取操作

        Args:
            operation_id: 操作ID

        Returns:
            Optional[Operation]: 操作对象
        """
        return self._operations.get(operation_id)

    def get_queue_stats(self) -> Dict[str, any]:
        """获取队列统计信息

        Returns:
            Dict[str, any]: 统计信息
        """
        return {
            **self._stats,
            'processing': self._processing,
            'stopped': self._stopped,
            'running_count': len(self._running_operations),
            'completed_count': len(self._completed_operations)
        }

    async def stop(self):
        """停止队列处理"""
        self.logger.info("正在停止操作队列...")
        self._stopped = True

        # 等待当前操作完成
        while self._processing and self._running_operations:
            await asyncio.sleep(0.1)

        self.logger.info("操作队列已停止")

    async def clear(self):
        """清空队列"""
        async with self._queue_lock:
            self._queue.clear()
            self._stats['queue_size'] = 0
            self.logger.info("操作队列已清空")
