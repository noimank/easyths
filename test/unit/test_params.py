"""操作参数模型校验规则的单元测试（无需 GUI/服务端）。"""

import pytest
from pydantic import ValidationError

from easyths.operations.params import (
    AccountSwitchParams,
    ConditionOrderParams,
    HistoricalQueryParams,
    LimitOrderParams,
    MarketOrderParams,
    OrderCancelParams,
    ReverseRepoBuyParams,
    StopLossParams,
    format_price,
)


def test_stock_code_must_be_six_digits():
    with pytest.raises(ValidationError):
        LimitOrderParams(stock_code="6000", price=10, quantity=100)
    with pytest.raises(ValidationError):
        LimitOrderParams(stock_code="6000000", price=10, quantity=100)
    with pytest.raises(ValidationError):
        LimitOrderParams(stock_code="60000a", price=10, quantity=100)


def test_lot_size_rules():
    # 股票：100 起且 100 的倍数
    LimitOrderParams(stock_code="600000", price=10, quantity=100)
    with pytest.raises(ValidationError):
        LimitOrderParams(stock_code="600000", price=10, quantity=50)
    with pytest.raises(ValidationError):
        LimitOrderParams(stock_code="600000", price=10, quantity=150)
    # 可转债（11/12 开头）：10 起且 10 的倍数
    LimitOrderParams(stock_code="113000", price=100, quantity=10)
    with pytest.raises(ValidationError):
        LimitOrderParams(stock_code="113000", price=100, quantity=5)


def test_price_and_quantity_positive():
    with pytest.raises(ValidationError):
        LimitOrderParams(stock_code="600000", price=0, quantity=100)
    with pytest.raises(ValidationError):
        LimitOrderParams(stock_code="600000", price=10, quantity=-100)


def test_order_amount_cap():
    with pytest.raises(ValidationError):
        LimitOrderParams(stock_code="600000", price=1000, quantity=10001)
    LimitOrderParams(stock_code="600000", price=1000, quantity=10000)


def test_unknown_params_forbidden():
    with pytest.raises(ValidationError):
        LimitOrderParams(stock_code="600000", price=10, quantity=100, typo=1)


def test_market_strategy_range():
    MarketOrderParams(stock_code="600000", quantity=100)
    MarketOrderParams(stock_code="600000", quantity=100, execution_strategy=6)
    with pytest.raises(ValidationError):
        MarketOrderParams(stock_code="600000", quantity=100, execution_strategy=0)
    with pytest.raises(ValidationError):
        MarketOrderParams(stock_code="600000", quantity=100, execution_strategy=7)


def test_condition_expire_days_enum():
    ConditionOrderParams(stock_code="600000", target_price=10, quantity=100)
    ConditionOrderParams(
        stock_code="600000", target_price=10, quantity=100, expire_days=1
    )
    with pytest.raises(ValidationError):
        ConditionOrderParams(
            stock_code="600000", target_price=10, quantity=100, expire_days=7
        )


def test_stop_loss_optional_quantity():
    StopLossParams(stock_code="600000", stop_loss_percent=3, stop_profit_percent=5)
    StopLossParams(
        stock_code="600000", stop_loss_percent=3, stop_profit_percent=5, quantity=100
    )
    # 可选数量同样受手数规则约束
    with pytest.raises(ValidationError):
        StopLossParams(
            stock_code="600000", stop_loss_percent=3, stop_profit_percent=5, quantity=50
        )
    with pytest.raises(ValidationError):
        StopLossParams(stock_code="600000", stop_loss_percent=0, stop_profit_percent=5)


def test_cancel_params_literals():
    OrderCancelParams()
    OrderCancelParams(stock_code="600000", cancel_type="buy")
    with pytest.raises(ValidationError):
        OrderCancelParams(cancel_type="both")
    with pytest.raises(ValidationError):
        OrderCancelParams(stock_code="60000")


def test_historical_time_range_literal():
    HistoricalQueryParams()
    HistoricalQueryParams(time_range="近一周")
    with pytest.raises(ValidationError):
        HistoricalQueryParams(time_range="近半年")


def test_account_switch_params():
    AccountSwitchParams(account_name="模拟账户")
    with pytest.raises(ValidationError):
        AccountSwitchParams()  # 缺失
    with pytest.raises(ValidationError):
        AccountSwitchParams(account_name="")  # 空串
    with pytest.raises(ValidationError):
        AccountSwitchParams(account_name="模拟账户", typo=1)  # 未知字段


def test_reverse_repo_amount_unit():
    ReverseRepoBuyParams(market="上海", time_range="1天期", amount=1000)
    with pytest.raises(ValidationError):
        ReverseRepoBuyParams(market="上海", time_range="1天期", amount=1500)
    with pytest.raises(ValidationError):
        ReverseRepoBuyParams(market="北京", time_range="1天期", amount=1000)
    with pytest.raises(ValidationError):
        ReverseRepoBuyParams(market="上海", time_range="5天期", amount=1000)


def test_format_price_precision():
    # ETF/可转债（5/1 开头）3 位小数，其余 2 位
    assert format_price("510300", 1.2345) == "1.234"
    assert format_price("113000", 100.5) == "100.500"
    assert format_price("600000", 10.5) == "10.50"
