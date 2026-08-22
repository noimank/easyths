"""OperationQueue 行为单元测试（无需 GUI/同花顺客户端）。"""

import threading
import time
from datetime import datetime, timedelta

import pytest

from easyths.core.base_operation import BaseOperation, operation_registry
from easyths.core.operation_queue import (
    _SWEEP_INTERVAL,
    RESULT_TTL,
    OperationQueue,
)
from easyths.models.operations import (
    EmptyParams,
    ErrorCode,
    Operation,
    OperationResult,
    OperationStatus,
)
from easyths.operations.results import ResultModel

# 记录操作实际执行顺序与执行线程
EXECUTED_ORDER: list[str] = []
THREADS: list[int] = []


class TagParams(EmptyParams):
    tag: str


class TagResult(ResultModel):
    tag: str


class RecorderOperation(BaseOperation[TagParams]):
    """按 tag 记录执行顺序的测试操作"""

    operation_name = "ut_recorder_op"
    description = "单元测试用操作"
    Params = TagParams
    Result = TagResult

    def pre_execute(self) -> bool:
        return True

    def execute(self, params: TagParams) -> OperationResult:
        EXECUTED_ORDER.append(params.tag)
        THREADS.append(threading.get_ident())
        return self._ok(data=params.tag)


class HangOperation(BaseOperation[TagParams]):
    """执行期长时间阻塞，用于触发看门狗超时"""

    operation_name = "ut_hang_op"
    description = "看门狗测试用卡死操作"
    Params = TagParams
    Result = TagResult

    def pre_execute(self) -> bool:
        return True

    def execute(self, params: TagParams) -> OperationResult:
        EXECUTED_ORDER.append(params.tag)
        THREADS.append(threading.get_ident())
        time.sleep(5)
        return self._ok(data=params.tag)


class BlockingOperation(BaseOperation[TagParams]):
    """占用消费线程直到 RELEASE 置位，用于构造 RUNNING 边界"""

    operation_name = "ut_blocking_op"
    description = "占用消费线程的测试操作"
    Params = TagParams
    Result = TagResult

    RELEASE = threading.Event()

    def pre_execute(self) -> bool:
        return True

    def execute(self, params: TagParams) -> OperationResult:
        EXECUTED_ORDER.append(params.tag)
        self.RELEASE.wait(timeout=5)
        return self._ok(data=params.tag)


operation_registry.register(RecorderOperation)
operation_registry.register(HangOperation)
operation_registry.register(BlockingOperation)


def _wait_until(predicate, timeout: float = 5.0) -> None:
    """轮询等待条件成立，超时断言失败"""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("等待条件超时")


@pytest.fixture
def started_queue():
    q = OperationQueue(automator=None)
    q.start()
    yield q
    q.stop()


def _submit(q: OperationQueue, tag: str, priority: int = 0) -> str:
    return q.submit(
        Operation(name="ut_recorder_op", params={"tag": tag}, priority=priority)
    )


def test_priority_order(started_queue):
    """高优先级操作先于低优先级执行（同批入队时）。"""
    EXECUTED_ORDER.clear()
    # 先停止消费再入队，保证两个操作在同一批次中比较优先级
    started_queue.stop()

    low_id = _submit(started_queue, "low", priority=0)
    high_id = _submit(started_queue, "high", priority=5)
    started_queue.start()

    low_result = started_queue.get_result(low_id, timeout=5)
    high_result = started_queue.get_result(high_id, timeout=5)
    assert low_result is not None and low_result.success
    assert high_result is not None and high_result.success
    assert EXECUTED_ORDER == ["high", "low"]


def test_cancel_before_execution(started_queue):
    """已入队未执行的操作可取消，执行时被跳过并返回取消结果。"""
    started_queue.stop()

    op_id = _submit(started_queue, "to-cancel")
    assert started_queue.cancel_operation(op_id) is True
    assert started_queue.get_state(op_id).status == OperationStatus.CANCELLED

    started_queue.start()
    result = started_queue.get_result(op_id, timeout=5)
    assert result is not None
    assert result.success is False
    assert result.error_code == ErrorCode.CANCELLED
    assert result.status == OperationStatus.CANCELLED
    assert "to-cancel" not in EXECUTED_ORDER


def test_cancel_unknown_fails():
    """未知操作不可取消。"""
    q = OperationQueue(automator=None)
    assert q.cancel_operation("not-exist") is False


def test_get_result_unknown_raises_key_error():
    """操作不存在时 get_result 明确抛 KeyError（区别于超时的 None）。"""
    q = OperationQueue(automator=None)
    with pytest.raises(KeyError):
        q.get_result("not-exist", timeout=0.1)


def test_get_result_timeout_returns_none(started_queue):
    """超时（操作仍在排队/执行）返回 None，与不存在（KeyError）区分。"""
    started_queue.stop()
    op_id = _submit(started_queue, "queued")
    assert started_queue.get_result(op_id, timeout=0.1) is None


def test_stop_drains_queued_operations():
    """stop 时排队未执行的操作以失败终态收尾并唤醒等待方。"""
    q = OperationQueue(automator=None)
    op_id = _submit(q, "drain-me")
    q.stop()

    op = q.get_state(op_id)
    assert op.status == OperationStatus.FAILED
    assert op.result.error_code == ErrorCode.INTERNAL
    assert "服务关闭" in op.result.message
    # 事件已置位，等待方立即拿到结果
    assert q.get_result(op_id, timeout=0.1) is op.result


def test_sweep_expired_evicts_old_operations():
    """超过 TTL 的已完成操作记录被淘汰，未过期的不受影响。"""
    q = OperationQueue(automator=None)

    old_op = Operation(name="ut_recorder_op", params={"tag": "old"})
    old_op.update_status(OperationStatus.COMPLETED)
    old_op.completed_at = datetime.now() - RESULT_TTL - timedelta(seconds=1)
    q._operations[old_op.id] = old_op
    q._completed_operations[old_op.id] = old_op
    q._events[old_op.id] = threading.Event()

    fresh_op = Operation(name="ut_recorder_op", params={"tag": "fresh"})
    fresh_op.update_status(OperationStatus.COMPLETED)
    q._operations[fresh_op.id] = fresh_op
    q._completed_operations[fresh_op.id] = fresh_op

    # 跳过扫描间隔限制后触发淘汰
    q._last_sweep = datetime.now() - _SWEEP_INTERVAL - timedelta(seconds=1)
    q._sweep_expired()

    assert old_op.id not in q._completed_operations
    assert old_op.id not in q._operations
    assert old_op.id not in q._events
    assert fresh_op.id in q._completed_operations
    assert fresh_op.id in q._operations


def test_get_status_after_submit():
    """提交后状态为 QUEUED，无需启动消费线程。"""
    q = OperationQueue(automator=None)
    op_id = _submit(q, "queued")
    assert q.get_state(op_id).status == OperationStatus.QUEUED


def test_result_ttl_is_three_hours():
    """业务约定：操作结果保留 3 小时（硬编码）。"""
    assert timedelta(hours=3) == RESULT_TTL


def test_invalid_params_fail_fast():
    """参数校验失败直接返回 invalid_params 终态，不触达 execute。"""
    op = RecorderOperation(automator=None)
    result = op.run({"tag": "x", "unknown": 1})
    assert result.success is False
    assert result.error_code == ErrorCode.INVALID_PARAMS
    assert result.status == OperationStatus.FAILED


def test_execution_timeout_fails_operation_and_keeps_queue_alive():
    """单操作超过看门狗时限：以 TIMEOUT 失败收尾，队列继续消费后续操作。"""
    EXECUTED_ORDER.clear()
    THREADS.clear()
    q = OperationQueue(automator=None)
    q.operation_timeout = 0.2
    q.start()
    try:
        hang_id = q.submit(Operation(name="ut_hang_op", params={"tag": "hang"}))
        next_id = _submit(q, "after-hang")

        hang_result = q.get_result(hang_id, timeout=5)
        assert hang_result is not None
        assert hang_result.success is False
        assert hang_result.error_code == ErrorCode.TIMEOUT

        # 看门狗收尾后队列未被拖死，后续操作正常执行
        next_result = q.get_result(next_id, timeout=5)
        assert next_result is not None and next_result.success
        assert q.get_queue_stats()["total_timeouts"] == 1
        # 超时后执行线程退役，后续操作换新线程执行
        assert len(THREADS) == 2
        assert THREADS[0] != THREADS[1]
    finally:
        q.stop()


def test_operations_share_persistent_executor_thread():
    """无看门狗超时时，所有操作固定在同一常驻执行线程上运行。

    线程绑定资源（如 mss 的 GDI 设备上下文）依赖此语义跨操作复用。
    """
    THREADS.clear()
    q = OperationQueue(automator=None)
    q.start()
    try:
        for tag in ("a", "b", "c"):
            result = q.get_result(_submit(q, tag), timeout=5)
            assert result is not None and result.success
        assert len(THREADS) == 3
        assert len(set(THREADS)) == 1
    finally:
        q.stop()


def test_cancel_running_operation_fails():
    """执行中（已认领）的操作不可取消。"""
    BlockingOperation.RELEASE.clear()
    q = OperationQueue(automator=None)
    q.start()
    try:
        op_id = q.submit(Operation(name="ut_blocking_op", params={"tag": "blocking"}))
        _wait_until(
            lambda: q.get_state(op_id).status == OperationStatus.RUNNING,
        )
        assert q.cancel_operation(op_id) is False
    finally:
        BlockingOperation.RELEASE.set()
        q.stop()


def test_stop_settled_operation_never_executes_after_restart():
    """stop 已收尾的操作即使随后被消费线程取到也不会再执行。"""
    EXECUTED_ORDER.clear()
    q = OperationQueue(automator=None)
    op_id = _submit(q, "after-stop")
    q.stop()

    q.start()
    try:
        result = q.get_result(op_id, timeout=5)
        assert result is not None
        assert result.error_code == ErrorCode.INTERNAL
        assert "after-stop" not in EXECUTED_ORDER
    finally:
        q.stop()


def test_submit_duplicate_id_rejected():
    """相同 ID 重复提交被拒绝。"""
    q = OperationQueue(automator=None)
    op = Operation(id="fixed-id", name="ut_recorder_op", params={"tag": "dup"})
    assert q.submit(op) == "fixed-id"
    with pytest.raises(ValueError, match="操作已存在"):
        q.submit(Operation(id="fixed-id", name="ut_recorder_op", params={"tag": "dup"}))


def test_submit_full_queue_raises_value_error():
    """队列满时提交以 ValueError 拒绝（对外契约，而非 queue.Full）。"""
    q = OperationQueue(automator=None)
    q.max_size = 1
    _submit(q, "first")
    with pytest.raises(ValueError, match="队列已满"):
        _submit(q, "second")
