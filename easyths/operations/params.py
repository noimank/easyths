"""操作参数模型：全部业务参数契约集中于此。

每个操作的 ``Params`` 模型是参数校验的唯一来源：
REST 提交时校验（未知/非法参数直接 422），队列执行时复用校验，
接口文档（/operations/ 列表与 OpenAPI schema）由模型自动生成。
"""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from easyths.models.operations import EmptyParams, OperationParams
from easyths.utils.execution_strategy import DEFAULT_STRATEGY

# ============ 公共构件 ============

StockCode = Annotated[str, Field(pattern=r"^\d{6}$", description="股票代码（6位数字）")]

#: 策略/条件单有效期（自然日），客户端仅支持这些档位
ExpireDays = Literal[1, 3, 5, 10, 20, 30]

#: 交易市场
Market = Literal["上海", "深圳"]

#: 国债逆回购期限
RepoTerm = Literal["1天期", "2天期", "3天期", "4天期", "7天期"]

#: 单笔委托金额上限（元）
MAX_ORDER_AMOUNT = 10_000_000


def format_price(stock_code: str, price: float) -> str:
    """按标的类型格式化价格文本。

    ETF/可转债（5/1 开头）支持 3 位小数，其余标的 2 位
    https://github.com/noimank/easyths/issues/6
    """
    return f"{price:.3f}" if stock_code.startswith(("5", "1")) else f"{price:.2f}"


def _lot_error(stock_code: str, quantity: int) -> str | None:
    """股/债手数规则：可转债（11/12 开头）10 股起且 10 的倍数，其余 100 起且 100 的倍数"""
    is_convertible = stock_code.startswith(("11", "12"))
    multiple = 10 if is_convertible else 100
    if quantity < multiple or quantity % multiple != 0:
        return f"数量必须是{multiple}的倍数且不小于{multiple}" + (
            "（可转债）" if is_convertible else "（股票）"
        )
    return None


class LotSizeParams(OperationParams):
    """股票代码 + 数量，含手数规则校验"""

    stock_code: StockCode
    quantity: Annotated[
        int,
        Field(gt=0, description="数量（股票必须是100的倍数，可转债必须是10的倍数）"),
    ]

    @model_validator(mode="after")
    def _check_lot_size(self) -> "LotSizeParams":
        if error := _lot_error(self.stock_code, self.quantity):
            raise ValueError(error)
        return self


class LimitOrderParams(LotSizeParams):
    """限价委托参数（买入/卖出共用）"""

    price: Annotated[float, Field(gt=0, le=10000, description="委托价格")]

    @model_validator(mode="after")
    def _check_amount(self) -> "LimitOrderParams":
        if self.price * self.quantity > MAX_ORDER_AMOUNT:
            raise ValueError(f"单笔委托金额超过{MAX_ORDER_AMOUNT}元上限")
        return self


class MarketOrderParams(LotSizeParams):
    """市价委托参数（买入/卖出共用）"""

    execution_strategy: Annotated[
        int,
        Field(
            ge=1,
            le=6,
            description="成交策略：1-对手方最优 2-本方最优 3-五档即成剩撤 4-即成剩撤 5-全额成交或撤 6-五档即成剩转限",
        ),
    ] = DEFAULT_STRATEGY


class ConditionOrderParams(LotSizeParams):
    """条件单参数（买入/卖出共用）"""

    target_price: Annotated[float, Field(gt=0, le=10000, description="触发价格")]
    expire_days: Annotated[ExpireDays, Field(description="策略有效期（自然日）")] = 30

    @model_validator(mode="after")
    def _check_amount(self) -> "ConditionOrderParams":
        if self.target_price * self.quantity > MAX_ORDER_AMOUNT:
            raise ValueError(f"单笔委托金额超过{MAX_ORDER_AMOUNT}元上限")
        return self


class StopLossParams(OperationParams):
    """止盈止损参数"""

    stock_code: StockCode
    stop_loss_percent: Annotated[
        float, Field(gt=0, le=100, description="止损百分比（如3表示3%）")
    ]
    stop_profit_percent: Annotated[
        float, Field(gt=0, le=100, description="止盈百分比（如5表示5%）")
    ]
    quantity: Annotated[
        int | None,
        Field(default=None, gt=0, description="卖出数量，不指定则使用全部可卖持仓"),
    ] = None
    expire_days: Annotated[ExpireDays, Field(description="策略有效期（自然日）")] = 30

    @model_validator(mode="after")
    def _check_lot_size(self) -> "StopLossParams":
        if self.quantity is not None and (
            error := _lot_error(self.stock_code, self.quantity)
        ):
            raise ValueError(error)
        return self


class OrderCancelParams(OperationParams):
    """撤单参数"""

    stock_code: StockCode | None = Field(
        default=None, description="股票代码，不指定则针对全部委托"
    )
    cancel_type: Literal["all", "buy", "sell"] = Field(
        default="all", description="撤单类型：all-全部 sell-卖单 buy-买单"
    )


class ConditionOrderCancelParams(OperationParams):
    """条件单删除参数"""

    stock_code: StockCode | None = Field(
        default=None, description="股票代码，不指定则删除全部条件单"
    )
    order_type: Literal["买入", "卖出"] | None = Field(
        default=None, description="订单类型，不指定则不限"
    )


class StockQueryParams(OperationParams):
    """按标的过滤的查询参数"""

    stock_code: StockCode | None = Field(
        default=None, description="股票代码，不指定则查询全部"
    )


class HistoricalQueryParams(StockQueryParams):
    """历史委托查询参数"""

    time_range: Literal["当日", "近一周", "近一月", "近三月", "近一年"] = Field(
        default="当日", description="查询时间范围"
    )


class AccountSwitchParams(OperationParams):
    """账户切换参数"""

    account_name: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "目标账户名（客户端下拉列表的完整展示名，如 平安证券-王*明，"
                "取值见 account_query 返回）"
            ),
        ),
    ]


class ReverseRepoBuyParams(OperationParams):
    """国债逆回购参数"""

    market: Market = Field(description="交易市场")
    time_range: RepoTerm = Field(description="回购期限")
    amount: Annotated[int, Field(gt=0, description="出借金额（必须是1000的倍数）")]

    @model_validator(mode="after")
    def _check_amount_unit(self) -> "ReverseRepoBuyParams":
        if self.amount % 1000 != 0:
            raise ValueError("出借金额必须是1000的倍数")
        return self


__all__ = [
    "AccountSwitchParams",
    "ConditionOrderCancelParams",
    "ConditionOrderParams",
    "EmptyParams",
    "ExpireDays",
    "HistoricalQueryParams",
    "LimitOrderParams",
    "Market",
    "MarketOrderParams",
    "MAX_ORDER_AMOUNT",
    "OrderCancelParams",
    "ReverseRepoBuyParams",
    "RepoTerm",
    "StockCode",
    "StockQueryParams",
    "StopLossParams",
    "format_price",
]
