# MCP 服务

EasyTHS 支持 [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) 协议，允许 AI 助手（如 Claude Desktop）直接调用同花顺交易功能。

## 什么是 MCP？

MCP 是一个开放协议，用于连接 AI 助手与外部系统。通过 MCP，你可以让 Claude、ChatGPT 等 AI 助手直接执行股票交易操作。

## 传输协议

EasyTHS MCP 服务支持三种传输协议：

| 协议 | 说明 | 推荐场景 |
|------|------|----------|
| **streamable-http** | 基于 HTTP 的流式传输，支持断线重连 | **推荐用于 Web 部署** |
| **http** | 传统 HTTP 传输，简单可靠 | 兼容旧版客户端 |
| **sse** | Server-Sent Events，单向推送 | 已弃用，不推荐使用 |

### 选择建议

- **Web 部署/远程访问**：使用 `streamable-http`（默认）
- **本地开发测试**：可使用 `http`
- **Claude Desktop 集成**：使用 `http` 或 `streamable-http`

## 配置 MCP 服务

### 修改配置文件

在 `config.toml` 中配置 MCP 传输类型：

```toml
[api]
# MCP 服务器传输类型
mcp_server_type = "streamable-http"  # 可选: http, streamable-http, sse

# API 密钥（MCP 客户端需要认证时启用）
key = "your-api-key-here"

# 其他配置...
host = "0.0.0.0"
port = 7648
```

## 服务端点

MCP 服务默认运行在以下路径：

```
http://localhost:7648/api/mcp-server/
```

完整的端点 URL 格式：

```
http://{host}:{port}/api/mcp-server/
```

## 使用 MCP 客户端连接

### Python 客户端

```python
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
import asyncio

async def main():
    # 基础连接
    transport = StreamableHttpTransport(
        url="http://localhost:7648/api/mcp-server/"
    )
    async with Client(transport) as client:
        # 调用工具
        result = await client.call_tool("funds_query", {})
        print(result)

asyncio.run(main())
```

### 带 API Key 认证的连接

```python
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

async def main():
    transport = StreamableHttpTransport(
        url="http://localhost:7648/api/mcp-server/",
        headers={
            "Authorization": "Bearer your-api-key-here"  # Bearer 和 key 之间只有一个空格
        }
    )
    async with Client(transport) as client:
        # 列出可用工具
        tools = await client.list_tools()
        for tool in tools:
            print(f"- {tool.name}: {tool.description}")

asyncio.run(main())
```

> **注意**：`Authorization` header 格式为 `Bearer <api-key>`，**`Bearer` 和 API key 之间有且仅有一个空格**，不要多加或遗漏空格。

### Claude Desktop 配置

> **先区分两个产品**：Claude Desktop（桌面应用）≠ Claude Code（CLI 命令行工具）。
> Claude Code **原生支持远程 HTTP MCP 直连并携带认证头**，无需任何桥接，配置见下一节；
> 以下限制仅针对**桌面应用**。

Claude Desktop 的配置文件不支持远程 HTTP 服务器的自定义认证头（官方已知限制，
[claude-ai-mcp#120](https://github.com/anthropics/claude-ai-mcp/issues/120)）。
启用 API Key 时需借助 [`mcp-remote`](https://github.com/geelen/mcp-remote) 桥接
（依赖 Node.js，`npx` 首次运行自动下载）。

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "easyths": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://localhost:7648/api/mcp-server/",
        "--header",
        "Authorization: Bearer your-api-key-here"
      ]
    }
  }
}
```

> **注意**：
> - `Bearer` 和 API key 之间有且仅有一个空格
> - 未启用 API Key 认证时，去掉 `"--header"` 与其后的 `"Authorization: ..."` 两行即可
> - API Key 以明文存放在配置文件中，注意文件权限

### 其他支持 HTTP MCP 的客户端

原生支持自定义请求头的客户端无需桥接、直连即可：

**Cursor**（`.cursor/mcp.json`）：

```json
{
  "mcpServers": {
    "easyths": {
      "url": "http://localhost:7648/api/mcp-server/",
      "headers": {
        "Authorization": "Bearer your-api-key-here"
      }
    }
  }
}
```

**Claude Code**：

```bash
claude mcp add --transport http easyths http://localhost:7648/api/mcp-server/ \
  --header "Authorization: Bearer your-api-key-here"
```

## 可用工具

MCP 服务提供以下交易工具：

### 交易操作

| 工具名 | 说明 |
|--------|------|
| `buy` | 买入股票 |
| `sell` | 卖出股票 |
| `market_buy` | 市价买入股票（无需指定价格） |
| `market_sell` | 市价卖出股票（无需指定价格） |

### 查询操作

| 工具名 | 说明 |
|--------|------|
| `holding_query` | 查询股票持仓 |
| `funds_query` | 查询账户资金 |
| `order_query` | 查询委托订单 |
| `historical_commission_query` | 查询历史委托 |

### 委托管理

| 工具名 | 说明 |
|--------|------|
| `order_cancel` | 撤销委托订单 |

### 条件单

| 工具名 | 说明 |
|--------|------|
| `condition_buy` | 条件买入 |
| `condition_sell` | 条件卖出 |
| `condition_order_query` | 查询条件单 |
| `condition_order_cancel` | 删除条件单 |

### 止损止盈

| 工具名 | 说明 |
|--------|------|
| `stop_loss_profit` | 设置止损止盈 |

### 国债逆回购

| 工具名 | 说明 |
|--------|------|
| `reverse_repo_buy` | 国债逆回购（出借资金） |
| `reverse_repo_query` | 查询国债逆回购利率 |

## 工具参数与返回格式

每个工具的入参与同名 REST 操作的请求参数一致，完整参数约束与
`data` 返回字段见 [API 文档 - 可用操作](api.md#available-operations)。

工具内部会提交操作并**同步等待终态结果**（最长 30 秒），返回统一信封并附带
`operation_id`：

```json
{
  "status": "completed",
  "success": true,
  "data": {"stock_code": "600000", "price": 10.5, "quantity": 100},
  "message": "成功提交600000的买入委托，耗时2.31秒",
  "error_code": null,
  "timestamp": "2026-08-22 06:46:56",
  "operation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

等待超时时返回 `success: false` 且 `error_code: "timeout"`，`message` 会明确区分：

- **操作仍在排队/执行中**：`status` 为当前状态，提示稍后重查，**请勿重复提交**（避免重复下单）
- **操作记录已失效**：`status` 为 null，可凭 `operation_id` 排查服务端日志

## 认证说明

### 启用 API Key 认证

如果配置文件中设置了 `api.key`，MCP 客户端需要在请求中提供认证信息：

```bash
# curl 示例
curl -X POST http://localhost:7648/api/mcp-server/ \
  -H "Authorization: Bearer your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

> **重要**：`Authorization` header 格式必须严格为 `Bearer <api-key>`，**`Bearer` 和 API key 之间有且仅有一个空格**。
>
> 常见错误示例：
> - ❌ `Beareryour-api-key-here`（缺少空格）
> - ❌ `Bearer  your-api-key-here`（多个空格）
> - ✅ `Bearer your-api-key-here`（正确）

### IP 白名单

如果启用了 IP 白名单（`api.ip_whitelist`），确保客户端 IP 在允许列表中：

```toml
[api]
ip_whitelist = "127.0.0.1,192.168.1.*"  # 仅允许本地和局域网
```

## 示例场景

### 场景 1：使用 AI 助手查询资金

```
你: 查询我的账户资金
AI: [调用 funds_query 工具]
    您的账户资金情况如下：
    - 总资产: ¥100,000
    - 可用金额: ¥50,000
    - 持仓市值: ¥50,000
```

### 场景 2：条件单交易

```
你: 当贵州茅台价格低于 1500 元时，买入 100 股
AI: [调用 condition_buy 工具]
    已创建条件单：
    - 股票: 贵州茅台 (600519)
    - 触发价格: ¥1500
    - 数量: 100 股
    - 有效期: 30 天
```

## 故障排查

### 问题：连接失败

1. 确认服务已启动：`curl http://localhost:7648/`
2. 检查端口配置：`[api] port = 7648`
3. 检查防火墙设置

### 问题：认证失败

1. 确认 API Key 配置正确
2. 检查请求头格式：`Authorization: Bearer <key>`
3. 查看服务日志获取详细错误信息

### 问题：工具调用失败

1. 确认同花顺客户端正在运行
2. 检查交易程序路径配置：`[trading] app_path`
3. 查看服务日志：默认 `C:/Users/你的用户名/easyths/log.txt`（可在 `[logging] file` 中自定义路径）

## 更多内容

- [API 服务](api.md)
- [基础用法](basic-usage.md)
- [常见问题](faq.md)
