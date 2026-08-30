"""结果契约单元测试：显式行装配、文本→数值转换、占位值为 null。"""

import re
from datetime import datetime

import pandas as pd
import pytest

from easyths.models.operations import (
    BEIJING_TZ,
    APIResponse,
    OperationResult,
    OperationStatus,
)
from easyths.operations.condition_order_query import ConditionOrderQueryOperation
from easyths.operations.historical_commission_query import (
    HistoricalCommissionQueryOperation,
)
from easyths.operations.holding_query import HoldingQueryOperation
from easyths.operations.order_cancel import _count_cancel_rows
from easyths.operations.order_query import OrderQueryOperation
from easyths.operations.results import (
    FundsResult,
    OrderCancelByContractResult,
    ReverseRepoQuote,
)


def _holding_raw() -> dict:
    """一条贴近客户端剪贴板的真实持仓记录（含千分位/百分号/--/多余列）"""
    return {
        "证券代码": "600000",
        "证券名称": "浦发银行\xa0",
        "持仓数量": "1,200",
        "可用数量": "1200",
        "冻结数量": "0",
        "参考成本价": "8.50",
        "当前价": "8.65",
        "浮动盈亏": "180.00",
        "盈亏比例(%)": "1.76",
        "当日盈亏": "--",
        "当日盈亏比(%)": "--",
        "最新市值": "10,380.00",
        "仓位占比(%)": "12.30",
        "当日买入": "0",
        "当日卖出": "0",
        "交易市场": "上海",
        "操作": "买入 卖出",
        "Unnamed: 16": "x",
    }


def test_holding_row_assembles_and_coerces():
    dumped = HoldingQueryOperation().parse_holding_row(_holding_raw()).model_dump()
    assert dumped["stock_code"] == "600000"
    assert dumped["stock_name"] == "浦发银行"
    assert dumped["quantity"] == 1200
    assert dumped["current_price"] == 8.65
    assert dumped["profit_ratio"] == 1.76
    assert dumped["market_value"] == 10380.0
    # 占位值统一为 null，未装配的多余列（操作/Unnamed）不进入结果
    assert dumped["daily_profit"] is None
    assert "操作" not in dumped
    assert len(dumped) == 16


def test_holding_row_current_price_simulated_account():
    """模拟账户持仓列为「市价」，实盘为「当前价」；按显式顺序取值。"""
    raw = _holding_raw()
    del raw["当前价"]
    raw["市价"] = "8.70"
    assert HoldingQueryOperation().parse_holding_row(raw).current_price == 8.7

    # 实盘列存在时优先，即使值为占位符也不回退到模拟列
    raw["当前价"] = "--"
    assert HoldingQueryOperation().parse_holding_row(raw).current_price is None


def test_holding_row_quantities_simulated_account():
    """模拟账户数量列为「股票余额/可用余额」，实盘为「持仓数量/可用数量」（语义相同）。"""
    raw = _holding_raw()
    del raw["持仓数量"]
    del raw["可用数量"]
    raw["股票余额"] = "1,200"
    raw["可用余额"] = "1,100"
    row = HoldingQueryOperation().parse_holding_row(raw)
    assert row.quantity == 1200
    assert row.available_quantity == 1100

    # 实盘列存在时优先
    raw["持仓数量"] = "900"
    assert HoldingQueryOperation().parse_holding_row(raw).quantity == 900


def test_holding_row_profit_ratio_simulated_account():
    """模拟账户盈亏比例列为「盈亏比(%)」，实盘为「盈亏比例(%)」；按显式顺序取值。"""
    raw = _holding_raw()
    del raw["盈亏比例(%)"]
    raw["盈亏比(%)"] = "1.8"
    assert HoldingQueryOperation().parse_holding_row(raw).profit_ratio == 1.8

    # 实盘列存在时优先，即使值为占位符也不回退到模拟列
    raw["盈亏比例(%)"] = "--"
    assert HoldingQueryOperation().parse_holding_row(raw).profit_ratio is None


def test_holding_row_missing_column_raises():
    """列名不匹配（客户端改版）时明确报错而非静默丢字段。"""
    raw = _holding_raw()
    del raw["证券代码"]
    with pytest.raises(KeyError):
        HoldingQueryOperation().parse_holding_row(raw)


def _order_raw() -> dict:
    return {
        "委托时间": "09:30:00",
        "证券代码": "600000",
        "证券名称": "浦发银行",
        "操作": "买入",
        "备注": "",
        "委托数量": "100",
        "成交数量": "0",
        "委托价格": "10.50",
        "成交均价": "--",
        "撤销数量": "0",
        "合同编号": "123456",
        "交易市场": "上海",
    }


def test_order_row_assembles():
    row = OrderQueryOperation().parse_order_row(_order_raw())
    assert row.operation == "买入"
    assert row.quantity == 100
    assert row.avg_fill_price is None

    historical = HistoricalCommissionQueryOperation().parse_historical_row(
        {**_order_raw(), "委托日期": "20260822"}
    )
    assert historical.order_date == "20260822"
    assert historical.contract_no == "123456"


def test_condition_order_row_assembles():
    row = ConditionOrderQueryOperation().parse_condition_row(
        {
            "状态": "未触发",
            "条件类型": "股价大于",
            "方向": "买入",
            "监控标的": "600000 浦发银行",
            "触发条件": "最新价 >= 10.50",
            "最新价": "10.42",
            "涨幅": "1.23%",
            "委托单": "买入100股 @ 10.50",
            "创建时间": "2026-08-22 09:30:00",
            "监控周期": "永久有效",
        }
    )
    dumped = row.model_dump()
    assert dumped["change_ratio"] == 1.23
    assert dumped["latest_price"] == 10.42


def test_funds_result_numeric():
    funds = FundsResult.model_validate(
        {
            "balance": "12,345.67",
            "frozen_amount": "--",
            "market_value": "10380.00",
            "total_assets": "22725.67",
            "available_amount": "12345.67",
            "withdrawable_amount": "12345.67",
            "holding_profit": "180.00",
            "daily_profit": "56.78",
            "daily_profit_ratio": "0.57%",
        }
    )
    dumped = funds.model_dump()
    assert dumped["balance"] == 12345.67
    assert dumped["frozen_amount"] is None
    assert dumped["daily_profit"] == 56.78
    assert dumped["daily_profit_ratio"] == 0.57


def test_funds_result_daily_profit_fields_optional():
    """旧版客户端无当日盈亏控件时两字段缺省，校验不报错。"""
    raw = {
        "balance": "12,345.67",
        "frozen_amount": "0.00",
        "market_value": "10380.00",
        "total_assets": "22725.67",
        "available_amount": "12345.67",
        "withdrawable_amount": "12345.67",
        "holding_profit": "180.00",
    }
    dumped = FundsResult.model_validate(raw).model_dump()
    assert dumped["daily_profit"] is None
    assert dumped["daily_profit_ratio"] is None


def test_reverse_repo_quote_strips_percent():
    quote = ReverseRepoQuote(market="上海", term="1天期", annual_rate="2.50%")
    assert quote.model_dump() == {"market": "上海", "term": "1天期", "annual_rate": 2.5}


def test_operation_result_timestamp_beijing_text():
    """OperationResult 序列化时间戳为北京时间秒级文本。"""
    result = OperationResult(status=OperationStatus.COMPLETED, success=True)
    dumped = result.model_dump(mode="json")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", dumped["timestamp"])


def test_from_result_passes_through_timestamp():
    """信封沿用操作完成时刻，而非响应构造时刻。"""
    fixed = datetime(2026, 8, 22, 6, 46, 56, tzinfo=BEIJING_TZ)
    result = OperationResult(
        status=OperationStatus.COMPLETED, success=True, timestamp=fixed
    )
    env = APIResponse.from_result(result)
    assert env.timestamp == fixed
    assert env.model_dump(mode="json")["timestamp"] == "2026-08-22 06:46:56"


def test_count_cancel_rows():
    df = pd.DataFrame(
        {
            "操作": ["买入", "卖出", "买入", "撤单"],
            "委托数量": [100, 200, 300, 400],
        }
    )
    assert _count_cancel_rows(df, "all") == 4
    assert _count_cancel_rows(df, "buy") == 2
    assert _count_cancel_rows(df, "sell") == 1
    # 空表（text2df 失败/无委托）不报错
    assert _count_cancel_rows(pd.DataFrame(), "buy") == 0


def test_order_cancel_by_contract_result():
    # 正常构造（cancelled_quantity 为 Int，必填）
    r = OrderCancelByContractResult(
        contract_no="1234567890",
        stock_code="600000",
        cancelled_quantity=100,
    )
    assert r.contract_no == "1234567890"
    assert r.stock_code == "600000"
    assert r.cancelled_quantity == 100

    # 不可撤时 cancelled_quantity=0
    r0 = OrderCancelByContractResult(
        contract_no="x", stock_code="600000", cancelled_quantity=0
    )
    assert r0.cancelled_quantity == 0

    # cancelled_quantity 接受 None（Int validator）
    r_none = OrderCancelByContractResult(
        contract_no="x", stock_code="600000", cancelled_quantity=None
    )
    assert r_none.cancelled_quantity is None

    # 严格模型：未知字段报错
    with pytest.raises(ValueError):
        OrderCancelByContractResult(
            contract_no="x",
            stock_code="600000",
            cancelled_quantity=100,
            extra=1,
        )
