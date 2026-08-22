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

在 `config.toml` 中设置：

详细的配置文件参考：[基础用法](basic-usage.md)

```toml
[api]
key = "your-secret-key"
```

> **注意**：如果未配置 API Key，则无需认证即可访问所有接口。出于安全考虑，建议在生产环境中务必配置 API Key。

---

## 统一响应信封 {#统一响应信封}

所有 REST 端点（以及 MCP 工具返回、Python SDK 解析结果）共用同一形状：

```json
{
  "success": true,          // 业务结果；操作未到终态（排队/执行中）时为 null
  "status": "completed",    // queued / running / completed / failed / cancelled
  "message": "...",         // 人读信息（成功消息或失败原因）
  "error_code": null,       // 失败原因分类，可编程处理
  "current_used_account": null,  // 操作实际执行时的当前使用账户（未确认过为 null）
  "data": {},               // 业务数据（查询类为记录列表）
  "timestamp": "2026-08-22 06:46:56"   // 北京时间，秒级
}
```

`data` 的字段由每个操作的 Result 模型唯一确定，下文[可用操作](#available-operations)
中每个操作都附有完整的返回字段表；数值字段为客户端文本自动转换的结果
（千分位逗号、百分号已剥离），无该项业务时为 `null`。

`current_used_account` 为操作终态结果统一携带的当前使用账户标识（多账户场景，见
[多账户支持](#多账户支持)），可用于事后核对操作实际落在哪个账户；
单账户场景可忽略。

### 错误码

| error_code | 含义 | 调用方建议 |
|------------|------|-----------|
| invalid_params | 参数校验未过（提交时即 422） | 修正参数后重提 |
| not_connected | 同花顺未连接/进程退出 | 先 `/system/reconnect` |
| client_rejected | 同花顺拒绝：涨跌停/资金不足/标的不支持等 | 不可原样重试 |
| ui_error | 控件定位失败等界面异常 | 可重试一次，持续失败需人工检查客户端 |
| cancelled | 排队中被取消 | 如需继续请重新提交 |
| timeout | 等待结果超时（408，操作仍在执行）；或执行超过硬超时被看门狗收尾（failed 终态，已自动断连） | 408 **勿重复提交**、稍后重查；终态 timeout 先恢复客户端再 `/system/reconnect` |
| not_found | 操作 ID 不存在或结果已淘汰（404） | 检查 ID |
| internal | 内部错误 | 查看服务端日志 |
| unauthorized | 认证失败：缺少或错误的 API Key（401） | 检查 API Key |
| forbidden | IP 不在白名单（403） | 更换来源机器或调整 `api.ip_whitelist` 配置 |
| rate_limited | 触发限流（429） | 降低请求频率，稍后重试 |

认证（401）、IP 白名单（403）、限流（429）等中间件层的拒绝响应同样以统一信封返回，
调用方无需按状态码特判响应体形状。

---

## 系统接口

### 健康检查

真实探活：检查连接标志 **和** 同花顺交易进程是否存活（进程崩溃会如实返回不健康）。

```http
GET /api/v1/system/health
```

**响应示例**:
```json
{
  "success": true,
  "status": null,
  "message": "系统运行正常",
  "error_code": null,
  "data": {
    "status": "healthy",
    "automator": "connected",
    "plugins": {"loaded": 16}
  },
  "timestamp": "2026-08-22 06:46:56"
}
```

### 获取系统状态

获取系统详细状态（含版本、自动化器真实探活与全部插件清单/参数 schema）。

```http
GET /api/v1/system/status
```

**响应示例**:
```json
{
  "success": true,
  "status": null,
  "message": "查询成功",
  "error_code": null,
  "data": {
    "name": "同花顺交易自动化系统",
    "version": "2.0.0",
    "description": "基于pywinauto的同花顺交易软件自动化系统",
    "automator": {
      "connected": true,
      "process_alive": true,
      "app_path": "C:/同花顺远航版/transaction/xiadan.exe",
      "backend": "uia"
    },
    "plugins": {
      "loaded_plugins": ["buy", "sell", "..."],
      "plugin_count": 19,
      "plugin_details": {}
    }
  },
  "timestamp": "2026-08-22 06:46:56"
}
```

### 重连同花顺

同花顺客户端重启后，无需重启服务，调用此接口恢复连接。

> 重连成功会**清空账户缓存**（账户集合/顺序与当前账户不可信）：此后带 `account_name`
> 的操作与 `account_switch` 会快速失败，需显式执行一次 `account_query` 重新初始化。

```http
POST /api/v1/system/reconnect
```

**响应示例**:
```json
{"success": true, "status": "completed", "message": "同花顺重连成功", "error_code": null, "data": null, "timestamp": "2026-08-22 06:46:56"}
```

失败时返回 503 与 `not_connected` 错误码，请检查客户端是否已启动。

---

## 操作接口

所有交易与查询操作共用同一套生命周期接口：**提交 → 排队 → 执行 → 查询结果**。

### 执行操作

提交交易操作到队列。

```http
POST /api/v1/operations/{operation_name}
```

**路径参数**:

- `operation_name`: 操作名称，见下文[可用操作](#available-operations)

**请求体**: 该操作的参数字段**平铺**在请求体顶层（具体字段见各操作说明），
可附带可选的 `priority` 与 `account_name` 字段：

```json
{
  "stock_code": "600000",
  "price": 10.50,
  "quantity": 100,
  "priority": 0,
  "account_name": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| *业务参数 | - | - | 平铺在请求体顶层，见各操作说明 |
| priority | integer | 否 | 优先级（0-10），数值越大优先级越高，默认 0 |
| account_name | string | 否 | 执行前指令：先切换到该账户再执行操作（见[多账户支持](#多账户支持)），空串提交即 422。`account_switch` 操作自身**没有**此字段（其 `account_name` 是业务参数） |

> **参数在提交时校验**：非法取值或未知字段直接返回 422（`error_code: invalid_params`），
> 不会进入队列排队执行。每个操作的完整字段约束见各操作的 OpenAPI 文档（`/docs`）。

**响应示例**（仅受理，未到终态，`success` 为 `null`）:
```json
{
  "success": null,
  "status": "queued",
  "message": "操作已添加到队列",
  "error_code": null,
  "data": {
    "operation_id": "550e8400-e29b-41d4-a716-446655440000",
    "queue_position": 0
  },
  "timestamp": "2026-08-22 06:46:56"
}
```

**受理响应 `data` 字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| operation_id | string | 操作 ID，用于查询状态/结果/取消 |
| queue_position | integer | 当前排队数（不含本操作） |

### 多账户支持 {#多账户支持}

客户端登录了多个账户时，有两种方式指定操作落在哪个账户，**语义不同，务必区分**：

> **`account_name` 的取值规则**：为客户端账户下拉列表的**完整展示名**（仅去除
> 首尾空白），如客户端展示「平安证券-王\*明」则账户名即「平安证券-王\*明」。
> 完整可用账户名以 [account_query](#account_query-账户列表查询) 返回为准。

> **不适用操作**：`account_switch` 与 `account_query` 不接受此指令——前者的
> `account_name` 是切换目标（业务参数），后者负责初始化账户缓存（指令执行
> 依赖该缓存，重连后携带指令会因缓存为空而失败）。

**方式一：显式传入 `account_name`（推荐，操作必然落在该账户）**

提交操作时携带 `account_name`，服务端会在执行该操作前先切换到目标账户，
**切换与操作在同一个队列槽内原子完成**——从切换到操作执行完毕期间，任何其他
调用方的操作都不会插入执行，因此操作**必然落在指定的账户上**。切换是幂等的，
已处于目标账户时重复切换无副作用；切换失败（如账户不存在）时操作以
`failed` + `执行前账户切换失败: ...` 收尾，**不会落到其他账户执行**。

```json
{ "stock_code": "600000", "price": 10.50, "quantity": 100, "account_name": "模拟账户" }
```

**方式二：先 `account_switch` 切换，再调用不指定 `account_name` 的接口（默认当前账户）**

`account_switch` 与后续操作是**两个独立的队列项**。排队执行期间，任何调用方
（包括你自己提交的其他带 `account_name` 的操作）都可能把当前账户切走。
因此不指定 `account_name` 的操作落在**执行时刻的当前账户**上，不一定是
你先前切换的账户。该方式仅适合确认同一时刻只有单一调用方使用的场景。

**核对手段**：每个终态结果都携带 `current_used_account` 字段（操作实际执行时的
当前账户），多账户场景下建议调用方核对该字段与预期一致。

> 服务启动时会自动执行一次 `account_query` 初始化账户缓存（含当前账户识别），
> 正常情况下服务就绪后即可直接使用 `account_name` 指令。

> 单账户使用可完全忽略本节：不传 `account_name` 即可，行为与之前版本一致。

### 获取操作状态

查询操作执行状态（非阻塞快照）。

```http
GET /api/v1/operations/{operation_id}/status
```

**响应示例**（统一信封，未到终态时 `success` 为 `null`、`data` 为 `null`）:
```json
{
  "success": null,
  "status": "running",
  "message": "",
  "error_code": null,
  "data": null,
  "timestamp": "2026-08-22 06:46:56"
}
```

**状态值**:

- `queued`: 排队中
- `running`: 执行中
- `completed`: 成功
- `failed`: 失败
- `cancelled`: 已取消（排队中被取消，未执行）

> **注意**：操作完成记录在内存中保留 3 小时，超时后查询将返回 404。

> **执行硬超时**：单个操作执行超过 `queue.operation_timeout`（默认 10 秒，见
> 配置模板）时，以 `failed` + `timeout` 终态收尾并**自动断开同花顺连接**
> （界面卡死保护，队列不阻塞），后续操作将快速失败；恢复交易客户端后调用
> `/api/v1/system/reconnect` 重连即可恢复服务。

### 获取操作结果

阻塞等待并获取操作终态结果，响应即统一信封（业务数据直接在 `data`，无双层嵌套）。

```http
GET /api/v1/operations/{operation_id}/result
```

**查询参数**:
- `timeout`: 超时时间（秒），可选，不传则阻塞等待

**状态码语义**:

- `200`: 操作已到终态，响应体为统一信封
- `404`: 操作不存在（ID 错误或结果已超过 3 小时被淘汰），`error_code: not_found`
- `408`: 等待超时但操作仍在排队/执行中（**请勿重复提交**），响应体带当前 `status`

**响应示例**:
```json
{
  "success": true,
  "status": "completed",
  "message": "成功提交600000的买入委托，耗时2.31秒",
  "error_code": null,
  "data": {
    "stock_code": "600000",
    "price": 10.5,
    "quantity": 100
  },
  "timestamp": "2026-08-22 06:46:56"
}
```

失败时 `success` 为 `false` 且 `error_code` 标明原因（见[错误码](#统一响应信封)）。

### 取消操作

取消排队中的操作（已开始执行的操作无法取消）。

```http
DELETE /api/v1/operations/{operation_id}
```

**响应示例**:
```json
{
  "success": true,
  "status": "cancelled",
  "message": "操作已取消",
  "error_code": null,
  "data": null,
  "timestamp": "2026-08-22 06:46:56"
}
```

### 获取可用操作列表

获取所有已加载的操作（含参数与结果 schema）。

```http
GET /api/v1/operations/
```

**响应示例**:
```json
{
  "success": true,
  "status": null,
  "message": "查询成功",
  "error_code": null,
  "data": {
    "operations": {
      "buy": {
        "name": "buy",
        "description": "买入股票",
        "parameters": {
          "properties": {
            "stock_code": {"pattern": "^\\d{6}$", "type": "string"},
            "price": {"maximum": 10000.0, "exclusiveMinimum": 0.0, "type": "number"},
            "quantity": {"exclusiveMinimum": 0.0, "type": "integer"}
          },
          "required": ["stock_code", "price", "quantity"],
          "type": "object"
        },
        "result_schema": {"properties": {"stock_code": {"type": "string"}, "...": {}}, "type": "object"}
      }
    },
    "count": 18
  },
  "timestamp": "2026-08-22 06:46:56"
}
```

> OpenAPI/Swagger 中结果端点的 `data` 是无类型的（异步结果端点无法按操作类型化）。
> 各操作结果的机器可读契约以本端点返回的 `result_schema` 为准，人工可读版见下文各操作小节。

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
  "status": null,
  "message": "查询成功",
  "error_code": null,
  "data": {
    "queued_count": 0,
    "running_count": 0,
    "completed_count": 10,
    "total_success": 10,
    "total_failed": 0
  },
  "timestamp": "2026-08-22 06:46:56"
}
```

---

## 可用操作 {#available-operations}

共 18 个操作，分为交易类、查询类与账户类。每个操作的小节包含：

- **请求参数**：平铺在 `POST` 请求体中（`priority` 与 `account_name` 为所有
  操作共用的可选字段——后者 `account_switch` 除外——见
  [多账户支持](#多账户支持)，不再重复列出）
- **响应数据**：终态（`GET .../result` 返回 200）时 `data` 的字段定义；
  交易类为单个对象，查询类为记录列表（每行一个对象）

通用参数约束：

- `stock_code`：6 位数字字符串（正则 `^\d{6}$`）
- 手数规则：股票（非可转债）数量必须是 100 的倍数且不小于 100；
  可转债（11/12 开头）必须是 10 的倍数且不小于 10
- 限价委托与条件单的单笔委托金额（价格 × 数量）上限为 10,000,000 元

### buy - 买入股票 {#buy-买入股票}

```http
POST /api/v1/operations/buy
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码（6位数字） |
| price | number | 是 | 委托价格（元），大于 0 且不超过 10000 |
| quantity | integer | 是 | 买入数量（股），遵循手数规则 |

**响应数据**（`data`，对象）:

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 股票代码 |
| price | number | 委托价格（元） |
| quantity | integer | 委托数量（股） |

**响应示例**（`GET .../result` 终态）:
```json
{
  "success": true,
  "status": "completed",
  "message": "成功提交600000的买入委托，耗时2.31秒",
  "error_code": null,
  "data": {"stock_code": "600000", "price": 10.5, "quantity": 100},
  "timestamp": "2026-08-22 06:46:56"
}
```

### sell - 卖出股票

```http
POST /api/v1/operations/sell
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码（6位数字） |
| price | number | 是 | 委托价格（元），大于 0 且不超过 10000 |
| quantity | integer | 是 | 卖出数量（股），遵循手数规则 |

**响应数据**（`data`，对象）: 同 [buy](#buy-买入股票)，
`stock_code` / `price` / `quantity`。

### market_buy - 市价买入 {#market_buy-市价买入}

以市价方式买入股票，无需指定价格，通过成交策略决定成交方式。

```http
POST /api/v1/operations/market_buy
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码（6位数字） |
| quantity | integer | 是 | 买入数量（股），遵循手数规则 |
| execution_strategy | integer | 否 | 成交策略（见下表），默认 3 |

**成交策略**:

| 值 | 策略名称 | 说明 |
|----|----------|------|
| 1 | 对手方最优 | 以对手方最优价格成交 |
| 2 | 本方最优 | 以本方最优价格成交 |
| 3 | 五档即成剩撤 | 逐档成交，剩余撤销（默认） |
| 4 | 即成剩撤 | 立即成交，剩余撤销 |
| 5 | 全额成交或撤 | 全部成交或不成交 |
| 6 | 五档即成剩转限 | 逐档成交，剩余转限价单 |

**响应数据**（`data`，对象）:

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 股票代码 |
| quantity | integer | 委托数量（股） |
| strategy | string | 实际使用的成交策略名称（请求策略不支持时为兜底策略「五档即成剩撤」） |

> **注意**：并不是所有类型的标的都支持市价交易。且支持市价交易的标的，可用的成交策略也不总是有以上 6 种。如果设置了该标的不支持的成交策略，系统会自动使用默认策略「五档即成剩撤」进行提交，实际使用的策略以 `strategy` 字段返回为准。

### market_sell - 市价卖出

以市价方式卖出股票，无需指定价格，通过成交策略决定成交方式。

```http
POST /api/v1/operations/market_sell
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码（6位数字） |
| quantity | integer | 是 | 卖出数量（股），遵循手数规则 |
| execution_strategy | integer | 否 | 成交策略（同 [market_buy](#market_buy-市价买入)），默认 3 |

**响应数据**（`data`，对象）: 同 [market_buy](#market_buy-市价买入)，
`stock_code` / `quantity` / `strategy`。

> **注意**：同 market_buy，并不是所有类型的标的都支持市价交易，且可用成交策略数量因标的而异。如果设置了不支持的策略，系统会自动使用「五档即成剩撤」提交。

### order_cancel - 撤单

```http
POST /api/v1/operations/order_cancel
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 否 | 股票代码（6位数字），不指定则针对全部委托 |
| cancel_type | string | 否 | 撤单类型：all(全部)/buy(买入)/sell(卖出)，默认 all |

**响应数据**（`data`，对象）:

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string \| null | 目标股票代码，`null` 表示全部委托 |
| cancel_type | string | 撤单类型：all / buy / sell |
| cancelled_count | integer | 撤销的委托笔数 |

### condition_buy - 条件买入 {#condition_buy-条件买入}

设置条件买入单，当股价达到目标价格时自动触发买入。

```http
POST /api/v1/operations/condition_buy
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码（6位数字） |
| target_price | number | 是 | 触发价格（元），大于 0 且不超过 10000 |
| quantity | integer | 是 | 买入数量（股），遵循手数规则 |
| expire_days | integer | 否 | 策略有效期（自然日），可选 1/3/5/10/20/30，默认 30 |

**响应数据**（`data`，对象）:

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 股票代码 |
| target_price | number | 触发价格（元） |
| quantity | integer | 委托数量（股） |
| expire_days | integer | 策略有效期（自然日） |

**响应示例**（`GET .../result` 终态）:
```json
{
  "success": true,
  "status": "completed",
  "message": "执行600000的条件买入成功，耗时2.05秒",
  "error_code": null,
  "data": {"stock_code": "600000", "target_price": 10.5, "quantity": 100, "expire_days": 30},
  "timestamp": "2026-08-22 06:46:56"
}
```

### condition_sell - 条件卖出

设置条件卖出单，当股价达到目标价格时自动触发卖出。

```http
POST /api/v1/operations/condition_sell
```

**请求参数**: 同 [condition_buy](#condition_buy-条件买入)（`target_price` 为卖出触发价格）。

**响应数据**（`data`，对象）: 同 [condition_buy](#condition_buy-条件买入)。

### condition_order_cancel - 条件单删除

删除指定的条件单。

```http
POST /api/v1/operations/condition_order_cancel
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 否 | 股票代码（6位数字），不指定则删除全部条件单 |
| order_type | string | 否 | 订单类型：买入/卖出，不指定则不限 |

**响应数据**（`data`，对象）:

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string \| null | 目标股票代码，`null` 表示全部条件单 |
| order_type | string \| null | 订单类型（买入/卖出），`null` 表示不限 |
| deleted_count | integer | 删除的条件单数量 |

**响应示例**（`GET .../result` 终态）:
```json
{
  "success": true,
  "status": "completed",
  "message": "条件单删除成功，删除1条记录，耗时1.54秒",
  "error_code": null,
  "data": {"stock_code": "600000", "order_type": "买入", "deleted_count": 1},
  "timestamp": "2026-08-22 06:46:56"
}
```

### stop_loss_profit - 止盈止损

为持仓股票设置止盈止损策略，当价格达到止盈或止损条件时自动触发卖出。

```http
POST /api/v1/operations/stop_loss_profit
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码（6位数字） |
| stop_loss_percent | number | 是 | 止损百分比（如 3 表示 3%），大于 0 且不超过 100 |
| stop_profit_percent | number | 是 | 止盈百分比（如 5 表示 5%），大于 0 且不超过 100 |
| quantity | integer | 否 | 卖出数量（股），遵循手数规则；不指定则使用全部可卖持仓 |
| expire_days | integer | 否 | 策略有效期（自然日），可选 1/3/5/10/20/30，默认 30 |

**响应数据**（`data`，对象）:

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 股票代码 |
| stop_loss_percent | number | 止损百分比（如 3 表示 3%） |
| stop_profit_percent | number | 止盈百分比（如 5 表示 5%） |
| quantity | integer | 委托数量（股）；请求未指定时为解析到的全部可卖数量 |
| expire_days | integer | 策略有效期（自然日） |

> **注意**：止盈百分比必须大于止损百分比。quantity 参数建议指定，因为受 T+1 限制，当天买入的股票如果不指定数量无法设置止盈止损。

**响应示例**（`GET .../result` 终态）:
```json
{
  "success": true,
  "status": "completed",
  "message": "执行600000的止盈止损单成功，耗时2.30秒",
  "error_code": null,
  "data": {
    "stock_code": "600000",
    "stop_loss_percent": 3.0,
    "stop_profit_percent": 5.0,
    "quantity": 100,
    "expire_days": 30
  },
  "timestamp": "2026-08-22 06:46:56"
}
```

### reverse_repo_buy - 国债逆回购购买

```http
POST /api/v1/operations/reverse_repo_buy
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| market | string | 是 | 交易市场：上海/深圳 |
| time_range | string | 是 | 回购期限：1天期/2天期/3天期/4天期/7天期 |
| amount | integer | 是 | 出借金额（元），必须是 1000 的倍数 |

**响应数据**（`data`，对象）:

| 字段 | 类型 | 说明 |
|------|------|------|
| market | string | 交易市场 |
| time_range | string | 回购期限 |
| amount | integer | 出借金额（元） |
| annual_rate | number | 成交年化利率（百分数值，如 2.5 表示 2.5%） |

**响应示例**（`GET .../result` 终态）:
```json
{
  "success": true,
  "status": "completed",
  "message": "国债逆回购操作成功，成功出借:10000 元，年化利率为：2.50%，耗时1.23秒",
  "error_code": null,
  "data": {"market": "上海", "time_range": "1天期", "amount": 10000, "annual_rate": 2.5},
  "timestamp": "2026-08-22 06:46:56"
}
```

### holding_query - 持仓查询

```http
POST /api/v1/operations/holding_query
```

**请求参数**: 无。

**响应数据**（`data`，记录列表，每行字段如下；数值型字段无该项业务时为 `null`）:

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 证券代码 |
| stock_name | string | 证券名称 |
| quantity | integer \| null | 持仓数量（股） |
| available_quantity | integer \| null | 可用数量（股） |
| frozen_quantity | integer \| null | 冻结数量（股） |
| cost_price | number \| null | 参考成本价（元） |
| current_price | number \| null | 当前价（元） |
| floating_profit | number \| null | 浮动盈亏（元） |
| profit_ratio | number \| null | 盈亏比例（%，如 1.76 表示 1.76%） |
| daily_profit | number \| null | 当日盈亏（元） |
| daily_profit_ratio | number \| null | 当日盈亏比（%） |
| market_value | number \| null | 最新市值（元） |
| position_ratio | number \| null | 仓位占比（%） |
| daily_bought | integer \| null | 当日买入（股） |
| daily_sold | integer \| null | 当日卖出（股） |
| market | string | 交易市场 |

### funds_query - 资金查询

```http
POST /api/v1/operations/funds_query
```

**请求参数**: 无。

**响应数据**（`data`，对象；单位元，数值型，无该项业务时为 `null`）:

| 字段 | 类型 | 说明 |
|------|------|------|
| balance | number \| null | 资金余额 |
| frozen_amount | number \| null | 冻结金额 |
| market_value | number \| null | 股票市值 |
| total_assets | number \| null | 总资产 |
| available_amount | number \| null | 可用金额 |
| withdrawable_amount | number \| null | 可取金额 |
| holding_profit | number \| null | 持仓盈亏 |
| daily_profit | number \| null | 当日盈亏 |
| daily_profit_ratio | number \| null | 当日盈亏比（%，如 0.57 表示 0.57%） |

**响应示例**（`GET .../result` 终态）:
```json
{
  "success": true,
  "status": "completed",
  "message": "资金查询完成，耗时1.05秒",
  "error_code": null,
  "data": {
    "balance": 50000.0,
    "frozen_amount": 1050.0,
    "market_value": 48940.0,
    "total_assets": 100000.0,
    "available_amount": 48950.0,
    "withdrawable_amount": 48950.0,
    "holding_profit": 123.45,
    "daily_profit": 56.78,
    "daily_profit_ratio": 0.57
  },
  "timestamp": "2026-08-22 06:46:56"
}
```

### order_query - 委托查询 {#order_query-委托查询}

```http
POST /api/v1/operations/order_query
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 否 | 股票代码（6位数字），不指定则查询全部 |

**响应数据**（`data`，记录列表，每行字段如下；数值型字段无该项业务时为 `null`）:

| 字段 | 类型 | 说明 |
|------|------|------|
| order_time | string | 委托时间 |
| stock_code | string | 证券代码 |
| stock_name | string | 证券名称 |
| operation | string | 委托方向（买入/卖出） |
| remark | string | 备注 |
| quantity | integer \| null | 委托数量（股） |
| filled_quantity | integer \| null | 成交数量（股） |
| price | number \| null | 委托价格（元） |
| avg_fill_price | number \| null | 成交均价（元） |
| cancelled_quantity | integer \| null | 撤销数量（股） |
| contract_no | string | 合同编号 |
| market | string | 交易市场 |

### historical_commission_query - 历史委托查询

```http
POST /api/v1/operations/historical_commission_query
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 否 | 股票代码（6位数字），不指定则查询全部 |
| time_range | string | 否 | 查询时间范围：当日/近一周/近一月/近三月/近一年，默认当日 |

**响应数据**（`data`，记录列表）: 字段同 [order_query](#order_query-委托查询)，
每行另加 `order_date`（string，委托日期）。

### condition_order_query - 条件单查询

查询未触发的条件单信息。

```http
POST /api/v1/operations/condition_order_query
```

**请求参数**: 无。

**响应数据**（`data`，记录列表，每行字段如下；数值型字段无该项业务时为 `null`）:

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 状态 |
| condition_type | string | 条件类型 |
| direction | string | 方向（买入/卖出） |
| target | string | 监控标的 |
| trigger_condition | string | 触发条件 |
| latest_price | number \| null | 最新价（元） |
| change_ratio | number \| null | 涨幅（%，如 1.23 表示 1.23%） |
| order_detail | string | 委托单 |
| created_at | string | 创建时间 |
| monitor_cycle | string | 监控周期 |

**响应示例**（`GET .../result` 终态）:
```json
{
  "success": true,
  "status": "completed",
  "message": "条件单查询成功，共获取到2条数据，耗时1.89秒",
  "error_code": null,
  "data": [
    {
      "status": "未触发",
      "condition_type": "价格条件",
      "direction": "买入",
      "target": "浦发银行(600000)",
      "trigger_condition": "最新价小于等于10.50元",
      "latest_price": 10.62,
      "change_ratio": -0.56,
      "order_detail": "买入100股，限价10.50元",
      "created_at": "2026-08-21 09:31:00",
      "monitor_cycle": "30天"
    }
  ],
  "timestamp": "2026-08-22 06:46:56"
}
```

### reverse_repo_query - 国债逆回购查询

```http
POST /api/v1/operations/reverse_repo_query
```

**请求参数**: 无。

**响应数据**（`data`，记录列表，每行字段如下）:

| 字段 | 类型 | 说明 |
|------|------|------|
| market | string | 交易市场（上海/深圳） |
| term | string | 期限（如 1天期） |
| annual_rate | number \| null | 年化利率（百分数值，如 2.5 表示 2.5%） |

**响应示例**（`GET .../result` 终态）:
```json
{
  "success": true,
  "status": "completed",
  "message": "查询国债逆回购年化利率成功，耗时1.01秒",
  "error_code": null,
  "current_used_account": null,
  "data": [
    {"market": "上海", "term": "1天期", "annual_rate": 2.5},
    {"market": "深圳", "term": "1天期", "annual_rate": 2.45}
  ],
  "timestamp": "2026-08-22 06:46:56"
}
```

### account_query - 账户列表查询 {#account_query-账户列表查询}

获取客户端所有已登录账户（幂等：首次经 GUI 读取，此后复用缓存）。
**服务启动时会自动执行一次本操作**，完成账户列表与当前账户的缓存初始化。

```http
POST /api/v1/operations/account_query
```

**请求参数**: 无。

**响应数据**（`data`，对象）：

| 字段 | 类型 | 说明 |
|------|------|------|
| available_accounts | object[] | 客户端全部可用账户记录，每行字段见下表 |

> 当前使用账户在信封 `current_used_account`（见[统一响应信封](#统一响应信封)），不在 `data` 中。

`available_accounts` 每行字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| account_name | string | 账户名，即客户端下拉列表的完整展示名（如 平安证券-王\*明）；接口 `account_name` 参数的取值来源 |
| account_index | integer | 账户序号（客户端列表位置，切换的定位依据） |

### account_switch - 账户切换

切换当前交易账户，执行逻辑：

1. 目标账户不在已缓存账户列表中（含列表未初始化）→ `client_rejected` 失败
2. 目标即当前账户 → 直接成功，不触 GUI（幂等）
3. 其余情况：向主窗口发送 `Alt + 账户序号` 完成切换，成功后刷新缓存

```http
POST /api/v1/operations/account_switch
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| account_name | string | 是 | 目标账户名（完整展示名，取值见 [account_query](#account_query-账户列表查询) 返回） |

**响应数据**（`data`，对象）：

| 字段 | 类型 | 说明 |
|------|------|------|
| previous_used_account | string \| null | 切换前使用的账户（此前未确认过为 `null`） |

> 切换后使用的账户在信封 `current_used_account`。

> 注意 `account_switch` 的 `account_name` 是**业务参数**（切换目标），该操作
> 不接受 `account_name` 执行指令。切换后想让后续操作稳定落在该账户，请直接
> 给后续操作显式传 `account_name`（见[多账户支持](#多账户支持)）。

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
        "stock_code": "600000",
        "price": 10.50,
        "quantity": 100,
        "priority": 5
    }
)
operation_id = response.json()["data"]["operation_id"]

# 阻塞等待终态结果（业务数据直接在 data）
result = requests.get(
    f"{base_url}/api/v1/operations/{operation_id}/result",
    headers=headers,  # 如果配置了 API Key
    params={"timeout": 30}
).json()
if result["success"]:
    print(result["data"]["stock_code"], result["data"]["quantity"])

# 查询持仓
response = requests.post(
    f"{base_url}/api/v1/operations/holding_query",
    headers=headers,  # 如果配置了 API Key
    json={}
)

# 多账户：显式指定 account_name，操作必然落在该账户（切换+执行原子完成）
response = requests.post(
    f"{base_url}/api/v1/operations/funds_query",
    headers=headers,
    json={"account_name": "模拟账户"}
)
# 终态结果携带 current_used_account，可核对操作实际落在的账户
# result["current_used_account"] == "模拟账户"
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
  "stock_code": "600000",
  "price": 10.50,
  "quantity": 100
  }'

# 查询持仓（带认证）
curl -X POST http://127.0.0.1:7648/api/v1/operations/holding_query \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{}'

# 多账户：先查账户列表，再显式指定账户执行操作（必然落在该账户）
curl -X POST http://127.0.0.1:7648/api/v1/operations/account_query \
  -H "Content-Type: application/json" -d '{}'
curl -X POST http://127.0.0.1:7648/api/v1/operations/funds_query \
  -H "Content-Type: application/json" \
  -d '{"account_name": "模拟账户"}'
```

---

## 交互式文档

启动服务后，访问以下地址查看完整的交互式 API 文档（每个操作的请求参数与
Result 模型均由 Pydantic 自动生成契约）：

- **Swagger UI**: `http://127.0.0.1:7648/docs`
- **ReDoc**: `http://127.0.0.1:7648/redoc`
