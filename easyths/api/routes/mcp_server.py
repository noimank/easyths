"""MCP 服务器路由 - 显式定义每个交易操作工具

Author: noimank
Email: noimank@163.com
"""
from typing import Optional

from fastmcp import FastMCP
from structlog import get_logger

from easyths.utils import project_config_instance

logger = get_logger(__name__)

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
    """执行操作的辅助函数

    Args:
        operation_name: 操作名称
        params: 操作参数

    Returns:
        执行结果字典
    """
    from easyths.models.operations import Operation

    if _operation_queue is None:
        return {
            "success": False,
            "error": "操作队列未初始化",
        }

    # 创建操作对象
    operation = Operation(
        name=operation_name,
        params=params,
        priority=0
    )

    # 提交操作到队列
    operation_id = _operation_queue.submit(operation)

    # 等待操作完成
    result = _operation_queue.get_result(operation_id, timeout=30.0)

    if result is None:
        return {
            "success": False,
            "error": "操作超时或未完成",
            "operation_id": operation_id
        }

    return {
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "operation_id": operation_id
    }


# ============= 交易操作工具 =============

@mcp_server.tool
def buy(stock_code: str, price: float, quantity: int) -> dict:
    """买入股票

    Args:
        stock_code: 股票代码（6位数字）
        price: 买入价格
        quantity: 买入数量（必须是100的倍数）

    Returns:
        买入结果
    """
    return _execute_operation("buy", {
        "stock_code": stock_code,
        "price": price,
        "quantity": quantity
    })


@mcp_server.tool
def sell(stock_code: str, price: float, quantity: int) -> dict:
    """卖出股票

    Args:
        stock_code: 股票代码（6位数字）
        price: 卖出价格
        quantity: 卖出数量（必须是100的倍数）

    Returns:
        卖出结果
    """
    return _execute_operation("sell", {
        "stock_code": stock_code,
        "price": price,
        "quantity": quantity
    })


# ============= 查询操作工具 =============

@mcp_server.tool
def holding_query(return_type: str = "json") -> dict:
    """查询股票持仓信息

    Args:
        return_type: 结果返回类型，可选值: str, json, dict, df, markdown

    Returns:
        持仓信息
    """
    return _execute_operation("holding_query", {
        "return_type": return_type
    })


@mcp_server.tool
def funds_query() -> dict:
    """查询账户资金信息

    Returns:
        资金信息，包含资金余额、可用金额、总资产等
    """
    return _execute_operation("funds_query", {})


@mcp_server.tool
def order_query(return_type: str, stock_code: Optional[str] = None) -> dict:
    """查询股票委托订单信息

    Args:
        return_type: 结果返回类型，可选值: str, json, dict, df, markdown
        stock_code: 股票代码（6位数字），不指定则查询所有股票的委托

    Returns:
        委托订单信息
    """
    params = {"return_type": return_type}
    if stock_code:
        params["stock_code"] = stock_code
    return _execute_operation("order_query", params)


@mcp_server.tool
def historical_commission_query(
    return_type: str,
    stock_code: Optional[str] = None,
    time_range: str = "当日"
) -> dict:
    """查询股票历史委托订单信息

    Args:
        return_type: 结果返回类型，可选值: str, json, dict, df, markdown
        stock_code: 股票代码（6位数字），不指定则查询所有股票的历史委托
        time_range: 查询时间范围，可选值: 当日, 近一周, 近一月, 近三月, 近一年

    Returns:
        历史委托订单信息
    """
    params = {"return_type": return_type, "time_range": time_range}
    if stock_code:
        params["stock_code"] = stock_code
    return _execute_operation("historical_commission_query", params)


# ============= 委托管理工具 =============

@mcp_server.tool
def order_cancel(
    stock_code: Optional[str] = None,
    cancel_type: str = "all"
) -> dict:
    """撤销委托订单

    Args:
        stock_code: 股票代码（6位数字），不指定则撤销所有待成交委托
        cancel_type: 撤单类型，可选值: all(全部), sell(卖出), buy(买入)

    Returns:
        撤单结果
    """
    params = {"cancel_type": cancel_type}
    if stock_code:
        params["stock_code"] = stock_code
    return _execute_operation("order_cancel", params)


# ============= 条件单工具 =============

@mcp_server.tool
def condition_buy(
    stock_code: str,
    target_price: float,
    quantity: int,
    expire_days: int = 30
) -> dict:
    """条件买入股票

    当股价达到目标价格时自动买入

    Args:
        stock_code: 股票代码（6位数字）
        target_price: 目标触发价格
        quantity: 买入数量（必须是100的倍数）
        expire_days: 策略有效期（天），可选值: 1, 3, 5, 10, 20, 30

    Returns:
        条件单创建结果
    """
    return _execute_operation("condition_buy", {
        "stock_code": stock_code,
        "target_price": target_price,
        "quantity": quantity,
        "expire_days": expire_days
    })


@mcp_server.tool
def condition_order_query(return_type: str = "json") -> dict:
    """查询条件单信息

    Args:
        return_type: 结果返回类型，可选值: str, json, dict, df, markdown

    Returns:
        条件单信息
    """
    return _execute_operation("condition_order_query", {
        "return_type": return_type
    })


@mcp_server.tool
def condition_order_cancel(
    stock_code: Optional[str] = None,
    order_type: Optional[str] = None
) -> dict:
    """删除条件单

    Args:
        stock_code: 股票代码（6位数字），不指定则删除所有条件单
        order_type: 订单类型，可选值: 买入, 卖出

    Returns:
        删除结果
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
    quantity: Optional[int] = None,
    expire_days: int = 30
) -> dict:
    """设置止损止盈

    Args:
        stock_code: 股票代码（6位数字）
        stop_loss_percent: 止损百分比（如3表示3%）
        stop_profit_percent: 止盈百分比（如5表示5%）
        quantity: 卖出数量（必须是100的倍数），不指定则使用全部持仓
        expire_days: 策略有效期（天），可选值: 1, 3, 5, 10, 20, 30

    Returns:
        设置结果
    """
    params = {
        "stock_code": stock_code,
        "stop_loss_percent": stop_loss_percent,
        "stop_profit_percent": stop_profit_percent,
        "expire_days": expire_days
    }
    if quantity:
        params["quantity"] = quantity
    return _execute_operation("stop_loss_profit", params)


# ============= 国债逆回购工具 =============

@mcp_server.tool
def reverse_repo_buy(
    market: str,
    time_range: str,
    amount: int
) -> dict:
    """国债逆回购（出借资金）

    Args:
        market: 交易市场，可选值: 上海, 深圳
        time_range: 回购期限，可选值: 1天期, 2天期, 3天期, 4天期, 7天期
        amount: 出借金额（必须是1000的倍数）

    Returns:
        逆回购结果
    """
    return _execute_operation("reverse_repo_buy", {
        "market": market,
        "time_range": time_range,
        "amount": amount
    })


@mcp_server.tool
def reverse_repo_query() -> dict:
    """查询国债逆回购年化利率

    Returns:
        各期限国债逆回购年化利率信息
    """
    return _execute_operation("reverse_repo_query", {})


# 创建 ASGI 应用用于挂载
# 从配置文件读取传输类型，支持: http, streamable-http, sse
# 使用明确的路径 /mcp-server
_mcp_transport = project_config_instance.api_mcp_server_type
logger.info(f"MCP 服务器传输类型: {_mcp_transport}")
mcp_asgi_app = mcp_server.http_app(path="/mcp-server", transport=_mcp_transport)
