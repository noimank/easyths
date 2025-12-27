# 开发指南

## 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/noimank/easyths.git
cd easyths

# 安装开发依赖
uv sync --group dev

# 运行测试
pytest

# 代码格式化
black easyths/
ruff check easyths/
```

## 编写新操作

### 操作插件目录

所有操作插件位于 `easyths/operations/` 目录下。项目会**自动加载**该目录下的所有插件，无需手动注册。

### 继承 BaseOperation

每个操作插件必须继承 `BaseOperation` 基类。基类提供了大量通用方法，开发者应优先复用这些方法：

```python
from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult

class MyOperation(BaseOperation):
    """我的操作"""
```

### 实现必需方法

#### 1. _get_metadata() - 定义插件元数据

```python
def _get_metadata(self) -> PluginMetadata:
    return PluginMetadata(
        name="MyOperation",              # 操作类名
        version="1.0.0",                  # 版本号
        description="操作描述",            # 描述
        author="你的名字",                 # 作者
        operation_name="my_operation",    # 操作名称（API 调用使用）
        parameters={                      # 参数定义
            "param1": {
                "type": "string",
                "required": True,
                "description": "参数说明"
            }
        }
    )
```

#### 2. validate() - 参数验证

```python
def validate(self, params: Dict[str, Any]) -> bool:
    """验证操作参数"""
    # 检查必需参数
    required_params = ["param1"]
    for param in required_params:
        if param not in params:
            self.logger.error(f"缺少必需参数: {param}")
            return False

    # 验证参数格式
    if not isinstance(params["param1"], str):
        self.logger.error("参数类型错误")
        return False

    return True
```

#### 3. execute() - 核心操作逻辑

```python
def execute(self, params: Dict[str, Any]) -> OperationResult:
    """执行操作"""
    try:
        # 你的操作逻辑
        result_data = {"key": "value"}

        return OperationResult(
            success=True,
            data=result_data
        )
    except Exception as e:
        return OperationResult(
            success=False,
            error=str(e)
        )
```

### 可选钩子方法

- **pre_execute()** - 执行前预处理（如切换菜单、关闭弹窗）
- **post_execute()** - 执行后处理

```python
def pre_execute(self, params: Dict[str, Any]) -> bool:
    """执行前钩子"""
    # 调用基类方法：设置焦点、关闭弹窗
    return super().pre_execute(params)
```

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
    title="标题",                 # 控件标题
    title_re=r"^正则.*",         # 标题正则匹配
    auto_id="1032"               # 自动化 ID（重要）
)
```

### 支持的筛选字段

UIA 后端支持的筛选字段：

- `control_type` - 控件类型（Window, Button, Edit, Text, Pane 等）

- `class_name` - 控件类名

- `title` - 控件标题

**手动筛选的字段**：

- `auto_id` - 自动化 ID（UIA 不直接支持，通过手动筛选实现）

- `title_re` - 标题正则表达式（手动筛选）

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

参考 `easyths/operations/buy.py` 和 `easyths/operations/funds_query.py` 获取完整实现。

### 简单操作示例

```python
from typing import Dict, Any
from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult

class SimpleQueryOperation(BaseOperation):
    """简单查询操作"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="SimpleQueryOperation",
            version="1.0.0",
            description="简单查询示例",
            author="your_name",
            operation_name="simple_query",
            parameters={}
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        # 切换菜单
        self.switch_left_menus("查询[F4]", "资金股票")

        # 获取数据
        main_window = self.get_main_window(wrapper_obj=True)
        main_panel = main_window.children(control_type="Pane")[0]
        text_controls = main_panel.children(control_type="Text")

        result_data = {}
        for control in text_controls:
            auto_id = control.element_info.automation_id
            if auto_id == "1016":
                result_data["可用金额"] = control.window_text()

        return OperationResult(success=True, data=result_data)
```

## 项目结构

```
easyths/
├── easyths/
│   ├── operations/          # 操作插件目录（新增插件放这里）
│   ├── core/
│   │   └── base_operation.py  # BaseOperation 基类
│   └── models/
│       └── operations.py      # 数据模型
├── docs/                     # 文档
└── pyproject.toml
```

## 下一步

[贡献指南](contributing.md)
