"""多账户框架单元测试：缓存语义、信封 current_used_account 透传、切换逻辑。

GUI 交互（下拉读取、Alt+序号 切换）以测试桩替换，只验证框架与业务判断。
"""

import time

import pytest

from easyths.core.account_state import AccountState, account_state
from easyths.core.base_operation import BaseOperation, operation_registry
from easyths.core.operation_queue import OperationQueue
from easyths.models.operations import (
    APIResponse,
    EmptyParams,
    ErrorCode,
    Operation,
    OperationResult,
    OperationStatus,
)
from easyths.operations.account_query import AccountQueryOperation
from easyths.operations.account_switch import AccountSwitchOperation
from easyths.operations.params import AccountSwitchParams
from easyths.operations.results import ResultModel


@pytest.fixture(autouse=True)
def _reset_account_state():
    """全局账户缓存在测试间互不泄漏"""
    account_state.clear()
    yield
    account_state.clear()


# ============ 缓存语义 ============


def test_fresh_state_accounts_empty():
    """未初始化时可用账户列表为空列表。"""
    assert AccountState().available_accounts == []


def test_update_accounts_replaces_list_only():
    """刷新只替换可用账户列表，不动当前使用账户（同源读取保证二者一致）。"""
    state = AccountState()
    state.update_available_accounts([("A", 0), ("B", 1)])
    assert state.available_accounts == [("A", 0), ("B", 1)]

    state.set_current_used_account("A")
    state.update_available_accounts([("A", 0), ("B", 1), ("C", 2)])
    assert state.available_accounts == [("A", 0), ("B", 1), ("C", 2)]
    assert state.current_used_account == "A"


def test_accounts_property_returns_copy():
    state = AccountState()
    state.update_available_accounts([("A", 0)])
    state.available_accounts.append(("B", 1))
    assert state.available_accounts == [("A", 0)]


# ============ 信封 current_used_account 透传 ============


def test_ok_fail_carry_current_used_account():
    """操作结果自动附带缓存中的当前使用账户（未确认为 None）。"""
    op = AccountQueryOperation(automator=None)
    assert op._ok().current_used_account is None
    account_state.set_current_used_account("A账户")
    assert op._ok().current_used_account == "A账户"
    assert op._fail("拒绝", ErrorCode.CLIENT_REJECTED).current_used_account == "A账户"


def test_api_response_from_result_passes_current_used_account():
    result = OperationResult(
        status=OperationStatus.COMPLETED, success=True, current_used_account="A账户"
    )
    assert APIResponse.from_result(result).current_used_account == "A账户"


# ============ account_query 接线（GUI 桩替换） ============


class _StubAccountQuery(AccountQueryOperation):
    def _read_accounts(self) -> list[tuple[str, int]]:
        # 模拟选中项识别（与真实实现同构：读取中写当前使用账户，清洗名一致）
        account_state.set_current_used_account("A账户")
        return [("A账户", 0), ("B账户", 1)]


class _NoGuiAccountQuery(AccountQueryOperation):
    def _read_accounts(self) -> list[tuple[str, int]]:
        raise AssertionError("已缓存时不应触达 GUI 读取")


def test_account_query_wiring_refreshes_cache():
    result = _StubAccountQuery(automator=None).execute(EmptyParams())
    assert result.success
    # 当前使用账户只在信封，data 仅账户列表
    assert result.data == {
        "available_accounts": [
            {"account_name": "A账户", "account_index": 0},
            {"account_name": "B账户", "account_index": 1},
        ],
    }
    assert result.current_used_account == "A账户"
    assert account_state.available_accounts == [("A账户", 0), ("B账户", 1)]
    assert account_state.current_used_account == "A账户"


def test_account_query_cache_hit_skips_gui():
    """已缓存时直接复用，不再触发 GUI 读取（幂等获取）。"""
    account_state.update_available_accounts([("A账户", 0), ("B账户", 1)])
    result = _NoGuiAccountQuery(automator=None).execute(EmptyParams())
    assert result.success
    assert result.data["available_accounts"] == [
        {"account_name": "A账户", "account_index": 0},
        {"account_name": "B账户", "account_index": 1},
    ]


# ============ account_switch 业务判断（GUI 桩替换） ============


class _KeyboardSwitchStub(AccountSwitchOperation):
    """记录 Alt+序号 按键的切换替身（不触真实 GUI）"""

    def __init__(self):
        super().__init__(automator=None)
        self.sent_keys: list[str] = []

    def get_main_window(self, wrapper_obj: bool = False):
        recorder = self

        class _Window:
            def type_keys(self, keys: str) -> None:
                recorder.sent_keys.append(keys)

        return _Window()


class _NoGuiSwitch(AccountSwitchOperation):
    """不应触 GUI 的场景替身"""

    def get_main_window(self, wrapper_obj: bool = False):
        raise AssertionError("该场景不应触达主窗口")


def test_account_switch_unknown_account_rejected():
    account_state.update_available_accounts([("A账户", 1), ("B账户", 2)])
    account_state.set_current_used_account("A账户")

    result = _NoGuiSwitch().execute(AccountSwitchParams(account_name="X账户"))
    assert result.success is False
    assert result.error_code == ErrorCode.CLIENT_REJECTED
    assert "不存在" in result.message
    assert "可用账户" in result.message
    assert account_state.current_used_account == "A账户"


def test_account_switch_empty_cache_rejected():
    """可用账户未初始化时同样拒绝并提示先 account_query（如重连后缓存已清空）。"""
    result = _NoGuiSwitch().execute(AccountSwitchParams(account_name="A账户"))
    assert result.success is False
    assert result.error_code == ErrorCode.CLIENT_REJECTED
    assert "account_query" in result.message


def test_account_switch_same_account_noop():
    """目标即当前使用账户：直接成功，不触 GUI。"""
    account_state.update_available_accounts([("A账户", 1), ("B账户", 2)])
    account_state.set_current_used_account("A账户")

    result = _NoGuiSwitch().execute(AccountSwitchParams(account_name="A账户"))
    assert result.success
    assert "无需切换" in result.message
    assert result.data == {"previous_used_account": "A账户"}
    assert account_state.current_used_account == "A账户"


def test_account_switch_success_sends_alt_index():
    account_state.update_available_accounts([("A账户", 1), ("B账户", 2)])
    account_state.set_current_used_account("A账户")

    op = _KeyboardSwitchStub()
    result = op.execute(AccountSwitchParams(account_name="B账户"))
    assert result.success
    assert op.sent_keys == ["%2"]  # Alt + 账户序号
    assert result.data == {"previous_used_account": "A账户"}
    assert account_state.current_used_account == "B账户"
    assert result.current_used_account == "B账户"


# ============ 看门狗超时结果的 current_used_account ============


class _EmptyResult(ResultModel):
    """无字段结果占位"""


class _HangOperation(BaseOperation[EmptyParams]):
    """执行期阻塞，用于触发看门狗超时"""

    operation_name = "ut_account_hang_op"
    description = "账户信封测试用卡死操作"
    Params = EmptyParams
    Result = _EmptyResult

    def pre_execute(self) -> bool:
        return True

    def execute(self, params: EmptyParams) -> OperationResult:
        time.sleep(5)
        return self._ok()


operation_registry.register(_HangOperation)


def test_watchdog_timeout_result_carries_current_used_account():
    """超时收尾的操作确已执行，结果附带执行时当前使用账户。"""
    account_state.set_current_used_account("A账户")
    q = OperationQueue(automator=None)
    q.operation_timeout = 0.2
    q.start()
    try:
        op_id = q.submit(Operation(name="ut_account_hang_op", params={}))
        result = q.get_result(op_id, timeout=5)
        assert result is not None
        assert result.error_code == ErrorCode.TIMEOUT
        assert result.current_used_account == "A账户"
    finally:
        q.stop()


# ============ 执行前账户指令（Operation.account_name） ============

SWITCH_CALLS: list[str] = []
EXECUTION_ORDER: list[str] = []


class _SwitchStubOperation(AccountSwitchOperation):
    """注册表中的 account_switch 替身：可控成功/拒绝（不触真实 GUI）"""

    reject = False

    def pre_execute(self) -> bool:
        return True

    def execute(self, params: AccountSwitchParams) -> OperationResult:
        EXECUTION_ORDER.append("switch")
        SWITCH_CALLS.append(params.account_name)
        if self.reject:
            return self._fail("账户不存在", ErrorCode.CLIENT_REJECTED)
        account_state.set_current_used_account(params.account_name)
        return self._ok()


class _TargetOperation(BaseOperation[EmptyParams]):
    """携带账户指令的目标操作"""

    operation_name = "ut_account_target_op"
    description = "账户指令测试目标操作"
    Params = EmptyParams
    Result = _EmptyResult

    def pre_execute(self) -> bool:
        return True

    def execute(self, params: EmptyParams) -> OperationResult:
        EXECUTION_ORDER.append("target")
        return self._ok(data="done")


operation_registry.register(_TargetOperation)


@pytest.fixture
def stub_switch(monkeypatch):
    """把注册表中的 account_switch 替换为可控替身，测试后清理实例缓存"""
    monkeypatch.setitem(
        operation_registry._operations, "account_switch", _SwitchStubOperation
    )
    monkeypatch.delitem(operation_registry._instances, "account_switch", raising=False)
    SWITCH_CALLS.clear()
    EXECUTION_ORDER.clear()
    yield
    operation_registry._instances.pop("account_switch", None)


def test_account_directive_switches_before_operation(stub_switch):
    """携带 account_name 的操作：同一队列槽内先切换再执行，结果携带新账户。"""
    q = OperationQueue(automator=None)
    q.start()
    try:
        op = Operation(name="ut_account_target_op", params={}, account_name="B账户")
        result = q.get_result(q.submit(op), timeout=5)
        assert result is not None and result.success
        assert SWITCH_CALLS == ["B账户"]
        assert EXECUTION_ORDER == ["switch", "target"]
        assert account_state.current_used_account == "B账户"
        assert result.current_used_account == "B账户"
    finally:
        q.stop()


def test_without_account_directive_no_switch(stub_switch):
    """未携带 account_name：不触发切换，直接执行目标操作。"""
    q = OperationQueue(automator=None)
    q.start()
    try:
        result = q.get_result(
            q.submit(Operation(name="ut_account_target_op", params={})), timeout=5
        )
        assert result is not None and result.success
        assert SWITCH_CALLS == []
        assert EXECUTION_ORDER == ["target"]
    finally:
        q.stop()


def test_switch_failure_short_circuits_operation(stub_switch, monkeypatch):
    """切换被拒：目标操作不执行，以切换失败结果收尾。"""
    monkeypatch.setattr(_SwitchStubOperation, "reject", True)
    q = OperationQueue(automator=None)
    q.start()
    try:
        op = Operation(name="ut_account_target_op", params={}, account_name="X账户")
        result = q.get_result(q.submit(op), timeout=5)
        assert result is not None
        assert result.success is False
        assert result.error_code == ErrorCode.CLIENT_REJECTED
        assert "执行前账户切换失败" in result.message
        assert EXECUTION_ORDER == ["switch"]
    finally:
        q.stop()


# ============ 启动账户初始化 ============


def test_initialize_account_state_populates_cache(monkeypatch):
    """启动账户初始化：注册表就绪时提交 account_query 即填充缓存。

    回归：曾因插件加载晚于 initialize_components 导致「未找到操作: account_query」。
    """
    from easyths.main import initialize_account_state

    class _InitQueryStub(_StubAccountQuery):
        def pre_execute(self) -> bool:
            return True

    monkeypatch.setitem(operation_registry._operations, "account_query", _InitQueryStub)
    monkeypatch.delitem(operation_registry._instances, "account_query", raising=False)
    q = OperationQueue(automator=None)
    q.start()
    try:
        initialize_account_state(q)
        assert account_state.available_accounts == [("A账户", 0), ("B账户", 1)]
        assert account_state.current_used_account == "A账户"
    finally:
        q.stop()
        operation_registry._instances.pop("account_query", None)
