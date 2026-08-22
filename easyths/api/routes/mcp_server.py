"""MCP 服务器路由 - 显式定义每个交易操作工具

Author: noimank
Email: noimank@163.com
"""

from typing import Literal, cast

from fastmcp import FastMCP
from structlog import get_logger

from easyths.models.operations import Operation
from easyths.utils import project_config_instance

logger = get_logger(__name__)

# MCP 工具等待操作完成的超时时间（秒）
_OPERATION_TIMEOUT = 30.0

# 创建 MCP 服务器实例
mcp_server = FastMCP(
    name="EasyTHS Trading Server",
    instructions="同花顺交易自动化系统 - 提供 MCP 协议接口",
)

# 全局存储队列引用
_operation_queue = None


def set_queue(queue) -> None:
    """设置操作队列引用"""
    global _operation_queue
    _operation_queue = queue


def _execute_operation(operation_name: str, params: dict) -> dict:
    """提交操作并等待终态结果，返回统一信封形状（与 REST 一致）

    超时时明确区分「操作仍在执行」与「记录已失效」，避免调用方误判后重复下单。
    """
    if _operation_queue is None:
        return {
            "success": False,
            "status": None,
            "error_code": "internal",
            "message": "操作队列未初始化",
        }

    operation = Operation(name=operation_name, params=params, priority=0)
    operation_id = _operation_queue.submit(operation)

    result = _operation_queue.get_result(operation_id, timeout=_OPERATION_TIMEOUT)
    if result is None:
        state = _operation_queue.get_state(operation_id)
        if state is None:
            return {
                "success": False,
                "status": None,
                "error_code": "timeout",
                "message": "等待操作结果超时，且操作记录已失效",
                "operation_id": operation_id,
            }
        return {
            "success": False,
            "status": state.status.value,
            "error_code": "timeout",
            "message": f"等待超时，操作仍在{state.status.value}，请勿重复提交，可稍后重查",
            "operation_id": operation_id,
        }

    response = result.model_dump(mode="json")
    response["operation_id"] = operation_id
    return response


# ============= 交易操作工具 =============


@mcp_server.tool
def buy(stock_code: str, price: float, quantity: int) -> dict:
    """买入股票

    Args:
        stock_code: 股票代码（6位数字）
        price: 买入价格
        quantity: 买入数量（股票必须是100的倍数，可转债必须是10的倍数）

    Returns:
        买入结果
    """
    return _execute_operation(
        "buy", {"stock_code": stock_code, "price": price, "quantity": quantity}
    )


@mcp_server.tool
def sell(stock_code: str, price: float, quantity: int) -> dict:
    """卖出股票

    Args:
        stock_code: 股票代码（6位数字）
        price: 卖出价格
        quantity: 卖出数量（股票必须是100的倍数，可转债必须是10的倍数）

    Returns:
        卖出结果
    """
    return _execute_operation(
        "sell", {"stock_code": stock_code, "price": price, "quantity": quantity}
    )


@mcp_server.tool
def market_buy(stock_code: str, quantity: int, execution_strategy: int = 3) -> dict:
    """市价买入股票，无需指定价格，通过成交策略决定成交方式。
    注意：并不是所有类型的标的都支持市价交易；若请求策略不被该标的支持，
    系统会自动改用「五档即成剩撤」提交。

    Args:
        stock_code: 股票代码（6位数字）
        quantity: 买入数量（股票必须是100的倍数，可转债必须是10的倍数）
        execution_strategy: 成交策略编号（1-6），默认3：1-对手方最优 2-本方最优 3-五档即成剩撤 4-即成剩撤 5-全额成交或撤 6-五档即成剩转限

    Returns:
        市价买入结果
    """
    return _execute_operation(
        "market_buy",
        {
            "stock_code": stock_code,
            "quantity": quantity,
            "execution_strategy": execution_strategy,
        },
    )


@mcp_server.tool
def market_sell(stock_code: str, quantity: int, execution_strategy: int = 3) -> dict:
    """市价卖出股票，无需指定价格，通过成交策略决定成交方式。
    注意：并不是所有类型的标的都支持市价交易；若请求策略不被该标的支持，
    系统会自动改用「五档即成剩撤」提交。

    Args:
        stock_code: 股票代码（6位数字）
        quantity: 卖出数量（股票必须是100的倍数，可转债必须是10的倍数）
        execution_strategy: 成交策略编号（1-6），默认3：1-对手方最优 2-本方最优 3-五档即成剩撤 4-即成剩撤 5-全额成交或撤 6-五档即成剩转限

    Returns:
        市价卖出结果
    """
    return _execute_operation(
        "market_sell",
        {
            "stock_code": stock_code,
            "quantity": quantity,
            "execution_strategy": execution_strategy,
        },
    )


# ============= 查询操作工具 =============


@mcp_server.tool
def holding_query() -> dict:
    """查询股票持仓信息

    Returns:
        持仓记录列表，字段：stock_code, stock_name, quantity, available_quantity,
        frozen_quantity, cost_price, current_price, floating_profit, profit_ratio,
        daily_profit, daily_profit_ratio, market_value, position_ratio,
        daily_bought, daily_sold, market（数值型，无该项业务时为 null）
    """
    return _execute_operation("holding_query", {})


@mcp_server.tool
def funds_query() -> dict:
    """查询账户资金信息

    Returns:
        资金信息（单位元，数值型）：balance 资金余额, frozen_amount 冻结金额,
        market_value 股票市值, total_assets 总资产, available_amount 可用金额,
        withdrawable_amount 可取金额, holding_profit 持仓盈亏
    """
    return _execute_operation("funds_query", {})


@mcp_server.tool
def order_query(stock_code: str | None = None) -> dict:
    """查询股票委托订单信息

    Args:
        stock_code: 股票代码（6位数字），不指定则查询所有股票的委托

    Returns:
        委托记录列表，字段：order_time, stock_code, stock_name, operation(买入/卖出),
        remark, quantity, filled_quantity, price, avg_fill_price, cancelled_quantity,
        contract_no, market（数值型，无该项业务时为 null）
    """
    params = {}
    if stock_code:
        params["stock_code"] = stock_code
    return _execute_operation("order_query", params)


@mcp_server.tool
def historical_commission_query(
    stock_code: str | None = None, time_range: str = "当日"
) -> dict:
    """查询股票历史委托订单信息

    Args:
        stock_code: 股票代码（6位数字），不指定则查询所有股票的历史委托
        time_range: 查询时间范围，可选值: 当日, 近一周, 近一月, 近三月, 近一年

    Returns:
        历史委托记录列表，字段同 order_query，另加 order_date 委托日期
    """
    params = {"time_range": time_range}
    if stock_code:
        params["stock_code"] = stock_code
    return _execute_operation("historical_commission_query", params)


# ============= 委托管理工具 =============


@mcp_server.tool
def order_cancel(stock_code: str | None = None, cancel_type: str = "all") -> dict:
    """撤销委托订单

    Args:
        stock_code: 股票代码（6位数字），不指定则撤销所有待成交委托
        cancel_type: 撤单类型，可选值: all(全部), sell(卖出), buy(买入)

    Returns:
        撤单结果：stock_code, cancel_type, cancelled_count 撤销笔数
    """
    params = {"cancel_type": cancel_type}
    if stock_code:
        params["stock_code"] = stock_code
    return _execute_operation("order_cancel", params)


# ============= 条件单工具 =============


@mcp_server.tool
def condition_buy(
    stock_code: str, target_price: float, quantity: int, expire_days: int = 30
) -> dict:
    """条件买入股票

    当股价达到目标价格时自动买入

    Args:
        stock_code: 股票代码（6位数字）
        target_price: 目标触发价格
        quantity: 买入数量（股票必须是100的倍数，可转债必须是10的倍数）
        expire_days: 策略有效期（天），可选值: 1, 3, 5, 10, 20, 30

    Returns:
        条件单创建结果
    """
    return _execute_operation(
        "condition_buy",
        {
            "stock_code": stock_code,
            "target_price": target_price,
            "quantity": quantity,
            "expire_days": expire_days,
        },
    )


@mcp_server.tool
def condition_sell(
    stock_code: str, target_price: float, quantity: int, expire_days: int = 30
) -> dict:
    """条件卖出股票

    当股价达到目标价格时自动卖出

    Args:
        stock_code: 股票代码（6位数字）
        target_price: 目标触发价格
        quantity: 卖出数量（股票必须是100的倍数，可转债必须是10的倍数）
        expire_days: 策略有效期（天），可选值: 1, 3, 5, 10, 20, 30

    Returns:
        条件单创建结果
    """
    return _execute_operation(
        "condition_sell",
        {
            "stock_code": stock_code,
            "target_price": target_price,
            "quantity": quantity,
            "expire_days": expire_days,
        },
    )


@mcp_server.tool
def condition_order_query() -> dict:
    """查询条件单信息

    Returns:
        条件单记录列表，字段：status, condition_type, direction(买入/卖出), target,
        trigger_condition, latest_price, change_ratio, order_detail, created_at,
        monitor_cycle（数值型，无该项业务时为 null）
    """
    return _execute_operation("condition_order_query", {})


@mcp_server.tool
def condition_order_cancel(
    stock_code: str | None = None, order_type: str | None = None
) -> dict:
    """删除条件单

    Args:
        stock_code: 股票代码（6位数字），不指定则删除所有条件单
        order_type: 订单类型，可选值: 买入, 卖出

    Returns:
        删除结果：stock_code, order_type, deleted_count 删除数量
    """
    params = {}
    if stock_code:
        params["stock_code"] = stock_code
    if order_type:
        params["order_type"] = order_type
    return _execute_operation("condition_order_cancel", params)


# ============= 止损止盈工具 =============


@mcp_server.tool
def stop_loss_profit(
    stock_code: str,
    stop_loss_percent: float,
    stop_profit_percent: float,
    quantity: int | None = None,
    expire_days: int = 30,
) -> dict:
    """设置止损止盈

    Args:
        stock_code: 股票代码（6位数字）
        stop_loss_percent: 止损百分比（如3表示3%）
        stop_profit_percent: 止盈百分比（如5表示5%）
        quantity: 卖出数量（股票必须是100的倍数，可转债必须是10的倍数），不指定则使用全部持仓
        expire_days: 策略有效期（天），可选值: 1, 3, 5, 10, 20, 30

    Returns:
        设置结果
    """
    params = {
        "stock_code": stock_code,
        "stop_loss_percent": stop_loss_percent,
        "stop_profit_percent": stop_profit_percent,
        "expire_days": expire_days,
    }
    if quantity:
        params["quantity"] = quantity
    return _execute_operation("stop_loss_profit", params)


# ============= 国债逆回购工具 =============


@mcp_server.tool
def reverse_repo_buy(market: str, time_range: str, amount: int) -> dict:
    """国债逆回购（出借资金）

    Args:
        market: 交易市场，可选值: 上海, 深圳
        time_range: 回购期限，可选值: 1天期, 2天期, 3天期, 4天期, 7天期
        amount: 出借金额（必须是1000的倍数）

    Returns:
        逆回购结果：market, time_range, amount, annual_rate 成交年化利率（百分数值）
    """
    return _execute_operation(
        "reverse_repo_buy",
        {"market": market, "time_range": time_range, "amount": amount},
    )


@mcp_server.tool
def reverse_repo_query() -> dict:
    """查询国债逆回购年化利率

    Returns:
        各期限利率行情列表，字段：market(上海/深圳), term 期限, annual_rate 年化利率（百分数值）
    """
    return _execute_operation("reverse_repo_query", {})


# 创建 ASGI 应用用于挂载
# 从配置文件读取传输类型，支持: http, streamable-http, sse
# 使用明确的路径 /mcp-server
_mcp_transport = project_config_instance.api_mcp_server_type
if _mcp_transport not in ("http", "streamable-http", "sse"):
    raise ValueError(f"不支持的 MCP 传输类型: {_mcp_transport}")
logger.info(f"MCP 服务器传输类型: {_mcp_transport}")
mcp_asgi_app = mcp_server.http_app(
    path="/mcp-server",
    transport=cast(Literal["http", "streamable-http", "sse"], _mcp_transport),
)
