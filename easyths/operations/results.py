"""操作结果模型：全部业务结果契约集中于此。

每个操作的 ``Result`` 模型是结果契约的唯一来源：字段定义生成接口文档
（/operations/ 列表的 result_schema），数值字段兼容客户端文本格式
（千分位逗号、百分号、全角空格），``--`` 等占位值统一转换为 null。

表格行模型只声明英文 snake_case 字段；「剪贴板中文记录 → 行模型」的
装配在各操作类的显式解析函数中完成（如 ``parse_holding_row``），
便于处理实盘/模拟账户的列名差异等适配逻辑。
"""

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from easyths.operations.params import ExpireDays, Market, RepoTerm


def _parse_num(value: object) -> float | None:
    """客户端数值文本转 float：千分位逗号/百分号/全角空格，占位值返回 None"""
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    text = str(value).replace(",", "").replace("\xa0", "").replace("%", "").strip()
    if text in {"", "--", "-"}:
        return None
    return float(text)


def _parse_int(value: object) -> int | None:
    """客户端整数文本转 int（复用数值解析，占位值返回 None）"""
    parsed = _parse_num(value)
    return int(parsed) if parsed is not None else None


def _parse_text(value: object) -> str:
    """客户端文本：去全角空格与首尾空白"""
    return str(value).replace("\xa0", " ").strip()


#: 可空数值字段（客户端文本自动转换，单位遵循字段 description）
Num = Annotated[float | None, BeforeValidator(_parse_num)]

#: 可空整数字段
Int = Annotated[int | None, BeforeValidator(_parse_int)]

#: 文本字段（自动清洗）
Text = Annotated[str, BeforeValidator(_parse_text)]


class ResultModel(BaseModel):
    """结果模型基类：字段即契约，英文 snake_case"""

    model_config = ConfigDict(extra="forbid")


# ============ 提交受理 ============


class SubmitResult(ResultModel):
    """操作提交受理结果"""

    operation_id: str = Field(description="操作 ID，用于查询状态/结果")
    queue_position: int = Field(description="当前排队数（不含本操作）")


# ============ 交易类结果 ============


class LimitOrderResult(ResultModel):
    """限价委托提交结果（buy / sell）"""

    stock_code: Text = Field(description="股票代码（6位数字）")
    price: float = Field(description="委托价格（元）")
    quantity: int = Field(description="委托数量（股）")


class MarketOrderResult(ResultModel):
    """市价委托提交结果（market_buy / market_sell）"""

    stock_code: Text = Field(description="股票代码（6位数字）")
    quantity: int = Field(description="委托数量（股）")
    strategy: Text = Field(
        description="实际使用的成交策略名称（请求策略不支持时为兜底策略）"
    )


class ConditionOrderResult(ResultModel):
    """条件单创建结果（condition_buy / condition_sell）"""

    stock_code: Text = Field(description="股票代码（6位数字）")
    target_price: float = Field(description="触发价格（元）")
    quantity: int = Field(description="委托数量（股）")
    expire_days: ExpireDays = Field(description="策略有效期（自然日）")


class StopLossResult(ResultModel):
    """止盈止损单创建结果"""

    stock_code: Text = Field(description="股票代码（6位数字）")
    stop_loss_percent: float = Field(description="止损百分比（如 3 表示 3%）")
    stop_profit_percent: float = Field(description="止盈百分比（如 5 表示 5%）")
    quantity: int = Field(description="委托数量（股），未指定时为全部可卖持仓")
    expire_days: ExpireDays = Field(description="策略有效期（自然日）")


class OrderCancelResult(ResultModel):
    """撤单结果"""

    stock_code: Text | None = Field(description="目标股票代码，null 表示全部委托")
    cancel_type: Literal["all", "buy", "sell"] = Field(
        description="撤单类型：all-全部 buy-买入 sell-卖出"
    )
    cancelled_count: int = Field(description="撤销的委托笔数")


class ConditionOrderCancelResult(ResultModel):
    """条件单删除结果"""

    stock_code: Text | None = Field(description="目标股票代码，null 表示全部条件单")
    order_type: Literal["买入", "卖出"] | None = Field(
        description="订单类型，null 表示不限"
    )
    deleted_count: int = Field(description="删除的条件单数量")


class ReverseRepoBuyResult(ResultModel):
    """国债逆回购出借结果"""

    market: Market = Field(description="交易市场")
    time_range: RepoTerm = Field(description="回购期限")
    amount: int = Field(description="出借金额（元）")
    annual_rate: Num = Field(description="成交年化利率（百分数值，如 2.5 表示 2.5%）")


# ============ 账户类结果 ============


class AccountRow(ResultModel):
    """账户行（account_query）：账户名 + 客户端列表序号"""

    account_name: Text = Field(
        description="账户名（客户端下拉列表的完整展示名，如 平安证券-王*明）"
    )
    account_index: int = Field(description="账户序号（客户端列表位置）")


class AccountsResult(ResultModel):
    """账户列表结果（account_query）；当前使用账户在信封 current_used_account"""

    available_accounts: list[AccountRow] = Field(description="客户端全部可用账户记录")


class AccountSwitchResult(ResultModel):
    """账户切换结果（account_switch）；切换后账户在信封 current_used_account"""

    previous_used_account: Text | None = Field(
        description="切换前使用的账户（此前未确认过为 null）"
    )


# ============ 查询类结果 ============


class FundsResult(ResultModel):
    """账户资金信息（单位：元，数值型；无该项业务时为 null）"""

    balance: Num = Field(description="资金余额")
    frozen_amount: Num = Field(description="冻结金额")
    market_value: Num = Field(description="股票市值")
    total_assets: Num = Field(description="总资产")
    available_amount: Num = Field(description="可用金额")
    withdrawable_amount: Num = Field(description="可取金额")
    holding_profit: Num = Field(description="持仓盈亏")
    daily_profit: Num = Field(
        default=None, description="当日盈亏；客户端版本无该控件时为 null"
    )
    daily_profit_ratio: Num = Field(
        default=None, description="当日盈亏比（%）；客户端版本无该控件时为 null"
    )


class ReverseRepoQuote(ResultModel):
    """单个期限的国债逆回购利率行情"""

    market: Market = Field(description="交易市场")
    term: Text = Field(description="期限（如 1天期）")
    annual_rate: Num = Field(description="年化利率（百分数值，如 2.5 表示 2.5%）")


# ============ 表格行模型（装配见各操作类的显式解析函数） ============


class HoldingRow(ResultModel):
    """持仓行（holding_query）"""

    stock_code: Text = Field(description="证券代码")
    stock_name: Text = Field(description="证券名称")
    quantity: Int = Field(description="持仓数量（股）")
    available_quantity: Int = Field(description="可用数量（股）")
    frozen_quantity: Int = Field(description="冻结数量（股）")
    cost_price: Num = Field(description="参考成本价（元）")
    current_price: Num = Field(description="当前价（元）")
    floating_profit: Num = Field(description="浮动盈亏（元）")
    profit_ratio: Num = Field(description="盈亏比例（%，如 1.76 表示 1.76%）")
    daily_profit: Num = Field(default=None, description="当日盈亏（元）")
    daily_profit_ratio: Num = Field(default=None, description="当日盈亏比（%）")
    market_value: Num = Field(description="最新市值（元）")
    position_ratio: Num = Field(description="仓位占比（%）")
    daily_bought: Int = Field(description="当日买入（股）")
    daily_sold: Int = Field(description="当日卖出（股）")
    market: Text = Field(description="交易市场")


class OrderRow(ResultModel):
    """委托行（order_query）"""

    order_time: Text = Field(description="委托时间")
    stock_code: Text = Field(description="证券代码")
    stock_name: Text = Field(description="证券名称")
    operation: Text = Field(description="操作（委托方向：买入/卖出）")
    remark: Text = Field(description="备注")
    quantity: Int = Field(description="委托数量（股）")
    filled_quantity: Int = Field(description="成交数量（股）")
    price: Num = Field(description="委托价格（元）")
    avg_fill_price: Num = Field(description="成交均价（元）")
    cancelled_quantity: Int = Field(description="撤销数量（股）")
    contract_no: Text = Field(description="合同编号")
    market: Text = Field(description="交易市场")


class HistoricalOrderRow(OrderRow):
    """历史委托行（historical_commission_query）：比当日委托多委托日期"""

    order_date: Text = Field(description="委托日期")


class ConditionOrderRow(ResultModel):
    """条件单行（condition_order_query，未触发页签）"""

    status: Text = Field(description="状态")
    condition_type: Text = Field(description="条件类型")
    direction: Text = Field(description="方向（买入/卖出）")
    target: Text = Field(description="监控标的")
    trigger_condition: Text = Field(description="触发条件")
    latest_price: Num = Field(description="最新价（元）")
    change_ratio: Num = Field(description="涨幅（%，如 1.23 表示 1.23%）")
    order_detail: Text = Field(description="委托单")
    created_at: Text = Field(description="创建时间")
    monitor_cycle: Text = Field(description="监控周期")


__all__ = [
    "AccountRow",
    "AccountSwitchResult",
    "AccountsResult",
    "ConditionOrderCancelResult",
    "ConditionOrderResult",
    "ConditionOrderRow",
    "FundsResult",
    "HistoricalOrderRow",
    "HoldingRow",
    "Int",
    "LimitOrderResult",
    "MarketOrderResult",
    "Num",
    "OrderCancelResult",
    "OrderRow",
    "ResultModel",
    "ReverseRepoBuyResult",
    "ReverseRepoQuote",
    "StopLossResult",
    "SubmitResult",
    "Text",
]
