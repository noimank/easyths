# 开发指南

## 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/noimank/easyths.git
cd easyths

# 安装开发依赖（包含服务端依赖和开发工具）
uv sync --all-extras

# 安装 pre-commit 质量门禁（ruff + mypy + pytest）
uv run pre-commit install

# 运行单元测试（默认只跑 test/unit，不会触发真实交易）
pytest

# 代码检查与格式化
ruff check easyths/
ruff format easyths/
```

## 编写新操作

### 操作插件目录

所有操作插件位于 `easyths/operations/` 目录下。项目会**自动加载**该目录下的所有插件（以 `_` 开头的模块除外），无需手动注册。

### 操作契约

操作契约全部为类属性：`operation_name`（注册名，即对外 API 路径）、
`description`（文档描述）、`Params`（参数模型）、`Result`（结果模型），
外加核心方法 `execute(params)`。**Params / Result 模型即契约**：
REST 提交时的参数校验（非法/未知参数直接 422）、接口文档
（OpenAPI 与 `GET /api/v1/operations/` 的 `parameters` / `result_schema`）
均由模型自动生成，无需手写 schema。

- 参数模型定义在 `easyths/operations/params.py`，继承 `OperationParams`
- 结果模型定义在 `easyths/operations/results.py`，继承 `ResultModel`
  （表格行模型只声明英文 snake_case 字段，客户端数值文本由 `Num` / `Int` /
  `Text` 类型自动清洗，`--` 等占位值转为 `null`）

```python
from easyths.core import BaseOperation
from easyths.models.operations import EmptyParams, OperationResult
from easyths.operations.results import FundsResult


class MyQueryOperation(BaseOperation[EmptyParams]):
    """我的查询操作"""

    operation_name = "my_query"          # 注册名（对外 API 路径）
    description = "查询我的数据"          # 文档描述
    Params = EmptyParams                 # 参数模型（校验+文档唯一来源）
    Result = FundsResult                 # 结果模型（构造+文档唯一来源）

    def execute(self, params: EmptyParams) -> OperationResult:
        ...
```

### 执行流水线

`run()` 由基类提供，业务代码无需书写兜底 try/except：

1. **参数校验**：pydantic 校验原始参数字典，失败映射为 `invalid_params`
2. **pre_execute**：检查同花顺连接、聚焦主窗口、清理残留弹窗（失败映射为 `not_connected`）
3. **execute**：核心业务逻辑；未捕获异常兜底为 `ui_error`

`execute` 内用 `_ok()` / `_fail()` 构造结果：

```python
def execute(self, params: MyParams) -> OperationResult:
    start_time = time.time()
    # ... GUI 自动化逻辑 ...

    # 业务拒绝（弹窗提示、资金不足等）→ CLIENT_REJECTED
    if rejected:
        return self._fail(message, ErrorCode.CLIENT_REJECTED)

    # 成功：data 必须是 Result 模型的 model_dump()
    return self._ok(
        data=MyResult(field=value).model_dump(),
        message=f"查询完成，耗时{time.time() - start_time:.2f}秒",
    )
```

> `data` 的形状必须与 `Result` 模型一致（查询类操作为
> `[RowModel(...).model_dump(), ...]` 记录列表），这是对外接口契约。

### 可选钩子

- **pre_execute()** - 执行前预处理（默认：连接检查、设置焦点、关闭弹窗），可按需重写

### 带参数的操作示例

```python
# easyths/operations/params.py 中定义参数模型
class MyQueryParams(StockQueryParams):
    """我的查询参数"""
    top_n: Annotated[int, Field(gt=0, le=100, description="返回条数")] = 10


# easyths/operations/results.py 中定义行模型
class MyRow(ResultModel):
    """我的查询行"""
    stock_code: Text = Field(description="证券代码")
    value: Num = Field(description="数值（无该项业务时为 null）")


# easyths/operations/my_query.py 中实现操作
class MyQueryOperation(BaseOperation[MyQueryParams]):
    operation_name = "my_query"
    description = "查询我的数据"
    Params = MyQueryParams
    Result = MyRow

    def parse_my_row(self, record: dict[str, Any]) -> MyRow:
        """剪贴板记录 → 行模型的显式装配（列名差异在此适配）"""
        return MyRow(stock_code=record["证券代码"], value=record["数值"])

    def execute(self, params: MyQueryParams) -> OperationResult:
        start_time = time.time()
        self.switch_left_menus("查询[F4]", "资金股票")
        # ... 定位表格控件、复制到剪贴板、text2df 解析 ...
        table_df = text2df(self.get_clipboard_data())
        rows = [self.parse_my_row(r).model_dump() for r in df_to_records(table_df)]
        return self._ok(
            data=rows,
            message=f"查询完成，耗时{time.time() - start_time:.2f}秒",
        )
```

注册后即自动获得 REST 端点 `POST /api/v1/operations/my_query`、
OpenAPI 文档以及 `/operations/` 列表中的 schema；如需 MCP 工具，
在 `easyths/api/routes/mcp_server.py` 中按现有工具样式添加。

## 控件定位 - 性能关键

> ⚠️ **重要**：项目**禁止使用** `child_window()` 方法，速度太慢（单次调用可达 2s）。必须使用 `children()` 方法手动解析控件树。

### 为什么禁止 child_window()

`child_window()` 内部会遍历整个控件树进行查找，性能极差。使用 `children()` 直接获取子控件集合后再筛选，速度可提升 3-10 倍。

### 使用 get_control_with_children()

基类提供了 `get_control_with_children()` 方法，这是项目推荐的控件定位方式：

```python
# 获取指定条件的控件
control = self.get_control_with_children(
    parent_control,
    class_name="Edit",           # 控件类名
    control_type="Edit",         # 控件类型
    title="标题",                 # 控件标题（精确匹配）
    title_contains="委托",        # 控件标题（子串包含匹配）
    auto_id="1032"               # 自动化 ID（重要）
)
```

### 支持的筛选字段

内置筛选字段（由 `children()` 直接支持）：

- `control_type` - 控件类型（Window, Button, Edit, Text, Pane 等）
- `class_name` - 控件类名
- `title` - 控件标题（精确匹配）

手动筛选的字段：

- `auto_id` - 自动化 ID（UIA 不直接支持，通过手动筛选实现）
- `title_contains` - 标题子串包含匹配（手动筛选）

> **注意**：`control_id` 字段在 UIA 后端中**不支持**，请使用 `auto_id`。

### 控件定位示例

```python
# 获取主窗口
main_window = self.get_main_window(wrapper_obj=True)

# 获取面板
main_panel = main_window.children(control_type="Pane")[0]

# 获取编辑框并输入内容
edit = self.get_control_with_children(main_panel, control_type="Edit", auto_id="1032")
edit.type_keys("内容")

# 获取按钮并点击
button = self.get_control_with_children(main_panel, control_type="Button", auto_id="2")
button.click()
```

### 通用辅助方法

```python
# 切换左侧菜单
self.switch_left_menus("查询[F4]", "资金股票")

# 获取主窗口
main_window = self.get_main_window(wrapper_obj=True)

# 关闭弹窗
self.close_pop_dialog()

# 等待弹窗
self.wait_for_pop_dialog(timeout=1.0)

# 睡眠
self.sleep(0.1)

# 检查弹窗是否存在
if self.is_exist_pop_dialog():
    # 处理弹窗
    pass
```

## 控件定位辅助工具

使用以下工具辅助控件定位开发：

### Accessibility Insights

- **下载地址**: https://accessibilityinsights.io/
- **用途**: 可视化查看控件树结构、获取控件的 Automation ID

### Inspect (Windows SDK)

- **用途**: 微软官方的辅助工具，查看控件属性

### 使用方法

1. 打开同花顺交易客户端
2. 启动 Accessibility Insights 或 Inspect
3. 鼠标悬停在目标控件上
4. 查看控件属性，重点关注：
   - **Automation Id** (auto_id)
   - **Control Type** (control_type)
   - **Class Name** (class_name)
   - **Name** (title)

## 完整示例

参考 `easyths/operations/buy.py`（交易类：单对象结果）、
`easyths/operations/funds_query.py`（查询类：单对象结果）和
`easyths/operations/holding_query.py`（查询类：表格行列表结果，
含实盘/模拟账户列名差异适配）获取完整实现。

## 项目结构

```
easyths/
├── easyths/
│   ├── __init__.py
│   ├── main.py                      # 主入口（FastAPI 服务端）
│   ├── trade_client.py              # Python Client SDK
│   ├── api/                         # FastAPI 路由和中间件
│   │   ├── app.py                   # FastAPI 应用配置
│   │   ├── responses.py             # 统一信封响应工具
│   │   ├── dependencies/            # API 依赖项
│   │   │   ├── common.py            # 通用依赖
│   │   │   └── __init__.py
│   │   ├── middleware/              # 中间件
│   │   │   ├── api_key_auth.py      # API Key 认证
│   │   │   ├── ip_whitelist.py      # IP 白名单
│   │   │   ├── logging.py           # 请求日志
│   │   │   ├── rate_limit.py        # 速率限制
│   │   │   └── __init__.py
│   │   └── routes/                  # API 路由
│   │       ├── operations.py        # 操作执行接口（按注册表生成）
│   │       ├── queue.py             # 队列管理接口
│   │       ├── system.py            # 系统状态接口
│   │       ├── mcp_server.py        # MCP 服务接口
│   │       └── __init__.py
│   ├── assets/                      # 资源文件
│   ├── core/                        # 核心组件
│   │   ├── __init__.py
│   │   ├── base_operation.py        # BaseOperation 基类与操作注册表
│   │   ├── operation_queue.py       # 操作队列（后台线程）
│   │   └── tonghuashun_automator.py # UI 自动化（pywinauto）
│   ├── models/                      # Pydantic 数据模型
│   │   ├── __init__.py
│   │   └── operations.py            # 状态/错误码/统一信封/操作与参数基类
│   ├── operations/                  # 交易操作插件（自动发现）
│   │   ├── params.py                # 全部操作的参数契约
│   │   ├── results.py               # 全部操作的结果契约
│   │   ├── buy.py                   # 买入股票
│   │   ├── sell.py                  # 卖出股票
│   │   ├── market_buy.py            # 市价买入
│   │   ├── market_sell.py           # 市价卖出
│   │   ├── condition_buy.py         # 条件买入
│   │   ├── condition_sell.py        # 条件卖出
│   │   ├── condition_order_query.py # 条件单查询
│   │   ├── condition_order_cancel.py # 条件单删除
│   │   ├── funds_query.py           # 资金查询
│   │   ├── holding_query.py         # 持仓查询
│   │   ├── order_query.py           # 委托查询
│   │   ├── order_cancel.py          # 撤单
│   │   ├── historical_commission_query.py  # 历史委托查询
│   │   ├── reverse_repo_buy.py      # 国债逆回购购买
│   │   ├── reverse_repo_query.py    # 国债逆回购查询
│   │   └── stop_loss_profit.py      # 止盈止损
│   └── utils/                       # 工具函数
│       ├── __init__.py
│       ├── captcha_ocr.py           # 验证码 OCR
│       ├── config.py                # 配置加载
│       ├── execution_strategy.py    # 市价成交策略匹配
│       ├── logger.py                # 日志工具
│       ├── screen_capture.py        # 屏幕截图
│       └── table_text_handler.py    # 表格文本处理
├── docs/                            # 项目文档
├── test/                            # 测试文件
│   ├── unit/                        # 单元测试（pytest 默认运行）
│   └── integration/                 # 集成测试（触发真实交易，需显式指定路径）
└── pyproject.toml                   # 项目配置
```

### 目录说明

| 目录 | 说明 |
|------|------|
| `easyths/api/` | FastAPI 服务端，包含路由、中间件和依赖项 |
| `easyths/api/routes/mcp_server.py` | MCP (Model Context Protocol) 服务接口，支持 AI 助手集成 |
| `easyths/core/` | 核心组件，操作队列和 UI 自动化 |
| `easyths/models/` | 状态/错误码/统一响应信封等基础数据模型 |
| `easyths/operations/` | 交易操作插件与参数/结果契约，自动发现并注册 |
| `easyths/utils/` | 工具函数和辅助模块 |
| `easyths/trade_client.py` | Python Client SDK，用于远程调用 API |
| `easyths/main.py` | 服务端主入口 |

### MCP 服务

项目支持 [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) 协议，允许 AI 助手（如 Claude Desktop）直接调用同花顺交易功能。

- **服务端点**: `/api/mcp-server/`
- **协议类型**: 支持 `http`、`streamable-http`、`sse` 三种传输协议
- **详细文档**: [MCP 服务文档](../getting-started/mcp-service.md)

## 下一步

[贡献指南](contributing.md)
