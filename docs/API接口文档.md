# QuantTrader API 接口文档

## 概述

QuantTrader 是一个基于同花顺交易软件的自动化交易系统，提供了完整的 REST API 接口用于执行交易操作。本文档详细介绍了所有可用的 API 接口及其使用方法。

### 基础信息

- **API 基础路径**: `http://localhost:8000`
- **认证方式**: Bearer Token
- **数据格式**: JSON
- **字符编码**: UTF-8

### 认证

所有 API 请求都需要在请求头中包含有效的 API 密钥：

```
Authorization: Bearer your_api_key_here
```

API 密钥需要在环境变量中配置（见 .env.example 文件）。

### 响应格式

所有 API 响应都遵循统一格式：

```json
{
  "success": true,
  "message": "操作成功",
  "data": {},
  "timestamp": "2024-01-01T12:00:00"
}
```

错误响应格式：

```json
{
  "success": false,
  "message": "操作失败",
  "error": "错误详情",
  "timestamp": "2024-01-01T12:00:00"
}
```

## 1. 系统接口

### 1.1 健康检查

检查系统各组件的运行状态。

**接口地址**: `GET /api/v1/system/health`

**请求参数**: 无

**响应示例**:
```json
{
  "success": true,
  "message": "系统运行正常",
  "data": {
    "status": "healthy",
    "timestamp": "2024-01-01T12:00:00",
    "components": {
      "automator": "connected",
      "logged_in": true,
      "plugins": {
        "loaded": 4
      }
    }
  }
}
```

### 1.2 系统状态

获取系统详细状态信息。

**接口地址**: `GET /api/v1/system/status`

**请求参数**: 无

**响应示例**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "timestamp": "2024-01-01T12:00:00",
    "automator": {
      "connected": true,
      "logged_in": true,
      "app_path": "C:/同花顺远航版/transaction/xiadan.exe",
      "backend": "win32"
    },
    "plugins": {
      "buy": {
        "name": "BuyOperation",
        "version": "1.0.0",
        "enabled": true
      },
      "sell": {
        "name": "SellOperation",
        "version": "1.0.0",
        "enabled": true
      }
    }
  }
}
```

### 1.3 系统信息

获取系统基本信息。

**接口地址**: `GET /api/v1/system/info`

**请求参数**: 无

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
      "插件化架构",
      "RESTful API",
      "实时监控"
    ]
  }
}
```

## 2. 操作接口

### 2.1 执行单个操作

执行指定的交易操作。

**接口地址**: `POST /api/v1/operations/{operation_name}`

**路径参数**:
- `operation_name`: 操作名称（见操作列表）

**请求体**:
```json
{
  "params": {
    // 操作参数，根据不同操作而变化
  },
  "priority": 0  // 可选，优先级 0-10
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "操作已添加到队列",
  "data": {
    "operation_id": "uuid-string",
    "status": "queued",
    "queue_position": 1
  }
}
```

### 2.2 批量执行操作

批量执行多个操作。

**接口地址**: `POST /api/v1/operations/batch`

**请求体**:
```json
{
  "operations": [
    {
      "name": "buy",
      "params": {
        "stock_code": "000001",
        "price": 10.50,
        "quantity": 100
      },
      "priority": 0
    }
  ],
  "mode": "sequential",  // sequential(顺序) 或 parallel(并行)
  "stop_on_error": false  // 遇到错误时是否停止
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "批量操作已提交，成功添加 1/1 个操作",
  "data": {
    "operations": [
      {
        "operation_id": "uuid-string",
        "name": "buy",
        "status": "queued"
      }
    ],
    "success_count": 1,
    "total_count": 1
  }
}
```

### 2.3 查询操作状态

查询指定操作的执行状态。

**接口地址**: `GET /api/v1/operations/{operation_id}/status`

**路径参数**:
- `operation_id`: 操作ID

**响应示例**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "operation_id": "uuid-string",
    "name": "buy",
    "status": "completed",
    "result": {
      "success": true,
      "data": {
        "stock_code": "000001",
        "price": "10.50",
        "quantity": 100,
        "operation": "buy",
        "success": true,
        "message": "委托成功"
      }
    },
    "error": null,
    "timestamp": "2024-01-01T12:00:00",
    "retry_count": 0
  }
}
```

### 2.4 取消操作

取消一个未执行或正在执行的操作。

**接口地址**: `DELETE /api/v1/operations/{operation_id}`

**路径参数**:
- `operation_id`: 操作ID

**响应示例**:
```json
{
  "success": true,
  "message": "操作已取消"
}
```

### 2.5 重试操作

重试一个失败的操作。

**接口地址**: `POST /api/v1/operations/{operation_id}/retry`

**路径参数**:
- `operation_id`: 操作ID

**响应示例**:
```json
{
  "success": true,
  "message": "操作已重新入队"
}
```

### 2.6 获取操作列表

获取所有可用的操作。

**接口地址**: `GET /api/v1/operations/`

**响应示例**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "buy": {
      "name": "BuyOperation",
      "version": "1.0.0",
      "description": "买入股票操作",
      "parameters": {
        "stock_code": {
          "type": "string",
          "required": true,
          "description": "股票代码（6位数字）"
        },
        "price": {
          "type": "number",
          "required": true,
          "description": "买入价格"
        },
        "quantity": {
          "type": "integer",
          "required": true,
          "description": "买入数量（必须是100的倍数）"
        }
      }
    }
  }
}
```

## 3. 队列接口

### 3.1 队列统计

获取操作队列的统计信息。

**接口地址**: `GET /api/v1/queue/stats`

**响应示例**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "total": 5,
    "pending": 1,
    "queued": 2,
    "running": 1,
    "completed": 1,
    "failed": 0,
    "cancelled": 0
  }
}
```

### 3.2 清空队列

清空操作队列中所有待执行的操作。

**接口地址**: `POST /api/v1/queue/clear`

**响应示例**:
```json
{
  "success": true,
  "message": "队列已清空"
}
```

## 4. 可用操作详解

### 4.1 买入操作 (buy)

**功能**: 自动买入指定股票

**参数**:
- `stock_code` (string, 必需): 6位股票代码，如 "000001"
- `price` (number, 必需): 买入价格，支持2位小数
- `quantity` (integer, 必需): 买入数量，必须是100的倍数

**示例请求**:
```bash
curl -X POST http://localhost:8000/api/v1/operations/buy \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "stock_code": "000001",
      "price": 10.50,
      "quantity": 100
    }
  }'
```

### 4.2 卖出操作 (sell)

**功能**: 自动卖出指定股票

**参数**:
- `stock_code` (string, 必需): 6位股票代码，如 "000001"
- `price` (number, 必需): 卖出价格，支持2位小数
- `quantity` (integer, 必需): 卖出数量，必须是100的倍数

**示例请求**:
```bash
curl -X POST http://localhost:8000/api/v1/operations/sell \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "stock_code": "000001",
      "price": 11.00,
      "quantity": 100
    }
  }'
```

### 4.3 资金查询 (funds_query)

**功能**: 查询账户资金信息

**参数**:
- `query_type` (string, 可选): 查询类型
  - "total": 总资金
  - "available": 可用资金
  - "frozen": 冻结资金
  - "stock_value": 股票市值
  - "all": 所有信息（默认）

**示例请求**:
```bash
curl -X POST http://localhost:8000/api/v1/operations/funds_query \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "query_type": "all"
    }
  }'
```

**响应数据示例**:
```json
{
  "资金余额": "10000.00",
  "冻结金额": "0.00",
  "可用金额": "10000.00",
  "可取金额": "10000.00",
  "股票市值": "5000.00",
  "总资产": "15000.00",
  "持仓盈亏": "100.00",
  "timestamp": 1704067200.0,
  "success": true
}
```

### 4.4 持仓查询 (holding_query)

**功能**: 查询当前持仓股票信息

**参数**:
- `return_type` (string, 可选): 返回数据格式
  - "str": 字符串格式（默认）
  - "json": JSON格式
  - "dict": 字典格式
  - "df": Pandas DataFrame格式
  - "markdown": Markdown表格格式

**示例请求**:
```bash
curl -X POST http://localhost:8000/api/v1/operations/holding_query \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "return_type": "json"
    }
  }'
```

## 5. 错误码说明

| HTTP状态码 | 错误说明 | 示例场景 |
|-----------|---------|---------|
| 400 | 请求参数错误 | 缺少必需参数、参数格式错误 |
| 401 | 认证失败 | API密钥无效或未提供 |
| 404 | 资源不存在 | 操作ID不存在、操作名称不存在 |
| 429 | 请求频率超限 | 超过API调用频率限制 |
| 500 | 服务器内部错误 | 系统异常、操作执行失败 |

## 6. 使用建议

1. **操作队列**: 所有交易操作都会进入队列串行执行，避免并发冲突
2. **重试机制**: 失败的操作支持自动重试（默认最多3次）
3. **优先级**: 可通过设置priority参数调整操作优先级（0-10）
4. **批量操作**: 对于多个相关操作，建议使用批量接口
5. **状态查询**: 建议定期查询操作状态，直到操作完成
6. **错误处理**: 请根据响应中的success字段判断操作是否成功

## 7. 示例代码

### Python 示例

```python
import requests
import json

# API配置
BASE_URL = "http://localhost:8000"
API_KEY = "your_api_key_here"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 买入股票示例
def buy_stock(stock_code, price, quantity):
    url = f"{BASE_URL}/api/v1/operations/buy"
    data = {
        "params": {
            "stock_code": stock_code,
            "price": price,
            "quantity": quantity
        }
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()

# 查询操作状态
def get_operation_status(operation_id):
    url = f"{BASE_URL}/api/v1/operations/{operation_id}/status"
    response = requests.get(url, headers=headers)
    return response.json()

# 使用示例
result = buy_stock("000001", 10.50, 100)
if result["success"]:
    operation_id = result["data"]["operation_id"]
    print(f"买入操作已提交，操作ID: {operation_id}")

    # 轮询查询状态
    while True:
        status = get_operation_status(operation_id)
        print(f"操作状态: {status['data']['status']}")

        if status["data"]["status"] in ["completed", "failed", "cancelled"]:
            break

        time.sleep(1)
```

### JavaScript 示例

```javascript
// API配置
const BASE_URL = "http://localhost:8000";
const API_KEY = "your_api_key_here";

const headers = {
    "Authorization": `Bearer ${API_KEY}`,
    "Content-Type": "application/json"
};

// 买入股票示例
async function buyStock(stockCode, price, quantity) {
    const response = await fetch(`${BASE_URL}/api/v1/operations/buy`, {
        method: "POST",
        headers,
        body: JSON.stringify({
            params: {
                stock_code: stockCode,
                price,
                quantity
            }
        })
    });

    return await response.json();
}

// 查询操作状态
async function getOperationStatus(operationId) {
    const response = await fetch(
        `${BASE_URL}/api/v1/operations/${operationId}/status`,
        { headers }
    );

    return await response.json();
}

// 使用示例
(async () => {
    const result = await buyStock("000001", 10.50, 100);
    if (result.success) {
        const operationId = result.data.operation_id;
        console.log(`买入操作已提交，操作ID: ${operationId}`);

        // 轮询查询状态
        const checkStatus = async () => {
            const status = await getOperationStatus(operationId);
            console.log(`操作状态: ${status.data.status}`);

            if (["completed", "failed", "cancelled"].includes(status.data.status)) {
                return;
            }

            setTimeout(checkStatus, 1000);
        };

        checkStatus();
    }
})();
```

## 8. 常见问题

### Q: 如何获取操作ID？
A: 执行操作时会返回operation_id，请保存此ID用于后续状态查询。

### Q: 操作执行需要多长时间？
A: 单个交易操作通常需要2-5秒，具体取决于同花顺客户端的响应速度。

### Q: 可以同时执行多个操作吗？
A: 可以，但所有操作会排队串行执行，确保不会冲突。

### Q: 如何设置API密钥？
A: 在.env文件中设置API_KEY环境变量，重启服务生效。

### Q: 支持哪些股票代码？
A: 支持6位数字的A股代码，如000001、600000等。

## 9. 更新日志

### v1.0.0
- 初始版本发布
- 支持基本的买卖操作
- 提供完整的REST API接口
- 实现操作队列管理
- 添加资金和持仓查询功能