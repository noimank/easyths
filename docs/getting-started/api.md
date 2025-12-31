# API 服务

EasyTHS 提供基于 FastAPI 的 RESTful API 接口，支持自动化交易操作。

## 基础信息

- **Base URL**: `http://127.0.0.1:7648`
- **Content-Type**: `application/json`
- **API 版本**: v1

## 认证

API 支持 Bearer Token 认证。在请求头中添加：

```http
Authorization: Bearer your-api-key
```

### 配置 API Key

可以通过以下两种方式配置 API Key：

**方式一：环境变量**

```bash
# Windows
set API_KEY=your-secret-key

# Linux/macOS
export API_KEY=your-secret-key
```

**方式二：配置文件**

在 `config.toml` 中设置：

详细的配置文件参考：[基础用法](basic-usage.md) 

```toml
[api]
key = "your-secret-key"
```

> **注意**：如果未配置 API Key，则无需认证即可访问所有接口。出于安全考虑，建议在生产环境中务必配置 API Key。

---

## 系统接口

### 健康检查

检查系统运行状态和各组件健康度。

```http
GET /api/v1/system/health
```

**响应示例**:
```json
{
  "success": true,
  "message": "系统运行正常",
  "data": {
    "status": "healthy",
    "timestamp": "2025-12-26T10:30:00",
    "components": {
      "automator": "connected",
      "logged_in": true,
      "plugins": {
        "loaded": 7
      }
    }
  }
}
```

### 获取系统状态

获取系统详细状态信息。

```http
GET /api/v1/system/status
```

**响应示例**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "timestamp": "2025-12-26T10:30:00",
    "automator": {
      "connected": true,
      "logged_in": true,
      "app_path": "C:/同花顺远航版/transaction/xiadan.exe",
      "backend": "win32"
    },
    "plugins": {
      "loaded_plugins": ["buy", "sell", "holding_query", "funds_query", "order_query", "order_cancel"],
      "plugin_count": 6
    }
  }
}
```

### 获取系统信息

获取系统基本信息。

```http
GET /api/v1/system/info
```

**响应示例**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "name": "同花顺交易自动化系统",
    "version": "1.0.0",
    "description": "基于pywinauto的同花顺交易软件自动化系统",
    "features": [
      "操作串行化",
      "优先级队列",
      "插件化架构",
      "RESTful API",
      "实时监控"
    ]
  }
}
```

---

## 操作接口

### 执行操作

提交交易操作到队列。

```http
POST /api/v1/operations/{operation_name}
```

**路径参数**:

- `operation_name`: 操作名称，见下文[可用操作](#available-operations)

**请求体**:
```json
{
  "params": {
    // 操作参数，根据不同操作而变化
  },
  "priority": 0
}
```

**参数说明**:

- `params`: 操作参数对象，具体参数见[可用操作](#available-operations)

- `priority`: 优先级 (0-10)，数值越大优先级越高，默认 0

**响应示例**:
```json
{
  "success": true,
  "message": "操作已添加到队列",
  "data": {
    "operation_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "queued",
    "queue_position": 0
  }
}
```

### 获取操作状态

查询操作执行状态。

```http
GET /api/v1/operations/{operation_id}/status
```

**响应示例**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "operation_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "buy",
    "status": "success",
    "result": {
      "success": true,
      "data": {
        "stock_code": "600000",
        "price": "10.50",
        "quantity": 100,
        "operation": "buy"
      }
    },
    "error": null,
    "timestamp": "2025-12-26T10:30:00",
    "retry_count": 0
  }
}
```

**状态值**:

- `queued`: 排队中

- `running`: 执行中

- `success`: 成功

- `failed`: 失败

### 获取操作结果

阻塞等待并获取操作结果。

```http
GET /api/v1/operations/{operation_id}/result?timeout=30
```

**查询参数**:
- `timeout`: 超时时间（秒），可选，默认阻塞等待

**响应示例**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "operation_id": "550e8400-e29b-41d4-a716-446655440000",
    "result": {
      "success": true,
      "data": {
        "stock_code": "600000",
        "price": "10.50",
        "quantity": 100
      }
    }
  }
}
```

### 取消操作

取消排队中的操作。

```http
DELETE /api/v1/operations/{operation_id}
```

**响应示例**:
```json
{
  "success": true,
  "message": "操作已取消"
}
```

### 获取可用操作列表

获取所有已加载的操作。

```http
GET /api/v1/operations/
```

**响应示例**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "operations": {
      "buy": {
        "name": "BuyOperation",
        "version": "1.0.0",
        "description": "买入股票操作",
        "parameters": {
          "stock_code": {
            "type": "string",
            "required": true,
            "description": "股票代码（6位数字）"
          }
        }
      }
    },
    "count": 7
  }
}
```

---

## 队列接口

### 获取队列统计

获取操作队列的统计信息。

```http
GET /api/v1/queue/stats
```

**响应示例**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "queued_count": 0,
    "running_count": 0,
    "success_count": 10,
    "failed_count": 0
  }
}
```

---

## 可用操作 {#available-operations}

### buy - 买入股票

```http
POST /api/v1/operations/buy
```

**请求参数**:
```json
{
  "params": {
    "stock_code": "600000",
    "price": 10.50,
    "quantity": 100
  },
  "priority": 5
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码（6位数字） |
| price | number | 是 | 买入价格 |
| quantity | integer | 是 | 买入数量（必须是100的倍数） |

### sell - 卖出股票

```http
POST /api/v1/operations/sell
```

**请求参数**:
```json
{
  "params": {
    "stock_code": "600000",
    "price": 10.50,
    "quantity": 100
  }
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码（6位数字） |
| price | number | 是 | 卖出价格 |
| quantity | integer | 是 | 卖出数量（必须是100的倍数） |

### holding_query - 持仓查询

```http
POST /api/v1/operations/holding_query
```

**请求参数**:
```json
{
  "params": {
    "return_type": "json"
  }
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| return_type | string | 否 | 返回类型：str/json/dict/df/markdown，默认 json |

### funds_query - 资金查询

```http
POST /api/v1/operations/funds_query
```

**请求参数**:
```json
{
  "params": {}
}
```

**响应数据包含**: 资金余额、冻结金额、可用金额、可取金额、股票市值、总资产、持仓盈亏

### order_query - 委托查询

```http
POST /api/v1/operations/order_query
```

**请求参数**:
```json
{
  "params": {
    "stock_code": "600000",
    "return_type": "json"
  }
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 否 | 股票代码，不指定则查询全部 |
| return_type | string | 是 | 返回类型：str/json/dict/df/markdown |

### order_cancel - 撤单

```http
POST /api/v1/operations/order_cancel
```

**请求参数**:
```json
{
  "params": {
    "stock_code": "600000",
    "cancel_type": "all"
  }
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 否 | 股票代码，不指定则撤销所有 |
| cancel_type | string | 否 | 撤单类型：all(全部)/buy(买入)/sell(卖出)，默认 all |

### historical_commission_query - 历史成交查询

```http
POST /api/v1/operations/historical_commission_query
```

**请求参数**:
```json
{
  "params": {
    "return_type": "json",
    "stock_code": "600000",
    "time_range": "当日"
  }
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| return_type | string | 否 | 返回类型：str/json/dict/df/markdown，默认 json |
| stock_code | string | 否 | 股票代码（6位数字），不指定则查询所有股票 |
| time_range | string | 否 | 时间范围：当日/近一周/近一月/近三月/近一年，默认当日 |

### reverse_repo_buy - 国债逆回购购买

```http
POST /api/v1/operations/reverse_repo_buy
```

**请求参数**:
```json
{
  "params": {
    "market": "上海",
    "time_range": "1天期",
    "amount": 10000
  }
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| market | string | 是 | 交易市场：上海/深圳 |
| time_range | string | 是 | 回购期限：1天期/2天期/3天期/4天期/7天期 |
| amount | integer | 是 | 出借金额（必须是1000的倍数） |

**响应示例**:
```json
{
  "success": true,
  "message": "操作成功",
  "data": {
    "operation_id": "...",
    "result": {
      "success": true,
      "data": {
        "market": "上海",
        "time_range": "1天期",
        "amount": 10000,
        "success": true,
        "message": "国债逆回购操作成功， 成功出借:10000 元， 年化利率为：2.50%"
      }
    }
  }
}
```

### reverse_repo_query - 国债逆回购查询

```http
POST /api/v1/operations/reverse_repo_query
```

**请求参数**:
```json
{
  "params": {}
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "operation_id": "...",
    "result": {
      "success": true,
      "data": {
        "reverse_repo_interest": [
          {
            "市场类型": "上海市场",
            "时间类型": "1天期",
            "年化利率": "2.50%"
          },
          {
            "市场类型": "深圳市场",
            "时间类型": "1天期",
            "年化利率": "2.45%"
          }
        ],
        "timestamp": "2025-12-27T10:30:00",
        "success": true,
        "message": "查询国债逆回购年化利率成功"
      }
    }
  }
}
```

### condition_buy - 条件买入

设置条件买入单，当股价达到目标价格时自动触发买入。

```http
POST /api/v1/operations/condition_buy
```

**请求参数**:
```json
{
  "params": {
    "stock_code": "600000",
    "target_price": 10.50,
    "quantity": 100,
    "expire_days": 30
  }
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码（6位数字） |
| target_price | number | 是 | 目标价格（触发价格） |
| quantity | integer | 是 | 买入数量（必须是100的倍数） |
| expire_days | integer | 否 | 有效期（自然日），可选1/3/5/10/20/30，默认30 |

**响应示例**:
```json
{
  "success": true,
  "message": "操作成功",
  "data": {
    "operation_id": "...",
    "result": {
      "success": true,
      "data": {
        "stock_code": "600000",
        "target_price": 10.50,
        "quantity": 100,
        "operation": "condition_buy",
        "success": true,
        "message": "执行600000的条件单成功"
      }
    }
  }
}
```

### stop_loss_profit - 止盈止损

为持仓股票设置止盈止损策略，当价格达到止盈或止损条件时自动触发卖出。

```http
POST /api/v1/operations/stop_loss_profit
```

**请求参数**:
```json
{
  "params": {
    "stock_code": "600000",
    "stop_loss_percent": 3.0,
    "stop_profit_percent": 5.0,
    "quantity": 100,
    "expire_days": 30
  }
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码（6位数字） |
| stop_loss_percent | number | 是 | 止损百分比（如3表示3%） |
| stop_profit_percent | number | 是 | 止盈百分比（如5表示5%） |
| quantity | integer | 否 | 卖出数量（必须是100的倍数），可选，不指定则使用全部可用持仓 |
| expire_days | integer | 否 | 有效期（自然日），可选1/3/5/10/20/30，默认30 |

> **注意**：止盈百分比必须大于止损百分比。quantity 参数建议指定，因为受 T+1 限制，当天买入的股票如果不指定数量无法设置止盈止损。

**响应示例**:
```json
{
  "success": true,
  "message": "操作成功",
  "data": {
    "operation_id": "...",
    "result": {
      "success": true,
      "data": {
        "stock_code": "600000",
        "stop_loss_percent": 3.0,
        "stop_profit_percent": 5.0,
        "operation": "stop_loss_profit",
        "success": true,
        "message": "执行600000的止盈止损单成功"
      }
    }
  }
}
```

### condition_order_query - 条件单查询

查询未触发的条件单信息。

```http
POST /api/v1/operations/condition_order_query
```

**请求参数**:
```json
{
  "params": {
    "return_type": "json"
  }
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| return_type | string | 否 | 返回类型：str/json/dict/df/markdown，默认 json |

**响应示例**:
```json
{
  "success": true,
  "message": "操作成功",
  "data": {
    "operation_id": "...",
    "result": {
      "success": true,
      "data": {
        "condition_orders": [...],
        "message": "条件单查询成功，共获取到2条数据",
        "timestamp": "2025-12-27T10:30:00",
        "success": true
      }
    }
  }
}
```

### condition_order_cancel - 条件单删除

删除指定的条件单。

```http
POST /api/v1/operations/condition_order_cancel
```

**请求参数**:
```json
{
  "params": {
    "stock_code": "600000",
    "order_type": "买入"
  }
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 否 | 股票代码（6位数字），不指定则删除所有条件单 |
| order_type | string | 否 | 订单类型：买入/卖出 |

**响应示例**:
```json
{
  "success": true,
  "message": "操作成功",
  "data": {
    "operation_id": "...",
    "result": {
      "success": true,
      "data": {
        "stock_code": "600000",
        "order_type": "买入",
        "deleted_count": 1,
        "message": "条件单删除成功",
        "timestamp": "2025-12-27T10:30:00",
        "success": true
      }
    }
  }
}
```

---

## 使用示例

### Python 示例

```python
import requests

base_url = "http://127.0.0.1:7648"
api_key = "your-api-key"  # 如果配置了 API Key

headers = {
    "Authorization": f"Bearer {api_key}"  # 如果配置了 API Key
}

# 买入股票
response = requests.post(
    f"{base_url}/api/v1/operations/buy",
    headers=headers,  # 如果配置了 API Key
    json={
        "params": {
            "stock_code": "600000",
            "price": 10.50,
            "quantity": 100
        },
        "priority": 5
    }
)
operation_id = response.json()["data"]["operation_id"]

# 查询操作状态
status = requests.get(
    f"{base_url}/api/v1/operations/{operation_id}/status",
    headers=headers  # 如果配置了 API Key
)
print(status.json())

# 查询持仓
response = requests.post(
    f"{base_url}/api/v1/operations/holding_query",
    headers=headers,  # 如果配置了 API Key
    json={"params": {"return_type": "json"}}
)
print(response.json())
```

### cURL 示例

```bash
# 健康检查
curl http://127.0.0.1:7648/api/v1/system/health

# 买入股票（带认证）
curl -X POST http://127.0.0.1:7648/api/v1/operations/buy \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "stock_code": "600000",
      "price": 10.50,
      "quantity": 100
    }
  }'

# 查询持仓（带认证）
curl -X POST http://127.0.0.1:7648/api/v1/operations/holding_query \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"params": {"return_type": "json"}}'
```

---

## 交互式文档

启动服务后，访问以下地址查看完整的交互式 API 文档：

- **Swagger UI**: `http://127.0.0.1:7648/docs`
- **ReDoc**: `http://127.0.0.1:7648/redoc`
