"""
easyths 客户端模块

提供与 easyths 服务端的通信接口，支持远程调用交易操作。

所有方法返回统一的响应信封（与服务端 REST / MCP 一致）::

    {
        "success": bool | None,     # 操作类方法的业务结果；快照类可能为 None
        "status": str | None,       # queued / running / completed / failed / cancelled
        "message": str,             # 错误信息或成功消息
        "error_code": str | None,   # invalid_params / not_connected / client_rejected /
                                    # ui_error / cancelled / timeout / not_found / internal /
                                    # unauthorized / forbidden / rate_limited
        "current_used_account": str | None,  # 操作执行时的当前使用账户（未确认过为 None）
        "data": Any,                # 业务数据（查询类为记录列表）
        "timestamp": str            # 北京时间，格式 "2026-08-22 06:46:56"
    }
"""

from typing import Any, Literal, TypedDict

import httpx

# ==================== 异常类 ====================


class TradeClientError(Exception):
    """客户端异常"""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


# ==================== 类型定义 ====================


class APIResponse(TypedDict):
    """统一响应信封格式"""

    success: bool | None
    status: str | None
    message: str
    error_code: str | None
    current_used_account: str | None
    data: Any
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
        >>> if result["success"]:
        ...     print(result["message"])
        >>>
        >>> # 查询持仓
        >>> result = client.query_holdings()
        >>> if result["success"]:
        ...     holdings = result["data"]
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
        scheme: str = "http",
    ):
        self.host = host
        self.port = port
        self.api_key = api_key
        self.timeout = timeout
        self.scheme = scheme
        self._base_url = f"{scheme}://{host}:{port}"
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.Client(base_url=self._base_url, timeout=self.timeout)
        return self._client

    def _request(self, method: str, path: str, **kwargs: Any) -> APIResponse:
        """发送 HTTP 请求

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
                f"API 请求失败: {e.response.text}", status_code=e.response.status_code
            ) from e
        except httpx.TimeoutException as e:
            raise TradeClientError(f"请求超时: {e}") from e

    # ==================== 系统管理 ====================

    def health_check(self) -> APIResponse:
        """健康检查（真实探活：连接标志 + 同花顺进程存活）"""
        return self._request("GET", "/api/v1/system/health")

    def get_system_status(self) -> APIResponse:
        """获取系统详细状态（含插件清单与参数 schema）"""
        return self._request("GET", "/api/v1/system/status")

    def reconnect(self) -> APIResponse:
        """重连同花顺（客户端重启后恢复服务）"""
        return self._request("POST", "/api/v1/system/reconnect")

    def get_queue_stats(self) -> APIResponse:
        """获取队列统计信息"""
        return self._request("GET", "/api/v1/queue/stats")

    def list_operations(self) -> APIResponse:
        """获取所有可用操作（含参数 schema）"""
        return self._request("GET", "/api/v1/operations/")

    # ==================== 账户操作便捷方法 ====================

    def query_accounts(self, timeout: float | None = None) -> APIResponse:
        """查询客户端所有已登录账户，数据在 result["data"]

        字段：available_accounts 可用账户记录列表（每行 account_name 账户名 /
        account_index 账户序号）；当前使用账户在信封 current_used_account（未确认过为 None）

        Args:
            timeout: 等待操作结果的超时时间（秒）
        """
        operation_id = self.execute_operation("account_query", {})
        return self.get_operation_result(operation_id, timeout=timeout)

    def switch_account(
        self, account_name: str, timeout: float | None = None
    ) -> APIResponse:
        """切换当前交易账户，切换前账户在 data["previous_used_account"]，
        切换后账户在信封 current_used_account

        Args:
            account_name: 目标账户名（客户端展示的账户标识）
        """
        operation_id = self.execute_operation(
            "account_switch", {"account_name": account_name}
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    # ==================== 通用操作方法 ====================

    def execute_operation(
        self,
        operation_name: str,
        params: dict[str, Any] | None = None,
        priority: int = 0,
        account_name: str | None = None,
    ) -> str:
        """执行操作（提交到队列，立即返回操作 ID）

        Args:
            operation_name: 操作名称
            params: 操作参数（非法参数提交时即抛出 TradeClientError，422）
            priority: 优先级（0-10），数字越大优先级越高
            account_name: 执行前切换到该账户（不指定则用当前账户）；
                account_switch 的同名业务参数优先，此时指令不生效

        Returns:
            操作 ID
        """
        data: dict[str, Any] = {**(params or {}), "priority": priority}
        if account_name is not None and "account_name" not in data:
            data["account_name"] = account_name
        result = self._request(
            "POST", f"/api/v1/operations/{operation_name}", json=data
        )
        return result["data"]["operation_id"]

    def get_operation_status(self, operation_id: str) -> APIResponse:
        """获取操作状态快照（非阻塞，未终态时 success 为 None）"""
        return self._request("GET", f"/api/v1/operations/{operation_id}/status")

    def get_operation_result(
        self, operation_id: str, timeout: float | None = None
    ) -> APIResponse:
        """获取操作结果（阻塞等待直到操作完成）

        Args:
            operation_id: 操作 ID
            timeout: 超时时间（秒），None 表示使用客户端默认超时时间

        Raises:
            TradeClientError: 操作超时（408）、操作不存在（404）或其他错误
        """
        params = {}
        if timeout is not None:
            params["timeout"] = timeout

        try:
            return self._request(
                "GET", f"/api/v1/operations/{operation_id}/result", params=params
            )
        except TradeClientError as e:
            if e.status_code == 408:
                raise TradeClientError(
                    f"操作 {operation_id} 等待超时，仍在执行中，请勿重复提交",
                    status_code=408,
                ) from e
            if e.status_code == 404:
                raise TradeClientError(
                    f"操作 {operation_id} 不存在或结果已过期",
                    status_code=404,
                ) from e
            raise

    def cancel_operation(self, operation_id: str) -> bool:
        """取消排队中的操作"""
        self._request("DELETE", f"/api/v1/operations/{operation_id}")
        return True

    # ==================== 交易操作便捷方法 ====================

    def buy(
        self,
        stock_code: str,
        price: float,
        quantity: int,
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """买入股票

        Args:
            stock_code: 股票代码（6位数字）
            price: 买入价格
            quantity: 买入数量（股票必须是100的倍数，可转债必须是10的倍数）
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）

        Examples:
            >>> result = client.buy("600000", 10.50, 100)
            >>> if result["success"]:
            ...     print(result["message"])
        """
        operation_id = self.execute_operation(
            "buy",
            {"stock_code": stock_code, "price": price, "quantity": quantity},
            account_name=account_name,
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def market_buy(
        self,
        stock_code: str,
        quantity: int,
        execution_strategy: Literal[1, 2, 3, 4, 5, 6] = 3,
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """市价买入股票，无需指定价格，通过成交策略决定成交方式。

        注意：并不是所有类型的标的都支持市价交易；若请求策略不被该标的支持，
        系统会自动改用「五档即成剩撤」提交。

        Args:
            stock_code: 股票代码（6位数字）
            quantity: 买入数量（股票必须是100的倍数，可转债必须是10的倍数）
            execution_strategy: 成交策略（1-6），默认 3（五档即成剩撤）
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        operation_id = self.execute_operation(
            "market_buy",
            {
                "stock_code": stock_code,
                "quantity": quantity,
                "execution_strategy": execution_strategy,
            },
            account_name=account_name,
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def market_sell(
        self,
        stock_code: str,
        quantity: int,
        execution_strategy: Literal[1, 2, 3, 4, 5, 6] = 3,
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """市价卖出股票，参数与返回同 market_buy"""
        operation_id = self.execute_operation(
            "market_sell",
            {
                "stock_code": stock_code,
                "quantity": quantity,
                "execution_strategy": execution_strategy,
            },
            account_name=account_name,
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def sell(
        self,
        stock_code: str,
        price: float,
        quantity: int,
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """卖出股票

        Args:
            stock_code: 股票代码（6位数字）
            price: 卖出价格
            quantity: 卖出数量（股票必须是100的倍数，可转债必须是10的倍数）
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        operation_id = self.execute_operation(
            "sell",
            {"stock_code": stock_code, "price": price, "quantity": quantity},
            account_name=account_name,
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def cancel_order(
        self,
        stock_code: str | None = None,
        cancel_type: Literal["all", "buy", "sell"] = "all",
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """撤销委托单

        Args:
            stock_code: 股票代码，不指定则撤销所有委托
            cancel_type: 撤单类型，"all" 全部, "buy" 买单, "sell" 卖单
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        params: dict[str, Any] = {"cancel_type": cancel_type}
        if stock_code:
            params["stock_code"] = stock_code
        operation_id = self.execute_operation(
            "order_cancel", params, account_name=account_name
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def condition_buy(
        self,
        stock_code: str,
        target_price: float,
        quantity: int,
        expire_days: int = 30,
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """条件买入股票（股价达到触发价自动买入）

        Args:
            stock_code: 股票代码（6位数字）
            target_price: 目标触发价格
            quantity: 买入数量（股票必须是100的倍数，可转债必须是10的倍数）
            expire_days: 有效期（自然日），可选1/3/5/10/20/30，默认30
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        operation_id = self.execute_operation(
            "condition_buy",
            {
                "stock_code": stock_code,
                "target_price": target_price,
                "quantity": quantity,
                "expire_days": expire_days,
            },
            account_name=account_name,
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def condition_sell(
        self,
        stock_code: str,
        target_price: float,
        quantity: int,
        expire_days: int = 30,
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """条件卖出股票（股价达到触发价自动卖出），参数同 condition_buy"""
        operation_id = self.execute_operation(
            "condition_sell",
            {
                "stock_code": stock_code,
                "target_price": target_price,
                "quantity": quantity,
                "expire_days": expire_days,
            },
            account_name=account_name,
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def stop_loss_profit(
        self,
        stock_code: str,
        stop_loss_percent: float,
        stop_profit_percent: float,
        quantity: int | None = None,
        expire_days: int = 30,
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """设置止盈止损

        Args:
            stock_code: 股票代码（6位数字）
            stop_loss_percent: 止损百分比（如3表示3%）
            stop_profit_percent: 止盈百分比（如5表示5%）
            quantity: 卖出数量，可选，不指定则使用全部可卖持仓
            expire_days: 有效期（自然日），可选1/3/5/10/20/30，默认30
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        params: dict[str, Any] = {
            "stock_code": stock_code,
            "stop_loss_percent": stop_loss_percent,
            "stop_profit_percent": stop_profit_percent,
            "expire_days": expire_days,
        }
        if quantity is not None:
            params["quantity"] = quantity
        operation_id = self.execute_operation(
            "stop_loss_profit", params, account_name=account_name
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    # ==================== 查询操作便捷方法 ====================

    def query_holdings(
        self, timeout: float | None = None, account_name: str | None = None
    ) -> APIResponse:
        """查询持仓，持仓数据在 result["data"]（记录列表）

        字段：stock_code, stock_name, quantity, available_quantity, frozen_quantity,
        cost_price, current_price, floating_profit, profit_ratio, daily_profit,
        daily_profit_ratio, market_value, position_ratio, daily_bought, daily_sold, market

        Args:
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        operation_id = self.execute_operation(
            "holding_query", {}, account_name=account_name
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def query_funds(
        self, timeout: float | None = None, account_name: str | None = None
    ) -> APIResponse:
        """查询资金，数据在 result["data"]（单位元，数值型）

        字段：balance 资金余额, frozen_amount 冻结金额, market_value 股票市值,
        total_assets 总资产, available_amount 可用金额, withdrawable_amount 可取金额,
        holding_profit 持仓盈亏

        Args:
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        operation_id = self.execute_operation(
            "funds_query", {}, account_name=account_name
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def query_orders(
        self,
        stock_code: str | None = None,
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """查询委托单，委托数据在 result["data"]（记录列表）

        字段：order_time, stock_code, stock_name, operation(买入/卖出), remark,
        quantity, filled_quantity, price, avg_fill_price, cancelled_quantity,
        contract_no, market

        Args:
            stock_code: 股票代码，不指定则查询所有委托
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        params: dict[str, Any] = {}
        if stock_code:
            params["stock_code"] = stock_code
        operation_id = self.execute_operation(
            "order_query", params, account_name=account_name
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def query_historical_commission(
        self,
        stock_code: str | None = None,
        time_range: Literal["当日", "近一周", "近一月", "近三月", "近一年"] = "当日",
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """查询历史委托，数据在 result["data"]（记录列表），字段同 query_orders 另加 order_date

        Args:
            stock_code: 股票代码（6位数字），不指定则查询所有股票
            time_range: 查询时间范围，默认"当日"
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        params: dict[str, Any] = {"time_range": time_range}
        if stock_code is not None:
            params["stock_code"] = stock_code
        operation_id = self.execute_operation(
            "historical_commission_query", params, account_name=account_name
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def reverse_repo_buy(
        self,
        market: Literal["上海", "深圳"],
        time_range: Literal["1天期", "2天期", "3天期", "4天期", "7天期"],
        amount: int,
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """购买国债逆回购

        Args:
            market: 交易市场，"上海" 或 "深圳"
            time_range: 回购期限，"1天期"/"2天期"/"3天期"/"4天期"/"7天期"
            amount: 出借金额（必须是1000的倍数）
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        operation_id = self.execute_operation(
            "reverse_repo_buy",
            {"market": market, "time_range": time_range, "amount": amount},
            account_name=account_name,
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def query_reverse_repo(
        self, timeout: float | None = None, account_name: str | None = None
    ) -> APIResponse:
        """查询国债逆回购年化利率，数据在 result["data"]（记录列表）

        字段：market(上海/深圳), term 期限, annual_rate 年化利率（百分数值，如 2.5 表示 2.5%）

        Args:
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        operation_id = self.execute_operation(
            "reverse_repo_query", {}, account_name=account_name
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def query_condition_orders(
        self, timeout: float | None = None, account_name: str | None = None
    ) -> APIResponse:
        """查询条件单，数据在 result["data"]（记录列表）

        字段：status, condition_type, direction(买入/卖出), target, trigger_condition,
        latest_price, change_ratio, order_detail, created_at, monitor_cycle

        Args:
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        operation_id = self.execute_operation(
            "condition_order_query", {}, account_name=account_name
        )
        return self.get_operation_result(operation_id, timeout=timeout)

    def cancel_condition_orders(
        self,
        stock_code: str | None = None,
        order_type: Literal["买入", "卖出"] | None = None,
        timeout: float | None = None,
        account_name: str | None = None,
    ) -> APIResponse:
        """删除条件单

        Args:
            stock_code: 股票代码（6位数字），不指定则删除所有条件单
            order_type: 订单类型，"买入" 或 "卖出"
            timeout: 等待操作结果的超时时间（秒）
            account_name: 执行前切换到该账户（不指定则用当前账户）
        """
        params: dict[str, Any] = {}
        if stock_code is not None:
            params["stock_code"] = stock_code
        if order_type is not None:
            params["order_type"] = order_type
        operation_id = self.execute_operation(
            "condition_order_cancel", params, account_name=account_name
        )
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
