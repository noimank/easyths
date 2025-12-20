# 同花顺交易自动化系统

基于pywinauto的同花顺交易软件自动化项目，提供RESTful API接口，确保操作顺序和避免高并发下的操作序列错误。

## 项目特点

- **操作串行化**：所有GUI操作串行执行，避免并发冲突
- **事务一致性**：确保操作的原子性和一致性
- **高度可扩展**：采用插件化设计，便于添加新的自动化操作
- **错误恢复**：完整的错误处理和恢复机制
- **实时监控**：详细的日志记录和状态监控

## 系统架构

```
REST API Layer -> Request Queue -> Task Orchestrator -> Operation Serializer -> GUI Automation Layer -> Tonghuashun
```

### 核心设计理念

1. **TonghuashunAutomator**：纯粹的GUI控件操作层
   - 提供灵活的控件查找方法（支持class_name、title、control_index等多种组合）
   - 实现控件缓存机制，提高操作效率
   - 不包含任何业务逻辑

2. **Operation插件**：业务逻辑实现层
   - 使用automator提供的底层API组合完成具体业务
   - 自行管理控件资源定义
   - 处理业务规则和异常情况

## 快速开始

### 1. 安装uv (如果尚未安装)

```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或者使用 winget
winget install -e --id astral-sh.uv
```

### 2. 安装项目依赖

```bash
# 安装生产依赖
uv sync

# 或者安装包含开发依赖
uv sync --dev
```

### 3. 配置系统

编辑 `config/trading_config.yaml`，配置同花顺路径和其他参数：

```yaml
trading:
  app_path: "C:/同花顺/xiadan.exe"  # 修改为实际路径
  backend: "win32"
  timeout: 30
  retry_count: 3

api:
  host: "0.0.0.0"
  port: 8000
```

### 4. 启动服务

```bash
# 使用uv运行
uv run python main.py

# 或者激活虚拟环境后运行
uv shell
python main.py
```

服务启动后，访问 http://localhost:8000 查看API文档。

## API接口

### 执行操作

```bash
# 买入股票
curl -X POST "http://localhost:8000/api/v1/operations/buy" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "000001",
    "price": 10.50,
    "quantity": 1000
  }'

# 卖出股票
curl -X POST "http://localhost:8000/api/v1/operations/sell" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "000001",
    "price": 11.00,
    "quantity": 1000
  }'

# 查询持仓
curl -X GET "http://localhost:8000/api/v1/operations/query_positions"

# 查询委托
curl -X GET "http://localhost:8000/api/v1/operations/query_orders"
```

### 批量操作

```bash
curl -X POST "http://localhost:8000/api/v1/operations/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "operations": [
      {"name": "buy", "params": {"stock_code": "000001", "price": 10.50, "quantity": 1000}},
      {"name": "sell", "params": {"stock_code": "000002", "price": 15.00, "quantity": 500}}
    ],
    "mode": "sequential"
  }'
```

### 查询状态

```bash
# 查询操作状态
curl -X GET "http://localhost:8000/api/v1/operations/{operation_id}/status"

# 查询系统状态
curl -X GET "http://localhost:8000/api/v1/system/status"

# 查询队列统计
curl -X GET "http://localhost:8000/api/v1/queue/stats"
```

## 开发自定义插件

### 1. 创建插件文件

在 `src/automation/operations/` 目录下创建新的插件文件：

```python
from typing import Dict, Any
from src.automation.base_operation import BaseOperation, register_operation
from src.models.operations import PluginMetadata, OperationResult

@register_operation
class MyOperation(BaseOperation):
    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="MyOperation",
            version="1.0.0",
            description="我的自定义操作",
            operation_name="my_operation",
            parameters={
                "param1": {
                    "type": "string",
                    "required": True,
                    "description": "参数1"
                }
            }
        )

    async def validate(self, params: Dict[str, Any]) -> bool:
        # 参数验证逻辑
        return True

    async def execute(self, params: Dict[str, Any]) -> OperationResult:
        # 操作执行逻辑
        # 使用 self.automator 提供的底层控件操作方法

        # 示例：点击按钮
        await self.automator.wait_and_click("button_name")

        # 示例：设置文本框内容
        await self.automator.set_edit_text("edit_control", "text")

        # 示例：获取表格数据
        data = await self.automator.get_grid_data("grid_name")

        return OperationResult(success=True, data={"result": "success"})
```

**设计原则**：
- `TonghuashunAutomator` 只提供底层控件操作（点击、输入、获取数据等）
- 具体的业务逻辑在各自的 `Operation` 中实现
- 这样设计更清晰，职责分离，便于维护和扩展

### 2. 自动注册

插件创建后会自动被系统加载和注册，可以通过以下URL访问：

- 操作列表：GET /api/v1/operations
- 执行操作：POST /api/v1/operations/my_operation

## 注意事项

1. **同花顺配置**：确保同花顺交易软件已正确安装并可以正常登录
2. **权限要求**：程序需要管理员权限才能控制其他窗口
3. **安全警告**：自动化交易存在风险，请谨慎使用
4. **监控日志**：定期检查 `logs/` 目录下的日志文件

## 项目结构

```
QuantTrader/
├── src/
│   ├── api/                     # API接口
│   │   └── trading_api.py
│   ├── automation/              # 自动化相关
│   │   ├── tonghuashun_automator.py
│   │   ├── base_operation.py
│   │   ├── operation_manager.py
│   │   └── operations/          # 操作插件
│   │       ├── buy_operation.py
│   │       ├── sell_operation.py
│   │       └── ...
│   ├── core/                    # 核心组件
│   │   ├── operation_queue.py
│   │   ├── state_manager.py
│   │   └── recovery_manager.py
│   ├── models/                  # 数据模型
│   │   └── operations.py
│   └── utils/                   # 工具类
│       └── logger.py
├── config/
│   └── trading_config.yaml      # 配置文件
├── logs/                        # 日志目录
├── plugins/                     # 外部插件目录
├── pyproject.toml               # 项目配置和依赖管理
└── main.py                      # 主程序入口
```

## 常见问题

### Q: 如何查看操作是否成功？

A: 通过操作ID查询状态：
```bash
curl -X GET "http://localhost:8000/api/v1/operations/{operation_id}/status"
```

### Q: 如何添加新的交易功能？

A: 创建新的操作插件，参考 `custom_operation.py` 示例。

### Q: 系统支持哪些同花顺版本？

A: 目前支持标准版的同花顺网上交易系统，使用Win32 backend。

### Q: 如何处理操作失败？

A: 系统会自动重试失败的操作，也可以手动重试：
```bash
curl -X POST "http://localhost:8000/api/v1/operations/{operation_id}/retry"
```

## 许可证

本项目仅供学习和研究使用，请勿用于实际交易。

## 联系方式

- 邮箱：noimank@163.com
- 作者：noimank（康康）


# 同花顺交易客户端需要做的设置

1.必须在设置->中关闭显示悬浮工具栏（不然无法判断是否有弹窗，程序就会无法正常运行）
2.在系统设置->快速交易中 将“买入时是否需要确认”、“卖出时是否需要确认”，“卖出时是否需要确认" ”底部是否提示委托或成交信息“，全部选择否，提高程序自动化速度
3.在系统设置->快速交易中 将”切换页面是否清空代码“ 选择是，可以提高程序自动化速度
4.在系统设置-> 交易设置中，将 ”默认买入价格“、”默认卖出价格“都选择空