# Client SDK

EasyTHS 提供了官方的 Python Client SDK（`TradeClient`），用于与服务端进行通信，执行各种交易操作。

## 安装

Client SDK 包含在 `easyths` 包中。根据您的使用场景，可以选择以下两种安装方式：

### 仅安装客户端 SDK（推荐用于远程调用）

如果您只需要使用 `TradeClient` 连接到已运行的服务端，可以仅安装基础包：

```bash
# 使用 pip 安装（推荐）
pip install easyths

# 或使用 uv
uv add easyths
```

**客户端模式仅依赖少量跨平台库**：

- `httpx` - HTTP 客户端
- `pydantic` - 数据验证
- `numpy` / `tzdata` 等基础依赖

### 安装完整服务端（包含客户端）

如果您需要在本地运行完整的服务端（包括自动化交易功能），需要安装服务端版本：

```bash
# 使用 pip 安装（推荐）
pip install easyths[server]

# 或使用 uv
uv add easyths[server]
```

**完整服务端包含**：

- 所有客户端依赖
- FastAPI 服务端
- pywinauto（Windows GUI 自动化）
- 其他服务端依赖（OCR、图像处理等）

> **注意**：完整服务端仅支持 Windows 系统。客户端 SDK 可以在任何系统上运行。

## 快速开始

### 基本用法

```python
from easyths import TradeClient

# 创建客户端
client = TradeClient(
    host="127.0.0.1",
    port=7648,
    api_key="your-api-key"  # 如果配置了 API Key
)

# 健康检查
health = client.health_check()
print(health)

# 使用完毕后关闭连接
client.close()
```

### 使用上下文管理器（推荐）

```python
from easyths import TradeClient

# 使用 with 语句自动管理连接
with TradeClient(host="127.0.0.1", port=7648, api_key="your-api-key") as client:
    health = client.health_check()
    print(health)
# 连接会自动关闭
```

---

## 初始化参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| host | str | "127.0.0.1" | 服务端主机地址 |
| port | int | 7648 | 服务端端口 |
| api_key | str | "" | API 密钥（用于身份验证） |
| timeout | float | 30.0 | 请求超时时间（秒） |
| scheme | str | "http" | 协议方案（http/https） |

---

## 系统管理

### 健康检查

```python
health = client.health_check()
# 返回: {"success": True, "message": "系统运行正常", "data": {...}}
```

### 获取系统状态

```python
status = client.get_system_status()
# 返回: {"success": True, "data": {"automator": {...}, "plugins": {...}}}
```

### 重连同花顺

同花顺客户端重启后，无需重启服务即可恢复连接：

```python
res = client.reconnect()
# 返回: {"success": True, "message": "同花顺重连成功"}
```

### 获取队列统计

```python
stats = client.get_queue_stats()
# 返回: {"success": True, "data": {"queued_count": 0, ...}}
```

### 获取可用操作列表

```python
ops = client.list_operations()
# 返回: {"success": True, "data": {"operations": {...}, "count": 19}}
# operations 内每个操作含 name / description / parameters / result_schema
```

---

## 多账户支持

客户端登录了多个账户时，**交易/查询方法均接受可选的
`account_name` 参数**（默认 `None` 用当前账户；`query_accounts()` 无此参数，
`switch_account()` 的 `account_name` 是切换目标本身而非指令）。两种用法的语义不同，务必区分：

> `account_name` 的取值为客户端账户下拉列表的**完整展示名**（仅去除首尾
> 空白，如「平安证券-王\*明」），完整列表以 `query_accounts()` 返回为准。

**显式传入 `account_name`（推荐）——操作必然落在该账户**

服务端在执行操作前先切换到目标账户，切换与操作在同一个队列槽内**原子完成**，
其他调用方的操作不会插入其间。因此操作必然落在指定账户上；切换失败时
操作以 `failed` + `执行前账户切换失败: ...` 收尾，不会落到其他账户执行。

```python
# 必然落在「模拟账户」上
result = client.buy("600000", 10.50, 100, account_name="模拟账户")
result = client.query_funds(account_name="实盘账户")

# 终态结果携带 current_used_account，可核对实际落在的账户
assert result["current_used_account"] == "实盘账户"
```

**先 `switch_account()` 再调用不指定 `account_name` 的方法——默认当前账户**

切换与后续操作是两个独立队列项，期间任何调用方都可能把当前账户切走。
不指定 `account_name` 的操作落在**执行时刻的当前账户**，不一定是先前切换
的账户。仅适合确认同一时刻只有单一调用方使用的场景。

> 单账户使用可完全忽略：不传 `account_name` 即可，行为与之前版本一致。

## 账户操作

### 查询账户列表

```python
result = client.query_accounts()

if result["success"]:
    # 当前使用账户在信封（未确认过为 None），不在 data 中
    print(f"当前使用账户: {result['current_used_account']}")
    for account in result["data"]["available_accounts"]:
        print(f"- {account['account_name']}（序号 {account['account_index']}）")
```

### 切换账户

幂等操作：已处于目标账户时重复切换无副作用。

```python
result = client.switch_account("模拟账户")

if result["success"]:
    data = result["data"]
    # 切换前账户在 data，切换后账户在信封
    print(f"已从 {data['previous_used_account']} 切换至 {result['current_used_account']}")
```

> `switch_account` 的 `account_name` 是切换目标（业务参数）。切换后想让后续
> 操作稳定落在该账户，请给后续操作显式传 `account_name`，而不是依赖
> 「先切换再调用」。

---

## 交易操作

### 买入股票

```python
result = client.buy(
    stock_code="600000",  # 股票代码
    price=10.50,          # 买入价格
    quantity=100          # 买入数量（股票100的倍数，可转债10的倍数）
)

# 检查结果
if result["success"]:
    data = result["data"]
    print(f"买入成功: {result['message']}")
    print(f"委托: {data['stock_code']} {data['quantity']}股 @ {data['price']}")
else:
    print(f"买入失败: {result['message']}（错误码: {result['error_code']}）")
```

### 卖出股票

```python
result = client.sell(
    stock_code="600000",
    price=11.00,
    quantity=100
)

if result["success"]:
    print("卖出成功")
```

### 市价买入

以市价方式买入股票，无需指定价格，通过成交策略决定成交方式。

```python
result = client.market_buy(
    stock_code="600000",       # 股票代码
    quantity=100,              # 买入数量（100的倍数）
    execution_strategy=3       # 成交策略（可选，默认3-五档即成剩撤）
)

if result["success"]:
    print(f"市价买入成功: {result['message']}")
else:
    print(f"市价买入失败: {result['message']}")
```

**成交策略**:

| 值 | 策略名称 |
|----|----------|
| 1 | 对手方最优 |
| 2 | 本方最优 |
| 3 | 五档即成剩撤（默认） |
| 4 | 即成剩撤 |
| 5 | 全额成交或撤 |
| 6 | 五档即成剩转限 |

> **注意**：并不是所有类型的标的都支持市价交易。且支持市价交易的标的，可用的成交策略也不总是有以上 6 种。如果设置了该标的不支持的成交策略，系统会自动使用默认策略「五档即成剩撤」进行提交。

### 市价卖出

以市价方式卖出股票，无需指定价格，通过成交策略决定成交方式。

```python
result = client.market_sell(
    stock_code="600000",       # 股票代码
    quantity=100,              # 卖出数量（100的倍数）
    execution_strategy=3       # 成交策略（可选，默认3-五档即成剩撤）
)

if result["success"]:
    print(f"市价卖出成功: {result['message']}")
else:
    print(f"市价卖出失败: {result['message']}")
```

> **注意**：同市价买入，并不是所有类型的标的都支持市价交易，且可用成交策略数量因标的而异。如果设置了不支持的策略，系统会自动使用「五档即成剩撤」进行提交。

### 撤销委托单

```python
# 撤销所有委托
result = client.cancel_order()

# 撤销指定股票的委托
result = client.cancel_order(stock_code="600000")

# 只撤销买单
result = client.cancel_order(cancel_type="buy")

# 只撤销卖单
result = client.cancel_order(cancel_type="sell")
```

### 条件买入

设置条件买入单，当股价达到目标价格时自动触发买入。

```python
result = client.condition_buy(
    stock_code="600000",      # 股票代码
    target_price=10.50,       # 目标触发价格
    quantity=100,             # 买入数量（股票100的倍数，可转债10的倍数）
    expire_days=30            # 有效期（可选1/3/5/10/20/30，默认30）
)

if result["success"]:
    data = result["data"]
    print(f"条件买入设置成功: {result['message']}")
    print(f"触发价: {data['target_price']}，有效期: {data['expire_days']}天")
else:
    print(f"条件买入设置失败: {result['message']}")
```

### 条件卖出

设置条件卖出单，当股价达到目标价格时自动触发卖出。

```python
result = client.condition_sell(
    stock_code="600000",      # 股票代码
    target_price=15.00,       # 目标触发价格
    quantity=100,             # 卖出数量（股票100的倍数，可转债10的倍数）
    expire_days=30            # 有效期（可选1/3/5/10/20/30，默认30）
)

if result["success"]:
    data = result["data"]
    print(f"条件卖出设置成功: {result['message']}")
    print(f"触发价: {data['target_price']}，有效期: {data['expire_days']}天")
else:
    print(f"条件卖出设置失败: {result['message']}")
```

### 止盈止损

为持仓股票设置止盈止损策略，当价格达到止盈或止损条件时自动触发卖出。

```python
result = client.stop_loss_profit(
    stock_code="600000",         # 股票代码
    stop_loss_percent=3.0,       # 止损百分比（如3表示3%）
    stop_profit_percent=5.0,     # 止盈百分比（如5表示5%）
    quantity=100,                # 卖出数量（可选，不指定则使用全部可用持仓）
    expire_days=30               # 有效期（可选1/3/5/10/20/30，默认30）
)

if result["success"]:
    data = result["data"]
    print(f"止盈止损设置成功: {result['message']}")
    print(f"止损{data['stop_loss_percent']}% / 止盈{data['stop_profit_percent']}%")
else:
    print(f"止盈止损设置失败: {result['message']}")
```

> **注意**：止盈百分比必须大于止损百分比。quantity 参数建议指定，因为受 T+1 限制，当天买入的股票如果不指定数量无法设置止盈止损。


### 购买国债逆回购

```python
result = client.reverse_repo_buy(
    market="上海",        # 交易市场：上海/深圳
    time_range="1天期",   # 回购期限：1天期/2天期/3天期/4天期/7天期
    amount=10000          # 出借金额（1000的倍数）
)

if result["success"]:
    rate = result["data"]["annual_rate"]  # 成交年化利率（百分数值，如 2.5 表示 2.5%）
    print(f"购买成功，年化利率: {rate}%")
else:
    error = result["message"]
    print(f"购买失败: {error}")
```


### 删除条件单

删除指定的条件单。

```python
# 删除所有条件单
result = client.cancel_condition_orders()

# 删除指定股票的条件单
result = client.cancel_condition_orders(stock_code="600000")

# 只删除买入条件单
result = client.cancel_condition_orders(order_type="买入")

# 删除指定股票的买入条件单
result = client.cancel_condition_orders(
    stock_code="600000",
    order_type="买入"
)

if result["success"]:
    count = result["data"]["deleted_count"]
    print(f"删除成功，共删除 {count} 条")
```

---

## 查询操作

### 查询持仓

```python
result = client.query_holdings()

if result["success"]:
    holdings = result["data"]  # JSON 记录列表
    for position in holdings:
        print(f"{position['stock_code']}: {position['quantity']}股")
```

### 查询资金

```python
result = client.query_funds()

if result["success"]:
    funds = result["data"]
    print(f"总资产: {funds['total_assets']}")
    print(f"可用金额: {funds['available_amount']}")
```

### 查询委托单

```python
# 查询所有委托
result = client.query_orders()

# 查询指定股票的委托
result = client.query_orders(stock_code="600000")

if result["success"]:
    orders = result["data"]  # 记录列表
    for order in orders:
        print(f"{order['stock_code']}: {order['quantity']}股 @ {order['price']}")
```

### 查询历史委托

```python
# time_range 可选: "当日"(默认)/"近一周"/"近一月"/"近三月"/"近一年"
result = client.query_historical_commission(time_range="近一月")

if result["success"]:
    commissions = result["data"]  # JSON 记录列表，字段同 query_orders 另加 order_date
    print(commissions)
```



### 查询国债逆回购年化利率

```python
result = client.query_reverse_repo()

if result["success"]:
    rates = result["data"]  # JSON 记录列表
    for item in rates:
        print(f"{item['market']} - {item['term']}: {item['annual_rate']}%")
```

### 查询条件单

查询未触发的条件单信息。

```python
result = client.query_condition_orders()

if result["success"]:
    orders = result["data"]  # JSON 记录列表
    print(orders)
```


---

## 通用操作方法

### 执行操作

```python
# 执行自定义操作
operation_id = client.execute_operation(
    operation_name="buy",
    params={
        "stock_code": "600000",
        "price": 10.50,
        "quantity": 100
    },
    priority=5,                    # 优先级 0-10，数字越大优先级越高
    account_name="模拟账户"         # 执行前切换到该账户（可选，见多账户支持）
)
print(f"操作ID: {operation_id}")
```

### 获取操作状态

```python
status = client.get_operation_status(operation_id)
print(status)
# 状态: queued/running/completed/failed/cancelled
# 未到终态时 success 为 None
```

### 获取操作结果

```python
# 阻塞等待直到操作完成
result = client.get_operation_result(
    operation_id=operation_id
)

if result["success"]:
    print("操作成功:", result["data"])
```

### 取消操作

```python
# 取消排队中的操作
success = client.cancel_operation(operation_id)
```

---

## 异常处理

SDK 提供了 `TradeClientError` 异常类，用于处理各种错误：

```python
from easyths import TradeClient, TradeClientError

try:
    with TradeClient(host="127.0.0.1", port=7648) as client:
        result = client.buy("600000", 10.50, 100)
        if result["success"]:
            print("买入成功")

except TradeClientError as e:
    print(f"交易失败: {e}")
    if e.status_code:
        print(f"状态码: {e.status_code}")
```

**常见错误状态码**：

- 连接失败：无法连接到服务端
- 401：认证失败（API Key 错误或未提供）
- 403：IP 不在服务端白名单
- 404：操作不存在或结果已被淘汰（超过 3 小时）
- 408：等待结果超时（操作仍在执行，**勿重复提交**，稍后重查）
- 422：参数校验失败（非法取值或未知字段）
- 429：触发限流，降低请求频率后重试
- 500：服务端内部错误

---

## 完整示例

### 简单交易脚本

```python
from easyths import TradeClient, TradeClientError

def simple_trade():
    """简单的交易示例"""
    with TradeClient(
        host="127.0.0.1",
        port=7648,
        api_key="your-api-key"
    ) as client:
        # 检查系统健康
        health = client.health_check()
        if not health["success"]:
            print("系统异常")
            return

        # 查询资金
        funds = client.query_funds()
        if funds["success"]:
            available = funds["data"]["available_amount"]
            print(f"可用资金: {available}")

        # 买入股票
        result = client.buy("600000", 10.50, 100)
        if result["success"]:
            print("买入成功")
        else:
            print(f"买入失败: {result['message']}")

if __name__ == "__main__":
    try:
        simple_trade()
    except TradeClientError as e:
        print(f"错误: {e}")
```

### 异步操作示例

```python
from easyths import TradeClient, TradeClientError
import time

def async_trade_example():
    """异步提交多个操作"""
    with TradeClient(host="127.0.0.1", port=7648) as client:
        operation_ids = []

        # 提交多个买入操作
        stocks = [("600000", 10.50), ("600036", 35.00), ("000001", 12.00)]
        for code, price in stocks:
            op_id = client.execute_operation(
                "buy",
                {"stock_code": code, "price": price, "quantity": 100},
                priority=5
            )
            operation_ids.append(op_id)
            print(f"已提交买入 {code}，操作ID: {op_id}")

        # 等待所有操作完成
        results = []
        for op_id in operation_ids:
            result = client.get_operation_result(op_id)
            results.append(result)

        # 处理结果
        for result in results:
            if result["success"]:
                print(f"操作成功: {result['message']}")
            else:
                print(f"操作失败: {result['message']}")
```

---

## API 参考

### TradeClient 类

```python
class TradeClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7648,
        api_key: str = "",
        timeout: float = 30.0,
        scheme: str = "http"
    ): ...

    # 系统管理
    def health_check(self) -> dict: ...
    def get_system_status(self) -> dict: ...
    def reconnect(self) -> dict: ...
    def get_queue_stats(self) -> dict: ...
    def list_operations(self) -> dict: ...

    # 通用操作
    def execute_operation(self, operation_name: str, params: dict, priority: int = 0, account_name: str = None) -> str: ...
    def get_operation_status(self, operation_id: str) -> dict: ...
    def get_operation_result(self, operation_id: str, timeout: float = None) -> dict: ...
    def cancel_operation(self, operation_id: str) -> bool: ...

    # 账户操作
    def query_accounts(self, timeout: float = None) -> dict: ...
    def switch_account(self, account_name: str, timeout: float = None) -> dict: ...

    # 交易操作（均支持可选 account_name 参数，见多账户支持）
    def buy(self, stock_code: str, price: float, quantity: int, timeout: float = None, account_name: str = None) -> dict: ...
    def sell(self, stock_code: str, price: float, quantity: int, timeout: float = None, account_name: str = None) -> dict: ...
    def market_buy(self, stock_code: str, quantity: int, execution_strategy: int = 3, timeout: float = None, account_name: str = None) -> dict: ...
    def market_sell(self, stock_code: str, quantity: int, execution_strategy: int = 3, timeout: float = None, account_name: str = None) -> dict: ...
    def cancel_order(self, stock_code: str = None, cancel_type: str = "all", timeout: float = None, account_name: str = None) -> dict: ...
    def condition_buy(self, stock_code: str, target_price: float, quantity: int, expire_days: int = 30, timeout: float = None, account_name: str = None) -> dict: ...
    def condition_sell(self, stock_code: str, target_price: float, quantity: int, expire_days: int = 30, timeout: float = None, account_name: str = None) -> dict: ...
    def stop_loss_profit(self, stock_code: str, stop_loss_percent: float, stop_profit_percent: float, quantity: int = None, expire_days: int = 30, timeout: float = None, account_name: str = None) -> dict: ...
    def query_condition_orders(self, timeout: float = None, account_name: str = None) -> dict: ...
    def cancel_condition_orders(self, stock_code: str = None, order_type: str = None, timeout: float = None, account_name: str = None) -> dict: ...
    def reverse_repo_buy(self, market: str, time_range: str, amount: int, timeout: float = None, account_name: str = None) -> dict: ...

    # 查询操作（均支持可选 account_name 参数，见多账户支持）
    def query_holdings(self, timeout: float = None, account_name: str = None) -> dict: ...
    def query_funds(self, timeout: float = None, account_name: str = None) -> dict: ...
    def query_orders(self, stock_code: str = None, timeout: float = None, account_name: str = None) -> dict: ...
    def query_historical_commission(self, stock_code: str = None, time_range: str = "当日", timeout: float = None, account_name: str = None) -> dict: ...
    def query_reverse_repo(self, timeout: float = None, account_name: str = None) -> dict: ...

    # 连接管理
    def close(self): ...
    def __enter__(self): ...
    def __exit__(self, exc_type, exc_val, exc_tb): ...
```

### 统一返回格式

所有方法（交易、查询、系统管理）返回与服务端 REST / MCP 一致的统一信封：

```python
{
    "success": bool | None,  # 业务结果；操作未到终态时为 None
    "status": str | None,    # queued/running/completed/failed/cancelled
    "message": str,          # 错误信息或成功消息
    "error_code": str | None,# 失败分类，可编程处理
    "current_used_account": str | None,  # 操作实际执行时的当前使用账户（未确认过为 None）
    "data": Any,             # 业务数据（查询类为记录列表）
    "timestamp": str         # 北京时间，格式 "2026-08-22 06:46:56"
}
```

`data` 的字段由每个操作的 Result 模型确定（交易类为单个对象，查询类为记录列表），
完整字段定义见 [API 文档 - 可用操作](api.md#available-operations)。

**示例**：
```python
result = client.buy("600000", 10.50, 100)
# {
#     "success": True,
#     "status": "completed",
#     "message": "成功提交600000的买入委托，耗时2.31秒",
#     "error_code": None,
#     "current_used_account": None,
#     "data": {"stock_code": "600000", "price": 10.5, "quantity": 100},
#     "timestamp": "2026-08-22 06:46:56"
# }
```

### TradeClientError 异常类

客户端 SDK 提供了专用的异常类 `TradeClientError`，用于处理客户端级别的错误：

```python
class TradeClientError(Exception):
    """客户端异常"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        """
        Args:
            message: 错误消息
            status_code: HTTP 状态码（可选）
        """
```

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| message | str | 错误消息描述 |
| status_code | int \| None | HTTP 状态码（如果有） |

**使用示例**：

```python
from easyths import TradeClient, TradeClientError

try:
    with TradeClient(host="127.0.0.1", port=7648) as client:
        result = client.buy("600000", 10.50, 100)
except TradeClientError as e:
    print(f"错误消息: {e}")
    print(f"状态码: {e.status_code}")
```

**常见异常场景**：

| 场景 | status_code | 说明 |
|------|-------------|------|
| 连接失败 | None | 无法连接到服务端，请检查服务端是否启动 |
| 认证失败 | 401 | API Key 错误或未提供 |
| IP 被拒 | 403 | 来源 IP 不在服务端白名单 |
| 参数校验失败 | 422 | 参数非法或包含未知字段，修正后重提 |
| 操作不存在 | 404 | 操作 ID 错误或结果已被淘汰（超过 3 小时） |
| 操作超时 | 408 | 等待结果超时，操作仍在执行，勿重复提交 |
| 触发限流 | 429 | 请求过于频繁，降低频率后重试 |
| 服务端错误 | 500 | 服务端内部错误 |
| HTTP 错误 | 其他 | HTTP 请求失败，对应相应的 HTTP 状态码 |

---

## 相关文档

- [API 服务](api.md) - RESTful API 接口文档
- [基础用法](basic-usage.md) - 配置和运行指南
- [同花顺客户端配置](ths-client.md) - 交易客户端设置
