"""
easyths 客户端模块

提供与 easyths 服务端的通信接口，支持远程调用交易操作。
"""
from typing import Any, Dict, Optional, Literal, TypedDict

import httpx


# ==================== 异常类 ====================

class TradeClientError(Exception):
    """客户端异常"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


# ==================== 类型定义 ====================

class APIResponse(TypedDict):
    """API 响应格式"""
    success: bool
    message: str
    data: Any
    error: Optional[str]
    timestamp: str


# ==================== 客户端类 ====================

class TradeClient:
    """
    easyths 交易客户端

    用于与 easyths 服务端进行通信，执行各种交易操作。

    Args:
        host: 服务端主机地址，默认为 "127.0.0.1"
        port: 服务端端口，默认为 7648
        api_key: API 密钥，用于身份验证
        timeout: 请求超时时间（秒），默认为 30
        scheme: 协议方案，http 或 https，默认为 http

    Examples:
        >>> # 基本使用
        >>> client = TradeClient(host="127.0.0.1", port=7648, api_key="your-api-key")
        >>> client.health_check()
        >>>
        >>> # 买入股票
        >>> result = client.buy("600000", 10.50, 100)
        >>> print(result["data"]["result"]["data"]["message"])
        >>>
        >>> # 查询持仓
        >>> result = client.query_holdings()
        >>> holdings = result["data"]["result"]["data"]["holdings"]
        >>>
        >>> # 使用上下文管理器
        >>> with TradeClient(...) as client:
        ...     client.buy("600000", 10.50, 100)
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7648,
        api_key: str = "",
        timeout: float = 30.0,
        scheme: str = "http"
    ):
        self.host = host
        self.port = port
        self.api_key = api_key
        self.timeout = timeout
        self.scheme = scheme
        self._base_url = f"{scheme}://{host}:{port}"
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                timeout=self.timeout
            )
        return self._client

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any
    ) -> APIResponse:
        """
        发送 HTTP 请求

        Args:
            method: HTTP 方法
            path: 请求路径
            **kwargs: 其他请求参数

        Returns:
            响应数据

        Raises:
            TradeClientError: 请求失败
        """
        client = self._get_client()

        # 添加 Bearer Token 认证头
        if self.api_key:
            headers = kwargs.get("headers", {})
            headers["Authorization"] = f"Bearer {self.api_key}"
            kwargs["headers"] = headers

        try:
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            raise TradeClientError(f"连接服务端失败: {e}") from e
        except httpx.HTTPStatusError as e:
            raise TradeClientError(
                f"API 请求失败: {e.response.text}",
                status_code=e.response.status_code
            ) from e
        except httpx.TimeoutException as e:
            raise TradeClientError(f"请求超时: {e}") from e

    # ==================== 系统管理 ====================

    def health_check(self) -> APIResponse:
        """
        健康检查

        Returns:
            健康检查结果，包含系统状态信息
        """
        return self._request("GET", "/api/v1/system/health")

    def get_system_status(self) -> APIResponse:
        """
        获取系统详细状态

        Returns:
            系统状态信息
        """
        return self._request("GET", "/api/v1/system/status")

    def get_system_info(self) -> APIResponse:
        """
        获取系统信息

        Returns:
            系统信息
        """
        return self._request("GET", "/api/v1/system/info")

    def get_queue_stats(self) -> APIResponse:
        """
        获取队列统计信息

        Returns:
            队列统计信息
        """
        return self._request("GET", "/api/v1/queue/stats")

    def list_operations(self) -> APIResponse:
        """
        获取所有可用操作

        Returns:
            可用操作列表
        """
        return self._request("GET", "/api/v1/operations/")

    # ==================== 通用操作方法 ====================

    def execute_operation(
        self,
        operation_name: str,
        params: Optional[Dict[str, Any]] = None,
        priority: int = 0
    ) -> str:
        """
        执行操作

        Args:
            operation_name: 操作名称
            params: 操作参数
            priority: 优先级（0-10），数字越大优先级越高

        Returns:
            操作 ID
        """
        data: Dict[str, Any] = {"params": params or {}, "priority": priority}
        result = self._request("POST", f"/api/v1/operations/{operation_name}", json=data)
        return result["data"]["operation_id"]

    def get_operation_status(
        self,
        operation_id: str
    ) -> APIResponse:
        """
        获取操作状态

        Args:
            operation_id: 操作 ID

        Returns:
            操作状态信息
        """
        return self._request("GET", f"/api/v1/operations/{operation_id}/status")

    def get_operation_result(
        self,
        operation_id: str,
        timeout: Optional[float] = None
    ) -> APIResponse:
        """
        获取操作结果（阻塞等待直到操作完成）

        Args:
            operation_id: 操作 ID
            timeout: 超时时间（秒），None 表示使用客户端默认超时时间

        Returns:
            操作结果，包含 success、message、data 等字段

        Raises:
            TradeClientError: 操作超时或其他错误

        Examples:
            >>> result = client.get_operation_result(op_id)
            >>> if result["data"]["result"]["success"]:
            ...     print("操作成功:", result["data"]["result"]["data"])
        """
        params = {}
        if timeout is not None:
            params["timeout"] = timeout

        try:
            return self._request("GET", f"/api/v1/operations/{operation_id}/result", params=params)
        except TradeClientError as e:
            if e.status_code == 408:
                raise TradeClientError(f"操作 {operation_id} 超时", status_code=408) from e
            raise

    def cancel_operation(self, operation_id: str) -> bool:
        """
        取消操作

        Args:
            operation_id: 操作 ID

        Returns:
            是否成功取消
        """
        self._request("DELETE", f"/api/v1/operations/{operation_id}")
        return True

    # ==================== 交易操作便捷方法 ====================

    def buy(
        self,
        stock_code: str,
        price: float,
        quantity: int,
        timeout: float = 60.0
    ) -> APIResponse:
        """
        买入股票

        Args:
            stock_code: 股票代码（6位数字）
            price: 买入价格
            quantity: 买入数量（必须是100的倍数）
            timeout: 操作超时时间（秒）

        Returns:
            操作结果，格式为：
            {
                "success": True,
                "message": "查询成功",
                "data": {
                    "operation_id": "...",
                    "result": {
                        "success": bool,
                        "data": {...},  # 业务数据
                        "error": None,
                        "timestamp": str
                    }
                },
                "error": None,
                "timestamp": str
            }

        Raises:
            TradeClientError: 连接失败、API 错误或操作超时

        Examples:
            >>> client = TradeClient(...)
            >>> result = client.buy("600000", 10.50, 100)
            >>> if result["data"]["result"]["success"]:
            ...     print(result["data"]["result"]["data"]["message"])
        """
        params = {
            "stock_code": stock_code,
            "price": price,
            "quantity": quantity
        }
        operation_id = self.execute_operation("buy", params)
        return self.get_operation_result(operation_id, timeout=timeout)

    def sell(
        self,
        stock_code: str,
        price: float,
        quantity: int,
        timeout: float = 60.0
    ) -> APIResponse:
        """
        卖出股票

        Args:
            stock_code: 股票代码（6位数字）
            price: 卖出价格
            quantity: 卖出数量（必须是100的倍数）
            timeout: 操作超时时间（秒）

        Returns:
            操作结果，格式与 buy() 相同

        Examples:
            >>> result = client.sell("600000", 11.00, 100)
            >>> print(result["data"]["result"]["data"]["message"])
        """
        params = {
            "stock_code": stock_code,
            "price": price,
            "quantity": quantity
        }
        operation_id = self.execute_operation("sell", params)
        return self.get_operation_result(operation_id, timeout=timeout)

    def cancel_order(
        self,
        stock_code: Optional[str] = None,
        cancel_type: Literal["all", "buy", "sell"] = "all",
        timeout: float = 60.0
    ) -> APIResponse:
        """
        撤销委托单

        Args:
            stock_code: 股票代码，不指定则撤销所有委托
            cancel_type: 撤单类型，"all" 全部, "buy" 买单, "sell" 卖单
            timeout: 操作超时时间（秒）

        Returns:
            操作结果

        Examples:
            >>> # 撤销所有委托
            >>> result = client.cancel_order()
            >>>
            >>> # 撤销指定股票的委托
            >>> result = client.cancel_order("600000")
            >>>
            >>> # 只撤销买单
            >>> result = client.cancel_order(cancel_type="buy")
        """
        params: Dict[str, Any] = {"cancel_type": cancel_type}
        if stock_code:
            params["stock_code"] = stock_code

        operation_id = self.execute_operation("order_cancel", params)
        return self.get_operation_result(operation_id, timeout=timeout)

    def condition_buy(
        self,
        stock_code: str,
        target_price: float,
        quantity: int,
        expire_days: int = 30,
        timeout: float = 60.0
    ) -> APIResponse:
        """
        条件买入股票

        设置条件买入单，当股价达到目标价格时自动触发买入。

        Args:
            stock_code: 股票代码（6位数字）
            target_price: 目标价格（触发价格）
            quantity: 买入数量（必须是100的倍数）
            expire_days: 有效期（自然日），可选1/3/5/10/20/30，默认30
            timeout: 操作超时时间（秒）

        Returns:
            操作结果，格式为：
            {
                "success": True,
                "message": "查询成功",
                "data": {
                    "operation_id": "...",
                    "result": {
                        "success": bool,
                        "data": {...},  # 业务数据
                        "error": None,
                        "timestamp": str
                    }
                },
                "error": None,
                "timestamp": str
            }

        Raises:
            TradeClientError: 连接失败、API 错误或操作超时

        Examples:
            >>> client = TradeClient(...)
            >>> result = client.condition_buy("600000", 10.50, 100, expire_days=30)
            >>> if result["data"]["result"]["success"]:
            ...     print(result["data"]["result"]["data"]["message"])
        """
        params = {
            "stock_code": stock_code,
            "target_price": target_price,
            "quantity": quantity,
            "expire_days": expire_days
        }
        operation_id = self.execute_operation("condition_buy", params)
        return self.get_operation_result(operation_id, timeout=timeout)

    def stop_loss_profit(
        self,
        stock_code: str,
        stop_loss_percent: float,
        stop_profit_percent: float,
        quantity: Optional[int] = None,
        expire_days: int = 30,
        timeout: float = 60.0
    ) -> APIResponse:
        """
        设置止盈止损

        为持仓股票设置止盈止损策略，当价格达到止盈或止损条件时自动触发卖出。

        Args:
            stock_code: 股票代码（6位数字）
            stop_loss_percent: 止损百分比（如3表示3%）
            stop_profit_percent: 止盈百分比（如5表示5%）
            quantity: 卖出数量（必须是100的倍数），可选，不指定则使用全部可用持仓
            expire_days: 有效期（自然日），可选1/3/5/10/20/30，默认30
            timeout: 操作超时时间（秒）

        Returns:
            操作结果，格式与 condition_buy() 相同

        Raises:
            TradeClientError: 连接失败、API 错误或操作超时

        Examples:
            >>> # 设置止盈止损
            >>> result = client.stop_loss_profit("600000", 3.0, 5.0, quantity=100)
            >>> print(result["data"]["result"]["data"]["message"])
        """
        params = {
            "stock_code": stock_code,
            "stop_loss_percent": stop_loss_percent,
            "stop_profit_percent": stop_profit_percent,
            "expire_days": expire_days
        }
        if quantity is not None:
            params["quantity"] = quantity

        operation_id = self.execute_operation("stop_loss_profit", params)
        return self.get_operation_result(operation_id, timeout=timeout)

    def query_condition_orders(
        self,
        return_type: Literal["str", "json", "dict", "df", "markdown"] = "json",
        timeout: float = 30.0
    ) -> APIResponse:
        """
        查询条件单

        Args:
            return_type: 结果返回类型
                - "str": 字符串格式
                - "json": JSON 格式（默认）
                - "dict": 字典格式
                - "df": pandas DataFrame
                - "markdown": Markdown 表格
            timeout: 操作超时时间（秒）

        Returns:
            操作结果，格式为：
            {
                "success": True,
                "message": "查询成功",
                "data": {
                    "operation_id": "...",
                    "result": {
                        "success": bool,
                        "data": {...},  # 业务数据
                        "error": None,
                        "timestamp": str
                    }
                },
                "error": None,
                "timestamp": str
            }

        Raises:
            TradeClientError: 连接失败、API 错误或操作超时

        Examples:
            >>> client = TradeClient(...)
            >>> result = client.query_condition_orders()
            >>> if result["data"]["result"]["success"]:
            ...     orders = result["data"]["result"]["data"]["condition_orders"]
            ...     print(orders)
        """
        params = {"return_type": return_type}
        operation_id = self.execute_operation("condition_order_query", params)
        return self.get_operation_result(operation_id, timeout=timeout)

    def cancel_condition_orders(
        self,
        stock_code: Optional[str] = None,
        order_type: Optional[Literal["买入", "卖出"]] = None,
        timeout: float = 60.0
    ) -> APIResponse:
        """
        删除条件单

        Args:
            stock_code: 股票代码（6位数字），不指定则删除所有条件单
            order_type: 订单类型，"买入" 或 "卖出"
            timeout: 操作超时时间（秒）

        Returns:
            操作结果，格式与 query_condition_orders() 相同

        Raises:
            TradeClientError: 连接失败、API 错误或操作超时

        Examples:
            >>> # 删除所有条件单
            >>> result = client.cancel_condition_orders()
            >>>
            >>> # 删除指定股票的条件单
            >>> result = client.cancel_condition_orders(stock_code="600000")
            >>>
            >>> # 只删除买入条件单
            >>> result = client.cancel_condition_orders(order_type="买入")
        """
        params: Dict[str, Any] = {}
        if stock_code is not None:
            params["stock_code"] = stock_code
        if order_type is not None:
            params["order_type"] = order_type

        operation_id = self.execute_operation("condition_order_cancel", params)
        return self.get_operation_result(operation_id, timeout=timeout)

    # ==================== 查询操作便捷方法 ====================

    def query_holdings(
        self,
        return_type: Literal["str", "json", "dict", "df", "markdown"] = "json",
        timeout: float = 30.0
    ) -> APIResponse:
        """
        查询持仓

        Args:
            return_type: 结果返回类型
                - "str": 字符串格式
                - "json": JSON 格式（默认）
                - "dict": 字典格式
                - "df": pandas DataFrame
                - "markdown": Markdown 表格
            timeout: 操作超时时间（秒）

        Returns:
            操作结果，持仓数据在 result["data"]["result"]["data"]["holdings"]

        Examples:
            >>> result = client.query_holdings()
            >>> holdings = result["data"]["result"]["data"]["holdings"]
        """
        params = {"return_type": return_type}
        operation_id = self.execute_operation("holding_query", params)
        return self.get_operation_result(operation_id, timeout=timeout)

    def query_funds(
        self,
        timeout: float = 30.0
    ) -> APIResponse:
        """
        查询资金

        Returns:
            操作结果，资金数据在 result["data"]["result"]["data"]
            包含：资金余额、冻结金额、可用金额、可取金额、股票市值、总资产、持仓盈亏

        Examples:
            >>> result = client.query_funds()
            >>> funds = result["data"]["result"]["data"]
            >>> print(funds["总资产"])
        """
        operation_id = self.execute_operation("funds_query", {})
        return self.get_operation_result(operation_id, timeout=timeout)

    def query_orders(
        self,
        stock_code: Optional[str] = None,
        return_type: Literal["str", "json", "dict", "df", "markdown"] = "json",
        timeout: float = 30.0
    ) -> APIResponse:
        """
        查询委托单

        Args:
            stock_code: 股票代码，不指定则查询所有委托
            return_type: 结果返回类型
            timeout: 操作超时时间（秒）

        Returns:
            操作结果，委托单数据在 result["data"]["result"]["data"]["orders"]

        Examples:
            >>> # 查询所有委托
            >>> result = client.query_orders()
            >>> orders = result["data"]["result"]["data"]["orders"]
            >>>
            >>> # 查询指定股票的委托
            >>> result = client.query_orders("600000")
        """
        params: Dict[str, Any] = {"return_type": return_type}
        if stock_code:
            params["stock_code"] = stock_code

        operation_id = self.execute_operation("order_query", params)
        return self.get_operation_result(operation_id, timeout=timeout)

    def query_historical_commission(
        self,
        return_type: Literal["str", "json", "dict", "df", "markdown"] = "json",
        timeout: float = 30.0
    ) -> APIResponse:
        """
        查询历史成交

        Args:
            return_type: 结果返回类型
            timeout: 操作超时时间（秒）

        Returns:
            操作结果，历史成交数据在 result["data"]["result"]["data"]

        Examples:
            >>> result = client.query_historical_commission()
        """
        params = {"return_type": return_type}
        operation_id = self.execute_operation("historical_commission_query", params)
        return self.get_operation_result(operation_id, timeout=timeout)

    def reverse_repo_buy(
        self,
        market: Literal["上海", "深圳"],
        time_range: Literal["1天期", "2天期", "3天期", "4天期", "7天期"],
        amount: int,
        timeout: float = 60.0
    ) -> APIResponse:
        """
        购买国债逆回购

        Args:
            market: 交易市场，"上海" 或 "深圳"
            time_range: 回购期限，"1天期"/"2天期"/"3天期"/"4天期"/"7天期"
            amount: 出借金额（必须是1000的倍数）
            timeout: 操作超时时间（秒）

        Returns:
            操作结果

        Examples:
            >>> # 购买上海市场1天期国债逆回购，出借10000元
            >>> result = client.reverse_repo_buy("上海", "1天期", 10000)
            >>> if result["data"]["result"]["success"]:
            ...     print(result["data"]["result"]["data"]["message"])
        """
        params = {
            "market": market,
            "time_range": time_range,
            "amount": amount
        }
        operation_id = self.execute_operation("reverse_repo_buy", params)
        return self.get_operation_result(operation_id, timeout=timeout)

    def query_reverse_repo(
        self,
        timeout: float = 30.0
    ) -> APIResponse:
        """
        查询国债逆回购年化利率

        Args:
            timeout: 操作超时时间（秒）

        Returns:
            操作结果，年化利率数据在 result["data"]["result"]["data"]["reverse_repo_interest"]

        Examples:
            >>> result = client.query_reverse_repo()
            >>> if result["data"]["result"]["success"]:
            ...     rates = result["data"]["result"]["data"]["reverse_repo_interest"]
            ...     for item in rates:
            ...         print(f"{item['市场类型']} - {item['时间类型']}: {item['年化利率']}")
        """
        operation_id = self.execute_operation("reverse_repo_query", {})
        return self.get_operation_result(operation_id, timeout=timeout)

    # ==================== 连接管理 ====================

    def close(self):
        """关闭客户端连接"""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时关闭连接"""
        self.close()

    def __del__(self):
        """析构时确保连接关闭"""
        self.close()
