"""集成测试公共前置（仅 test/integration 生效）。

自动化类用例统一依赖 ``automator`` / ``run_op`` 夹具：连接客户端、
初始化账户缓存、创建操作实例都由夹具完成，用例只写参数与业务断言。

账户缓存是进程内单例（``account_state``），生产启动流程会执行一次
``account_query`` 完成初始化（``main.initialize_account_state``）；
集成测试绕过服务端，因此必须由夹具补上这一步，否则
``get_current_account_name`` / 结果信封的 ``current_used_account``
以及账户切换都会拿到空缓存。
"""

from typing import Any

import pytest

from easyths.core.account_state import account_state
from easyths.core.base_operation import BaseOperation
from easyths.core.tonghuashun_automator import TonghuashunAutomator
from easyths.models.operations import OperationResult
from easyths.operations.account_query import AccountQueryOperation
from easyths.operations.account_switch import AccountSwitchOperation


@pytest.fixture(scope="session")
def automator():
    """连接同花顺客户端（会话级复用，只连一次）

    客户端未运行/未登录属于环境不满足，跳过而非报错；断链统一在
    会话结束时清理，用例内不要自行 disconnect。
    """
    automator = TonghuashunAutomator()
    if not automator.connect():
        pytest.skip("同花顺客户端未运行或连接失败，请先启动并登录交易客户端")
    yield automator
    automator.disconnect()


@pytest.fixture
def accounts(automator):
    """账户缓存初始化（对应生产启动时的 account_query）

    已初始化时为缓存命中，不触 GUI；未初始化时读取客户端账户下拉并
    识别当前使用账户。初始化失败视为测试环境不可用，直接失败并给出
    操作结果信息。
    """
    result = AccountQueryOperation(automator).run({})
    if not result.success:
        pytest.fail(f"账户信息初始化失败：{result.message}", pytrace=False)
    assert account_state.current_used_account, "账户列表已初始化但未识别当前使用账户"
    return account_state.available_accounts


@pytest.fixture
def run_op(automator, accounts):
    """创建操作实例并同步执行，返回 OperationResult

    用法::

        def test_buy_op(run_op):
            result = run_op(BuyOperation, {"stock_code": "000001", "price": 11.55, "quantity": 100})
    """

    def _run(
        operation_class: type[BaseOperation], params: dict[str, Any] | None = None
    ) -> OperationResult:
        return operation_class(automator).run(params or {})

    return _run


@pytest.fixture
def switch_account(automator, accounts):
    """切换账户的小工具（目标账户名取自 account_query 结果）"""

    def _switch(account_name: str) -> OperationResult:
        return AccountSwitchOperation(automator).run({"account_name": account_name})

    return _switch
