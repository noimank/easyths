"""自动化测试 - 同步操作模式

需要运行中的同花顺客户端，使用 ``pytest test/integration/automation_test.py``
运行。连接客户端与账户缓存初始化由 conftest 夹具统一完成，用例只保留
操作参数与业务断言。

Author: noimank
Email: noimank@163.com
"""

import pytest

from easyths.core.account_state import account_state
from easyths.core.tonghuashun_automator import TonghuashunAutomator
from easyths.operations.account_query import AccountQueryOperation
from easyths.operations.buy import BuyOperation
from easyths.operations.condition_buy import ConditionBuyOperation
from easyths.operations.condition_order_cancel import ConditionOrderCancelOperation
from easyths.operations.condition_order_query import ConditionOrderQueryOperation
from easyths.operations.condition_sell import ConditionSellOperation
from easyths.operations.funds_query import FundsQueryOperation
from easyths.operations.historical_commission_query import (
    HistoricalCommissionQueryOperation,
)
from easyths.operations.holding_query import HoldingQueryOperation
from easyths.operations.market_buy import MarketBuyOperation
from easyths.operations.market_sell import MarketSellOperation
from easyths.operations.order_cancel import OrderCancelOperation
from easyths.operations.order_query import OrderQueryOperation
from easyths.operations.reverse_repo_buy import ReverseRepoBuyOperation
from easyths.operations.reverse_repo_query import ReverseRepoQueryOperation
from easyths.operations.sell import SellOperation
from easyths.operations.stop_loss_profit import StopLossProfitOperation

pytestmark = pytest.mark.integration


def test_automator_basic():
    """测试自动化器基本功能（独占实例，不干扰会话级 automator）"""
    automator = TonghuashunAutomator()

    try:
        connected = automator.connect()
        print(f"连接结果: {connected}")
        assert connected, "连接失败"
        assert automator.is_connected(), "未连接"
        assert automator.main_window is not None, "主窗口为空"
        print("测试通过!")
    finally:
        automator.disconnect()


def test_account_query(automator):
    """账户查询（冷路径：清空缓存后重新读取客户端账户下拉）"""
    account_state.clear()

    result = AccountQueryOperation(automator).run({})
    assert result.success, result.message
    assert account_state.available_accounts, "未读取到任何账户"
    assert account_state.current_used_account, "未识别当前使用账户"
    print(f"操作结果: {result}")


def test_account_switch(accounts, switch_account):
    """账户切换（仅在登录了多个账户时执行，结束后还原）"""
    previous = account_state.current_used_account
    target = next((name for name, _ in accounts if name != previous), None)
    if target is None:
        pytest.skip("仅登录一个账户，无法验证账户切换")

    try:
        result = switch_account(target)
        assert result.success, result.message
        assert account_state.current_used_account == target
        print(f"操作结果: {result}")
    finally:
        # 还原当前账户，避免影响后续用例
        switch_account(previous)


def test_buy_op(run_op):
    """买入操作"""
    result = run_op(
        BuyOperation, {"stock_code": "000001", "price": 110.55, "quantity": 100}
    )
    print(f"买入结果: {result.success}, data: {result.data}")


def test_sell_op(run_op):
    """卖出操作"""
    result = run_op(
        SellOperation, {"stock_code": "000001", "price": 11.55, "quantity": 1000}
    )
    print(f"操作结果: {result.success}, data: {result.data}")


def test_funds_query_op(run_op):
    """资金查询"""
    result = run_op(FundsQueryOperation)
    print(f"操作结果: {result.success}, data: {result.data}")


def test_order_cancel_op(run_op):
    """撤单"""
    result = run_op(
        OrderCancelOperation, {"stock_code": "000001", "cancel_type": "all"}
    )
    print(f"操作结果: {result.success}, data: {result.data}")


def test_holding_query_op(run_op):
    """持仓查询（银河证券的菜单名差异依赖账户缓存初始化）"""
    result = run_op(HoldingQueryOperation)
    print(f"操作结果: {result}")


def test_order_query_op(run_op):
    """委托查询"""
    result = run_op(OrderQueryOperation, {"stock_code": "000001"})
    print(f"操作结果: {result.success}, data: {result.data}")


def test_historical_commission_query_op(run_op):
    """历史委托查询"""
    result = run_op(HistoricalCommissionQueryOperation)
    print(f"操作结果: {result.success}, data: {result.data}")


def test_reverse_repo_buy_op(run_op):
    """逆回购买入"""
    result = run_op(
        ReverseRepoBuyOperation,
        {
            # 交易市场   ["上海", "深圳"]
            "market": "上海",
            # 回购期限   ["1天期", "2天期", "3天期", "4天期", "7天期"]
            "time_range": "1天期",
            "amount": 100000,
        },
    )
    print(f"操作结果: {result.success}, data: {result.data}, message={result.message}")


def test_reverse_repo_query_op(run_op):
    """逆回购查询"""
    result = run_op(
        ReverseRepoQueryOperation,
        {
            # 交易市场   ["上海", "深圳"]
            "market": "上海",
            # 回购期限   ["1天期", "2天期", "3天期", "4天期", "7天期"]
            "time_range": "1天期",
            "amount": 100000,
        },
    )
    print(f"操作结果: {result.success}, data: {result.data}")


def test_condition_buy_op(run_op):
    """条件买入"""
    result = run_op(
        ConditionBuyOperation,
        {"stock_code": "000001", "target_price": 12.1, "quantity": 100},
    )
    print(f"操作结果: {result.success}, data: {result.data}")


def test_condition_sell_op(run_op):
    """条件卖出"""
    result = run_op(
        ConditionSellOperation,
        {"stock_code": "000001", "target_price": 12.1, "quantity": 100},
    )
    print(f"操作结果: {result.success}, data: {result.data}")


def test_stop_loss_profit_op(run_op):
    """止盈止损"""
    result = run_op(
        StopLossProfitOperation,
        {
            "stock_code": "000001",
            "stop_loss_percent": 3.1,
            "stop_profit_percent": 5.6,
            "quantity": 100,
            "expire_days": 1,
        },
    )
    print(f"操作结果: {result.success}, data: {result.data}")


def test_condition_order_query_op(run_op):
    """条件单查询"""
    result = run_op(ConditionOrderQueryOperation)
    print(f"操作结果: {result.success}, data: {result.data}")


def test_condition_order_cancel_op(run_op):
    """条件单撤销"""
    result = run_op(ConditionOrderCancelOperation)
    print(f"操作结果: {result.success}, data: {result.data}")


def test_market_buy_op(run_op):
    """市价买入"""
    result = run_op(
        MarketBuyOperation,
        {"stock_code": "000001", "quantity": 100, "execution_strategy": 7},
    )
    print(f"操作结果: {result.success}, data: {result.data}, message: {result.message}")


def test_market_sell_op(run_op):
    """市价卖出"""
    result = run_op(
        MarketSellOperation,
        {"stock_code": "000001", "quantity": 100, "execution_strategy": 2},
    )
    print(f"操作结果: {result.success}, data: {result.data}, message: {result.message}")
