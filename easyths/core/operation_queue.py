"""操作队列 - 后台线程串行执行所有操作

Author: noimank
Email: noimank@163.com
"""

import queue
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import structlog

from easyths.core.account_state import account_state
from easyths.core.base_operation import operation_registry
from easyths.models.operations import (
    TERMINAL_STATUSES,
    ErrorCode,
    Operation,
    OperationResult,
    OperationStatus,
)
from easyths.utils import project_config_instance

logger = structlog.get_logger(__name__)

# 已完成操作结果的保留时长（硬编码 3 小时），超时后从内存淘汰，
# 避免 _operations/_completed_operations 无限增长
RESULT_TTL = timedelta(hours=3)
# 两次淘汰扫描之间的最小间隔
_SWEEP_INTERVAL = timedelta(minutes=5)


class _OperationExecutor:
    """常驻操作执行线程。

    所有操作固定在同一执行线程上串行运行（经内部队列派发）。线程内
    惰性初始化的线程绑定资源（mss 的 GDI 设备上下文等）因此在整个
    线程生命周期内复用——与改造前所有操作共用单一消费线程的语义
    一致。看门狗超时后整个线程被抛弃换新，惰性状态由新线程首次
    使用时自行重建。
    """

    def __init__(self) -> None:
        self._jobs: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self._thread = threading.Thread(
            target=self._loop, name="op-executor", daemon=True
        )
        self._thread.start()

    def _loop(self) -> None:
        while (job := self._jobs.get()) is not None:
            job()

    def submit(self, job: Callable[[], None]) -> None:
        """派发一个任务到执行线程"""
        self._jobs.put(job)

    def retire(self) -> None:
        """通知线程处理完当前任务后退出（已卡死时仅在其恢复后生效）"""
        self._jobs.put(None)

    def is_alive(self) -> bool:
        return self._thread.is_alive()


class OperationQueue:
    """操作队列 - 后台线程串行执行所有操作

    设计原则：
        - 单一后台线程：所有操作按顺序串行执行
        - 优先级队列：高优先级操作优先执行
        - 状态迁移原子化：QUEUED→RUNNING 仅由消费线程在锁内认领，
          取消/停机/清空只能在锁内把 QUEUED 直接迁到终态；认领失败
          的操作一律跳过不执行，杜绝「已取消/已停机收尾却仍执行」
        - 执行看门狗：单操作硬超时（默认 10 秒），界面卡死时操作以
          TIMEOUT 收尾并断开 automator，后续操作快速失败，队列不陪葬
        - 事件通知：每个操作挂一个 threading.Event，完成即置位，
          get_result 无忙轮询等待
        - 状态查询：get_state 非阻塞快照；get_result 阻塞等待终态
    """

    def __init__(self, automator=None):
        """初始化操作队列

        Args:
            automator: 自动化器实例
        """
        self.automator = automator
        self.max_size = project_config_instance.queue_max_size
        # 单操作执行硬超时（秒），界面卡死时以此保护队列
        self.operation_timeout = project_config_instance.queue_operation_timeout

        # 优先级队列：存储 (-priority, counter, operation) 元组
        # -priority 实现降序（高优先级先执行）
        # counter 保证相同优先级按时间顺序执行（FIFO）
        self._queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=self.max_size)
        self._operations: dict[str, Operation] = {}  # 所有操作
        self._running_operations: dict[str, Operation] = {}  # 正在运行的操作
        self._completed_operations: dict[str, Operation] = {}  # 已完成的操作
        self._events: dict[str, threading.Event] = {}  # 完成通知
        self._queue_counter = 0  # 用于保证相同优先级的顺序
        self._last_sweep = datetime.now()  # 上次过期淘汰扫描时间

        # 控制标志
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()  # 保护 queue_counter 与 events 的注册
        self._executor: _OperationExecutor | None = None  # 常驻执行线程
        self._stats = {
            "total_processed": 0,
            "total_failed": 0,
            "total_success": 0,
            "total_timeouts": 0,
            "queue_size": 0,
        }

        self.logger = structlog.get_logger(__name__)

    # ============ 生命周期 ============

    def start(self) -> None:
        """启动队列处理线程"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._process_loop, name="OperationQueue", daemon=False
        )
        self._thread.start()
        self.logger.info("操作队列已启动")

    def stop(self) -> None:
        """停止队列处理，未执行的排队操作以失败终态收尾并唤醒所有等待方"""
        self._running = False

        if self._thread is not None:
            self.logger.info("正在停止操作队列...")
            # 等待当前操作完成（执行看门狗保证有界，最长约 operation_timeout）
            while self._thread.is_alive() and self._running_operations:
                time.sleep(0.1)
            if self._thread.is_alive():
                self._thread.join(timeout=5)

        # 排队中未执行的操作统一失败收尾，释放等待方。
        # 在锁内置为终态后，消费线程即使随后从队列取到也无法认领执行
        with self._lock:
            for op in list(self._operations.values()):
                if op.status is OperationStatus.QUEUED:
                    self._settle(
                        op,
                        OperationResult(
                            status=OperationStatus.FAILED,
                            success=False,
                            message="服务关闭，操作未执行",
                            error_code=ErrorCode.INTERNAL,
                        ),
                    )

        # 退役执行线程（若已卡死则在其恢复后自行退出）
        if self._executor is not None:
            self._executor.retire()
            self._executor = None

        self.logger.info("操作队列已停止")

    def clear(self) -> None:
        """清空队列，排队中的操作以取消终态收尾"""
        while not self._queue.empty():
            try:
                op = self._queue.get_nowait()[2]
            except queue.Empty:
                break
            with self._lock:
                if op.status is OperationStatus.QUEUED:
                    self._settle(
                        op,
                        OperationResult(
                            status=OperationStatus.CANCELLED,
                            success=False,
                            message="队列已清空，操作未执行",
                            error_code=ErrorCode.CANCELLED,
                        ),
                    )
        self._stats["queue_size"] = 0
        self.logger.info("操作队列已清空")

    # ============ 消费循环 ============

    def _process_loop(self) -> None:
        """队列处理主循环 - 在后台线程运行"""
        self.logger.info("开始处理操作队列")

        while self._running:
            try:
                try:
                    operation = self._queue.get(timeout=0.1)[2]
                except queue.Empty:
                    self._sweep_expired()
                    continue

                # 认领失败：操作已被取消/停机/清空置为终态，跳过不执行
                if not self._claim(operation):
                    self._stats["total_processed"] += 1
                    continue

                self._running_operations[operation.id] = operation
                self._stats["queue_size"] = self._queue.qsize()

                try:
                    result = self._execute_with_watchdog(operation)
                    if result.success:
                        operation.update_status(OperationStatus.COMPLETED)
                        self._stats["total_success"] += 1
                    else:
                        operation.update_status(OperationStatus.FAILED)
                        self._stats["total_failed"] += 1
                    self._settle(operation, result)

                except Exception as e:
                    error_msg = f"执行操作异常: {e}"
                    self.logger.exception(error_msg, operation_id=operation.id)
                    operation.update_status(OperationStatus.FAILED)
                    self._settle(
                        operation,
                        OperationResult(
                            status=OperationStatus.FAILED,
                            success=False,
                            message=error_msg,
                            error_code=ErrorCode.INTERNAL,
                        ),
                    )
                    self._stats["total_failed"] += 1

                finally:
                    self._running_operations.pop(operation.id, None)
                    self._stats["total_processed"] += 1
                    self._sweep_expired()

            except Exception as e:
                self.logger.exception("处理队列时发生异常", error=str(e))
                time.sleep(1)

        self._running = False
        self.logger.info("停止处理操作队列")

    def _claim(self, operation: Operation) -> bool:
        """QUEUED→RUNNING 原子认领（仅消费线程调用）。

        取消/停机/清空已在锁内把 QUEUED 迁到终态时认领必然失败，
        保证已取消或已停机收尾的操作绝不会再执行。
        """
        with self._lock:
            if operation.status is not OperationStatus.QUEUED:
                return False
            operation.update_status(OperationStatus.RUNNING)
            return True

    def _execute_with_watchdog(self, operation: Operation) -> OperationResult:
        """提交到常驻执行线程并限时等待完成。

        执行线程与消费线程分离：消费线程只在 Event 上限时等待，永远
        不会卡在操作内部。超时后执行线程无法强杀、可能仍在操作 UI：
        退役该线程并断开 automator，使后续操作在 pre_execute 快速失败，
        避免与残留线程同时驱动界面；下一个操作自动在新执行线程上运行。
        """
        if self._executor is None or not self._executor.is_alive():
            self._executor = _OperationExecutor()
        executor = self._executor

        outcome: dict[str, Any] = {}
        done = threading.Event()

        def _run() -> None:
            try:
                outcome["result"] = self._execute_sync(operation)
            except Exception as e:  # 线程内异常带回消费线程统一收尾
                outcome["error"] = e
            finally:
                done.set()

        executor.submit(_run)

        if not done.wait(timeout=self.operation_timeout):
            self._stats["total_timeouts"] += 1
            executor.retire()
            self._executor = None
            if self.automator is not None:
                self.automator.disconnect()
            self.logger.error(
                "操作执行超时，已断开同花顺连接",
                operation_id=operation.id,
                operation_name=operation.name,
                timeout=self.operation_timeout,
            )
            return OperationResult(
                status=OperationStatus.FAILED,
                success=False,
                message=(
                    f"操作执行超时（>{self.operation_timeout:.0f}秒），疑似界面卡死，"
                    "已断开同花顺连接，请恢复客户端后调用重连接口"
                ),
                error_code=ErrorCode.TIMEOUT,
                # 操作已实际执行，附带执行时当前使用账户（排队期取消/停机收尾不带）
                current_used_account=account_state.current_used_account,
            )

        if "error" in outcome:
            raise outcome["error"]
        return outcome["result"]

    def _execute_sync(self, operation: Operation) -> OperationResult:
        """同步执行操作"""
        self.logger.info(
            "开始执行操作",
            operation_id=operation.id,
            operation_name=operation.name,
            params=operation.params,
        )

        # 执行前账户指令：在同一执行线程内先切换，与目标操作同槽原子执行，
        # 其他操作不会插入其间；account_switch 幂等，已处于目标账户时无害
        if operation.account_name is not None and (
            switch_failure := self._switch_account_before(operation.account_name)
        ):
            return switch_failure

        operation_instance = operation_registry.get_operation_instance(
            operation.name, self.automator
        )
        if not operation_instance:
            raise ValueError(f"未找到操作: {operation.name}")

        result = operation_instance.run(operation.params)

        # 界面异常且同花顺进程已退出时主动断连，
        # 让后续操作快速失败而不是逐个超时
        if (
            result.error_code == ErrorCode.UI_ERROR
            and self.automator is not None
            and not self.automator.is_process_alive()
        ):
            self.automator.disconnect()
            self.logger.warning("检测到同花顺进程已退出，已断开连接")

        return result

    def _switch_account_before(self, account_name: str) -> OperationResult | None:
        """执行前切换账户，就绪返回 None，失败返回终态结果（目标操作不再执行）"""
        switch_instance = operation_registry.get_operation_instance(
            "account_switch", self.automator
        )
        if switch_instance is None:
            return OperationResult(
                status=OperationStatus.FAILED,
                success=False,
                message="未找到操作: account_switch",
                error_code=ErrorCode.INTERNAL,
            )

        result = switch_instance.run({"account_name": account_name})
        if result.success:
            return None

        self.logger.warning(
            "执行前账户切换失败",
            account_name=account_name,
            error_code=result.error_code,
            message=result.message,
        )
        return OperationResult(
            status=OperationStatus.FAILED,
            success=False,
            message=f"执行前账户切换失败: {result.message}",
            error_code=result.error_code,
            current_used_account=result.current_used_account,
        )

    def _settle(self, operation: Operation, result: OperationResult) -> None:
        """写入终态结果、转入完成列表并唤醒等待方。

        调用方保证对该操作的独占：消费线程对已认领（RUNNING）的操作
        独占；取消/停机/清空在 _lock 内对 QUEUED 的操作独占。
        """
        operation.result = result
        if operation.status not in TERMINAL_STATUSES:
            operation.update_status(
                OperationStatus.CANCELLED
                if result.error_code == ErrorCode.CANCELLED
                else OperationStatus.FAILED
            )
        self._completed_operations[operation.id] = operation
        event = self._events.get(operation.id)
        if event is not None:
            event.set()

    def _sweep_expired(self) -> None:
        """淘汰超过 TTL 的已完成操作记录，防止内存无限增长"""
        now = datetime.now()
        if now - self._last_sweep < _SWEEP_INTERVAL:
            return
        self._last_sweep = now
        deadline = now - RESULT_TTL
        expired = [
            op_id
            for op_id, op in list(self._completed_operations.items())
            if (op.completed_at or op.created_at) < deadline
        ]
        for op_id in expired:
            self._completed_operations.pop(op_id, None)
            self._operations.pop(op_id, None)
            self._events.pop(op_id, None)
        if expired:
            self.logger.info("已淘汰过期操作记录", evicted=len(expired))

    # ============ 对外接口 ============

    def submit(self, operation: Operation) -> str:
        """提交操作到队列（注册、置 QUEUED、入队均在锁内完成）。

        Raises:
            ValueError: 队列已满或操作已存在
        """
        if not operation.id:
            operation.id = str(uuid.uuid4())

        with self._lock:
            if self._queue.qsize() >= self.max_size:
                raise ValueError("队列已满，无法添加操作")
            if operation.id in self._operations:
                raise ValueError(f"操作已存在: {operation.id}")

            counter = self._queue_counter
            self._queue_counter += 1
            self._events[operation.id] = threading.Event()
            # 先置 QUEUED 再入队发布：消费线程取到时状态必为 QUEUED，
            # 不可能反过来把终态覆盖回 QUEUED
            operation.update_status(OperationStatus.QUEUED)
            try:
                self._queue.put((-operation.priority, counter, operation), block=False)
            except queue.Full:
                # 并发提交穿过 qsize 预检的兜底；回滚注册避免泄漏
                self._events.pop(operation.id, None)
                raise ValueError("队列已满，无法添加操作") from None
            self._operations[operation.id] = operation

        self._stats["queue_size"] = self._queue.qsize()
        self.logger.info(
            "操作已添加到队列",
            operation_id=operation.id,
            operation_name=operation.name,
            priority=operation.priority,
            queue_size=self._stats["queue_size"],
        )

        return operation.id

    def get_state(self, operation_id: str) -> Operation | None:
        """获取操作的非阻塞快照（不存在或已被 TTL 淘汰时返回 None）"""
        return self._operations.get(operation_id)

    def get_result(
        self, operation_id: str, timeout: float | None = None
    ) -> OperationResult | None:
        """阻塞等待并获取操作终态结果。

        Args:
            operation_id: 操作ID
            timeout: 超时时间（秒），None 表示无限等待

        Returns:
            终态结果；超时仍未完成返回 None。
            操作不存在时抛出 KeyError（先用 get_state 确认存在性）。
        """
        operation = self._operations.get(operation_id)
        if operation is None:
            raise KeyError(operation_id)

        if operation.result is not None:
            return operation.result

        event = self._events.get(operation_id)
        if event is not None and not event.wait(timeout):
            return None  # 超时，操作仍在排队/执行

        return operation.result

    def get_queue_stats(self) -> dict[str, Any]:
        """获取队列统计信息"""
        return {
            **self._stats,
            "processing": self._running,
            "running_count": len(self._running_operations),
            "completed_count": len(self._completed_operations),
            "queued_count": self._queue.qsize(),
        }

    def cancel_operation(self, operation_id: str) -> bool:
        """取消操作（仅支持取消已入队但未执行的操作）。

        在锁内把 QUEUED 迁到 CANCELLED 并立即落终态唤醒等待方；消费
        线程已认领（RUNNING）则取消失败。被取消的操作留在优先级队列
        中无法移除，消费时认领失败被跳过。

        Returns:
            bool: 是否成功取消
        """
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation is None or operation.status is not OperationStatus.QUEUED:
                return False
            self._settle(
                operation,
                OperationResult(
                    status=OperationStatus.CANCELLED,
                    success=False,
                    message="操作已取消",
                    error_code=ErrorCode.CANCELLED,
                ),
            )

        self.logger.info("操作已标记为取消", operation_id=operation_id)
        return True
