# EasyTHS

**同花顺交易自动化系统** - 基于 Python 的同花顺客户端自动化交易工具。

## 适用人群

如果你需要：

- 🔸 **股票交易 API** - 为量化策略提供标准化的交易接口
- 🔸 **AI 助手集成** - 让 Claude Desktop 等 AI 助手直接执行交易操作
- 🔸 **低成本方案** - 无需购买昂贵的 QMT/miniQMT 等专业交易终端
- 🔸 **本地化部署** - 数据完全可控，适合对隐私有要求的个人开发者
- 🔸 **快速验证** - 快速搭建交易原型，验证策略想法

EasyTHS 是为你量身定制的轻量级解决方案。

## 特性

### 核心能力

- 🚀 **极速交易** - 深度优化自动化流程，压榨性能极限，提供极速稳定的交易体验
- 🖥️ **GUI 自动化** - 基于 pywinauto 的 Windows GUI 自动化
- 🌐 **RESTful API** - FastAPI 提供的高性能 HTTP API 接口
- 🤖 **MCP 支持** - 支持 Model Context Protocol，可被 AI 助手直接调用
- 📊 **数据管理** - 支持交易数据的记录和查询

### 生产级安全

- 🔑 **API Key 认证** - 支持 API Key 身份验证，防止未授权访问
- 🛡️ **IP 白名单** - 严格的 IP 白名单控制，限制访问来源
- 🌐 **CORS 跨域** - 可配置的跨域策略，灵活控制访问权限
- 🔒 **本地运行** - 数据完全本地化，不上传任何第三方服务器

### 相比 EasyTrader

[EasyTrader](https://github.com/shidenggui/easytrader) 是早期的同花顺自动化交易项目，EasyTHS 在其基础上做了全面升级：

- ⚡ **更完整的功能** - 支持更全面的交易操作，覆盖更多业务场景
- 🚀 **高并发支持** - 优化的并发处理能力，适合高频交易场景
- 🎯 **持续维护** - 活跃的开发和维护，快速响应问题

## 项目架构

### 整体设计

EasyTHS 采用分层架构设计，将系统职责清晰分离，确保代码的可维护性和可扩展性。

```
┌──────────────────────────────────────────────────────────────┐
│                         客户端层                         │
│  TradeClient - 远程调用客户端 (HTTP + Bearer Token)       │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                         API 层                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  FastAPI 路由                                      │  │
│  │  ├─ system.py     - 系统管理                        │  │
│  │  ├─ operations.py - 操作执行                        │  │
│  │  ├─ queue.py      - 队列管理                        │  │
│  │  └─ mcp_server.py - MCP 服务                        │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  中间件                                            │  │
│  │  ├─ API Key 认证                                   │  │
│  │  ├─ IP 白名单                                      │  │
│  │  ├─ 速率限制                                        │  │
│  │  └─ 请求日志                                        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                         核心层                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  OperationQueue - 优先级队列（后台线程串行执行）       │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  TonghuashunAutomator - 同花顺 GUI 自动化           │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  BaseOperation - 操作基类与插件注册机制               │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                       操作插件层                          │
│  buy.py | sell.py | market_buy.py | market_sell.py       │
│  condition_*.py | stop_loss_profit.py | order_*.py       │
│  holding_query.py | funds_query.py | reverse_repo_*.py   │
│  params.py（参数契约）| results.py（结果契约）           │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                       工具层                             │
│  config.py | captcha_ocr.py | screen_capture.py         │
│  table_text_handler.py | execution_strategy.py          │
└──────────────────────────────────────────────────────────────┘
```

### 核心设计思想

#### 1. 同步执行 + 异步 API 体验

- **操作层**：所有业务操作采用同步函数实现，简化代码逻辑
- **队列层**：后台线程串行处理所有操作，保证线程安全
- **API 层**：异步接口返回 operation_id，客户端可轮询查询结果

```
客户端请求 → API 立即返回 operation_id → 后台队列串行执行 → 客户端查询结果
```

#### 2. 插件化操作系统

- **BaseOperation**：操作契约全部为类属性 —— `operation_name`（注册名）、`description`（文档描述）、`Params`（参数模型）、`Result`（结果模型），外加核心方法 `execute(params)`
- **Params / Result 模型即契约**：REST 提交校验（非法/未知参数直接 422）、接口文档（OpenAPI 与 `/operations/` 列表）由模型自动生成
- **OperationRegistry**：自动扫描并注册 `operations/` 目录下的所有操作插件

```python
class BuyOperation(LimitOrderOperation):
    operation_name = "buy"          # 注册名（对外 API 路径）
    description = "买入股票"         # 文档描述
    Params = LimitOrderParams       # 参数模型（校验+文档唯一来源）
    Result = LimitOrderResult       # 结果模型（构造+文档唯一来源）

    def execute(self, params: LimitOrderParams) -> OperationResult: ...

# run() 完整流程：参数校验（pydantic）→ pre_execute（连接检查/清弹窗）→ execute
```

#### 3. 优先级队列调度

- **PriorityQueue**：基于优先级的任务调度（数字越大优先级越高）
- **串行执行**：单一后台线程保证 GUI 操作的线程安全
- **状态追踪**：QUEUED → RUNNING → COMPLETED / FAILED / CANCELLED

```python
# 提交操作（需要自定义优先级时使用通用方法）
operation_id = client.execute_operation(
    "buy", {"stock_code": "600000", "price": 10.50, "quantity": 100}, priority=5
)

# 查询状态
status = client.get_operation_status(operation_id)

# 获取结果（阻塞等待）
result = client.get_operation_result(operation_id, timeout=60)
```

#### 4. 性能优化策略

- **控件查找优化**：直接遍历子控件替代 `child_window()`，性能提升数倍
- **菜单切换优化**：精确定位 Tree 控件，从 2.2s 降至 0.7s
- **Wrapper 对象复用**：减少控件实例化开销，节省 0.3s+

```python
# 禁止使用 child_window()
# ❌ 慢速方式
control = parent.child_window(class_name="Edit", auto_id="2404")

# ✅ 快速方式
control = self.get_control_with_children(
    parent, class_name="Edit", auto_id="2404"
)
```

#### 5. 弹窗智能处理

- **自动检测**：识别多种弹窗类型（风险测评、验证码、失败提示等）
- **批量关闭**：`close_pop_dialog()` 自动清理所有弹窗
- **验证码识别**：集成 OCR 服务自动识别验证码

#### 6. 安全机制

- **API Key 认证**：Bearer Token 方式的 API 密钥验证
- **IP 白名单**：严格限制访问来源
- **速率限制**：防止接口滥用
- **本地化部署**：所有数据保留在本地，不上传第三方

### 目录结构

```
easyths/
├── __init__.py
├── main.py                      # 服务启动入口
├── trade_client.py              # 远程调用客户端 (TradeClient SDK)
├── api/                         # FastAPI 服务端
│   ├── app.py                   # FastAPI 应用配置
│   ├── responses.py             # 统一信封响应工具
│   ├── routes/                  # API 路由
│   │   ├── system.py           # 系统管理接口
│   │   ├── operations.py       # 操作执行接口
│   │   ├── queue.py            # 队列管理接口
│   │   └── mcp_server.py       # MCP 服务接口 (Model Context Protocol)
│   ├── middleware/              # 中间件
│   │   ├── api_key_auth.py     # API Key 认证
│   │   ├── ip_whitelist.py     # IP 白名单
│   │   ├── rate_limit.py       # 速率限制
│   │   └── logging.py          # 请求日志
│   └── dependencies/            # 依赖注入
│       └── common.py
├── core/                        # 核心组件
│   ├── tonghuashun_automator.py # 同花顺自动化器 (pywinauto)
│   ├── base_operation.py        # 操作基类与注册表
│   └── operation_queue.py       # 优先级操作队列
├── operations/                  # 操作插件 (自动发现)
│   ├── params.py                # 全部操作的参数契约（Pydantic 模型）
│   ├── results.py               # 全部操作的结果契约（Pydantic 模型）
│   ├── buy.py                   # 买入股票
│   ├── sell.py                  # 卖出股票
│   ├── market_buy.py            # 市价买入
│   ├── market_sell.py           # 市价卖出
│   ├── condition_buy.py         # 条件买入
│   ├── condition_sell.py        # 条件卖出
│   ├── stop_loss_profit.py      # 止盈止损
│   ├── condition_order_query.py # 条件单查询
│   ├── condition_order_cancel.py # 条件单删除
│   ├── order_cancel.py          # 撤单
│   ├── order_query.py           # 查委托
│   ├── holding_query.py         # 查持仓
│   ├── funds_query.py           # 查资金
│   ├── historical_commission_query.py  # 查历史委托
│   ├── reverse_repo_buy.py      # 国债逆回购购买
│   └── reverse_repo_query.py    # 国债逆回购查询
├── models/                      # 数据模型
│   └── operations.py            # 状态/错误码/统一信封/操作与参数基类
├── utils/                       # 工具模块
│   ├── config.py                # 配置管理
│   ├── captcha_ocr.py           # 验证码 OCR
│   ├── screen_capture.py        # 屏幕截图
│   ├── execution_strategy.py    # 市价成交策略匹配
│   ├── table_text_handler.py    # 表格文本处理
│   └── logger.py                # 日志配置
└── assets/                      # 资源文件
```

### 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| API 框架 | FastAPI | 高性能异步 Web 框架 |
| GUI 自动化 | pywinauto | Windows GUI 自动化 |
| 日志 | structlog | 结构化日志 |
| HTTP 客户端 | httpx | 现代异步 HTTP 客户端 |
| 数据验证 | Pydantic | 类型安全的数据验证 |
| 配置管理 | TOML | 人类可读的配置格式 |

## 快速开始

> **前置要求**
>
> 使用 EasyTHS 前，请确保：
>
> 1. 已安装同花顺远航版客户端 - [前往下载](https://download.10jqka.com.cn/)
> 2. 已按照 [同花顺客户端配置](getting-started/ths-client.md) 完成设置
> 3. 同花顺客户端正在运行中
>
> 否则 EasyTHS 将无法正常工作。

```bash
# 安装服务端
pip install easyths[server]

# 启动服务
easyths
```

## 命令行参数

EasyTHS 支持以下命令行参数：

| 参数 | 说明 |
|------|------|
| `--exe_path <path>` | 指定同花顺交易程序路径（优先级高于配置文件） |
| `--config <file>` | 指定 TOML 配置文件路径 |
| `--get_config` | 将示例配置文件复制到当前目录 |
| `--version, -v` | 显示版本信息 |
| `--help` | 显示帮助信息 |

### 使用示例

```bash
# 使用默认配置启动（自动检测同花顺远航版）
easyths

# 使用自定义配置文件启动
easyths --config my_config.toml

# 指定交易程序路径启动（免费版或其他版本）
easyths --exe_path "C:/同花顺/xiadan.exe"

# 生成示例配置文件
easyths --get_config

# 组合使用
easyths --config my_config.toml --exe_path "C:/同花顺/xiadan.exe"
```

## 文档

- [快速开始](getting-started/index.md)
- [基础用法](getting-started/basic-usage.md)
- [MCP 服务](getting-started/mcp-service.md) - AI 助手集成指南
- [API 文档](getting-started/api.md)
- [常见问题](getting-started/faq.md)

## 许可证

MIT License
