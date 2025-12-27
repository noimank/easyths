# Client SDK

EasyTHS 提供了官方的 Python Client SDK（`TradeClient`），用于与服务端进行通信，执行各种交易操作。

## 安装

Client SDK 包含在 `easyths` 包中。根据您的使用场景，可以选择以下两种安装方式：

### 仅安装客户端 SDK（推荐用于远程调用）

如果您只需要使用 `TradeClient` 连接到已运行的服务端，可以仅安装客户端依赖，这样可以大幅减少依赖包的数量：

```bash
# 使用 uv 安装（推荐）
uv add "easyths[client]"

# 或使用 pip
pip install "easyths[client]"
```

**客户端模式仅依赖**：

- `httpx` - HTTP 客户端

- `pydantic` - 数据验证

### 安装完整包（包含服务端）

如果您需要在本地运行完整的服务端（包括自动化交易功能），需要安装完整包：

```bash
# 使用 uv 安装（推荐）
uv add easyths

# 或使用 pip
pip install easyths
```

**完整包包含**：

- 所有客户端依赖

- FastAPI 服务端

- pywinauto（Windows GUI 自动化）

- 其他服务端依赖（OCR、图像处理等）

> **注意**：完整包仅支持 Windows 系统。客户端 SDK 可以在任何系统上运行。

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

### 获取系统信息

```python
info = client.get_system_info()
# 返回: {"success": True, "data": {"name": "...", "version": "..."}}
```

### 获取队列统计

```python
stats = client.get_queue_stats()
# 返回: {"success": True, "data": {"queued_count": 0, ...}}
```

### 获取可用操作列表

```python
ops = client.list_operations()
# 返回: {"success": True, "data": {"operations": {...}, "count": 7}}
```

---

## 交易操作

### 买入股票

```python
result = client.buy(
    stock_code="600000",  # 股票代码
    price=10.50,          # 买入价格
    quantity=100,         # 买入数量（100的倍数）
    timeout=60.0          # 超时时间（可选，默认60秒）
)

# 检查结果
if result["data"]["result"]["success"]:
    data = result["data"]["result"]["data"]
    print(f"买入成功: {data['message']}")
else:
    error = result["data"]["result"]["error"]
    print(f"买入失败: {error}")
```

### 卖出股票

```python
result = client.sell(
    stock_code="600000",
    price=11.00,
    quantity=100,
    timeout=60.0
)

if result["data"]["result"]["success"]:
    print("卖出成功")
```

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

---

## 查询操作

### 查询持仓

```python
result = client.query_holdings(
    return_type="json",  # str/json/dict/df/markdown
    timeout=30.0
)

if result["data"]["result"]["success"]:
    holdings = result["data"]["result"]["data"]["holdings"]
    for position in holdings:
        print(f"{position['股票代码']}: {position['持仓数量']}股")
```

### 查询资金

```python
result = client.query_funds(timeout=30.0)

if result["data"]["result"]["success"]:
    funds = result["data"]["result"]["data"]
    print(f"总资产: {funds['总资产']}")
    print(f"可用金额: {funds['可用金额']}")
```

### 查询委托单

```python
# 查询所有委托
result = client.query_orders(return_type="json")

# 查询指定股票的委托
result = client.query_orders(
    stock_code="600000",
    return_type="json"
)

if result["data"]["result"]["success"]:
    orders = result["data"]["result"]["data"]["orders"]
    for order in orders:
        print(f"{order['股票代码']}: {order['委托数量']}股 @ {order['委托价格']}")
```

### 查询历史成交

```python
result = client.query_historical_commission(return_type="json")

if result["data"]["result"]["success"]:
    commissions = result["data"]["result"]["data"]
    print(commissions)
```

### 购买国债逆回购

```python
result = client.reverse_repo_buy(
    market="上海",        # 交易市场：上海/深圳
    time_range="1天期",   # 回购期限：1天期/2天期/3天期/4天期/7天期
    amount=10000,         # 出借金额（1000的倍数）
    timeout=60.0
)

if result["data"]["result"]["success"]:
    message = result["data"]["result"]["data"]["message"]
    print(f"购买成功: {message}")
else:
    error = result["data"]["result"]["error"]
    print(f"购买失败: {error}")
```

### 查询国债逆回购年化利率

```python
result = client.query_reverse_repo(timeout=30.0)

if result["data"]["result"]["success"]:
    rates = result["data"]["result"]["data"]["reverse_repo_interest"]
    for item in rates:
        print(f"{item['市场类型']} - {item['时间类型']}: {item['年化利率']}")
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
    priority=5  # 优先级 0-10，数字越大优先级越高
)
print(f"操作ID: {operation_id}")
```

### 获取操作状态

```python
status = client.get_operation_status(operation_id)
print(status)
# 返回状态: queued/running/success/failed
```

### 获取操作结果

```python
# 阻塞等待直到操作完成
result = client.get_operation_result(
    operation_id=operation_id,
    timeout=30.0  # 超时时间（可选）
)

if result["data"]["result"]["success"]:
    print("操作成功:", result["data"]["result"]["data"])
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
        if result["data"]["result"]["success"]:
            print("买入成功")

except TradeClientError as e:
    print(f"交易失败: {e}")
    if e.status_code:
        print(f"状态码: {e.status_code}")
```

**常见错误状态码**：

- 连接失败：无法连接到服务端
- 401：认证失败（API Key 错误）
- 408：操作超时
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
        if funds["data"]["result"]["success"]:
            available = funds["data"]["result"]["data"]["可用金额"]
            print(f"可用资金: {available}")

        # 买入股票
        result = client.buy("600000", 10.50, 100)
        if result["data"]["result"]["success"]:
            print("买入成功")
        else:
            print(f"买入失败: {result['data']['result']['error']}")

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
            result = client.get_operation_result(op_id, timeout=60)
            results.append(result)

        # 处理结果
        for result in results:
            if result["data"]["result"]["success"]:
                data = result["data"]["result"]["data"]
                print(f"操作成功: {data.get('message', 'N/A')}")
            else:
                print(f"操作失败: {result['data']['result']['error']}")
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
    def health_check(self) -> APIResponse: ...
    def get_system_status(self) -> APIResponse: ...
    def get_system_info(self) -> APIResponse: ...
    def get_queue_stats(self) -> APIResponse: ...
    def list_operations(self) -> APIResponse: ...

    # 通用操作
    def execute_operation(self, operation_name: str, params: dict, priority: int = 0) -> str: ...
    def get_operation_status(self, operation_id: str) -> APIResponse: ...
    def get_operation_result(self, operation_id: str, timeout: float = None) -> APIResponse: ...
    def cancel_operation(self, operation_id: str) -> bool: ...

    # 交易操作
    def buy(self, stock_code: str, price: float, quantity: int, timeout: float = 60.0) -> APIResponse: ...
    def sell(self, stock_code: str, price: float, quantity: int, timeout: float = 60.0) -> APIResponse: ...
    def cancel_order(self, stock_code: str = None, cancel_type: str = "all", timeout: float = 60.0) -> APIResponse: ...
    def reverse_repo_buy(self, market: str, time_range: str, amount: int, timeout: float = 60.0) -> APIResponse: ...

    # 查询操作
    def query_holdings(self, return_type: str = "json", timeout: float = 30.0) -> APIResponse: ...
    def query_funds(self, timeout: float = 30.0) -> APIResponse: ...
    def query_orders(self, stock_code: str = None, return_type: str = "json", timeout: float = 30.0) -> APIResponse: ...
    def query_historical_commission(self, return_type: str = "json", timeout: float = 30.0) -> APIResponse: ...
    def query_reverse_repo(self, timeout: float = 30.0) -> APIResponse: ...

    # 连接管理
    def close(self): ...
    def __enter__(self): ...
    def __exit__(self, exc_type, exc_val, exc_tb): ...
```

### APIResponse 类型

所有 API 方法返回的响应格式：

```python
class APIResponse(TypedDict):
    success: bool      # 操作是否成功
    message: str       # 响应消息
    data: Any          # 响应数据
    error: str | None  # 错误信息（如果有）
    timestamp: str     # 响应时间戳
```

对于交易操作（如 `buy`, `sell`），实际返回的数据结构为：

```python
{
    "success": True,
    "message": "查询成功",
    "data": {
        "operation_id": "...",     # 操作ID
        "result": {
            "success": bool,        # 业务操作是否成功
            "data": {...},          # 业务数据
            "error": str | None,    # 业务错误信息
            "timestamp": str
        }
    },
    "error": None,
    "timestamp": "..."
}
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
| 操作超时 | 408 | 操作执行时间超过设定的超时时间 |
| 服务端错误 | 500 | 服务端内部错误 |
| HTTP 错误 | 其他 | HTTP 请求失败，对应相应的 HTTP 状态码 |

---

## 相关文档

- [API 服务](api.md) - RESTful API 接口文档
- [基础用法](basic-usage.md) - 配置和运行指南
- [同花顺客户端配置](ths-client.md) - 交易客户端设置
