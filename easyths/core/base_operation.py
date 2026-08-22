"""操作插件基类 - 同步执行模式

Author: noimank
Email: noimank@163.com
"""

import importlib
import pkgutil
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Optional, cast
from uuid import uuid4

import pyperclip
import pywinauto
import structlog
from PIL import Image
from pydantic import ValidationError

if TYPE_CHECKING:
    from pywinauto.base_wrapper import BaseWrapper

from easyths.core.account_state import account_state
from easyths.core.tonghuashun_automator import TonghuashunAutomator
from easyths.models.operations import (
    ErrorCode,
    OperationParams,
    OperationResult,
    OperationStatus,
)
from easyths.operations.results import ResultModel
from easyths.utils import get_captcha_ocr_server
from easyths.utils.config import project_config_instance

logger = structlog.get_logger(__name__)


class BaseOperation[Ps: OperationParams](ABC):
    """操作插件基类 - 同步执行模式。

    子类契约（全部为类属性，无需实例方法元数据）::

        class BuyOperation(LimitOrderOperation):
            operation_name = "buy"          # 注册名（对外 API 路径）
            description = "买入股票"         # 文档描述
            Params = LimitOrderParams       # 参数模型（校验+文档唯一来源）
            Result = LimitOrderResult       # 结果模型（构造+文档唯一来源）

            def execute(self, params: LimitOrderParams) -> OperationResult: ...

    执行流水线（``run``）：参数校验（pydantic）→ 环境准备（``pre_execute``）
    → ``execute``。各阶段失败分别映射为带错误码的终态结果，业务代码内
    无需书写兜底 try/except。
    """

    operation_name: ClassVar[str]
    description: ClassVar[str] = ""
    Params: ClassVar[type[OperationParams]]
    Result: ClassVar[type[ResultModel]]

    def __init__(self, automator: TonghuashunAutomator | None = None):
        """初始化操作

        Args:
            automator: 同花顺自动化器实例
        """
        self.automator: TonghuashunAutomator | None = automator
        self.logger = structlog.get_logger(f"{__name__}.{self.__class__.__name__}")

    # ============ 结果构造 ============

    def _ok(self, data: Any = None, message: str = "") -> OperationResult:
        """构造成功结果（自动附带 account_state 缓存的当前使用账户）"""
        return OperationResult(
            status=OperationStatus.COMPLETED,
            success=True,
            data=data,
            message=message,
            current_used_account=account_state.current_used_account,
        )

    def _fail(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UI_ERROR,
        status: OperationStatus = OperationStatus.FAILED,
    ) -> OperationResult:
        """构造失败结果（自动附带 account_state 缓存的当前使用账户）"""
        return OperationResult(
            status=status,
            success=False,
            message=message,
            error_code=error_code,
            current_used_account=account_state.current_used_account,
        )

    # ============ 执行流水线 ============

    def pre_execute(self) -> bool:
        """执行前钩子：检查同花顺连接、聚焦主窗口、清理残留弹窗"""
        if not self.automator or not self.automator.is_connected():
            self.logger.error("同花顺未连接，无法执行操作")
            return False

        self.set_main_window_focus()
        self.close_pop_dialog()
        return True

    def run(self, params: dict[str, Any]) -> OperationResult:
        """运行操作的完整流程：参数校验 → 环境准备 → 核心执行"""
        start_time = datetime.now()

        self.logger.info(f"开始执行操作: {self.operation_name}", params=params)

        # 阶段1：参数验证
        try:
            model = cast(Ps, self.Params.model_validate(params))
        except ValidationError as e:
            message = f"参数验证失败: {e.error_count()}处错误"
            self.logger.error(
                message, params=params, errors=e.errors(include_url=False)
            )
            return self._fail(message, ErrorCode.INVALID_PARAMS)

        # 阶段2：执行前检查
        try:
            if not self.pre_execute():
                return self._fail("同花顺未连接或环境准备失败", ErrorCode.NOT_CONNECTED)
        except Exception as e:
            self.logger.exception("执行前检查异常", params=params)
            return self._fail(f"执行前检查异常: {e}", ErrorCode.UI_ERROR)

        # 阶段3：核心操作（execute 内部的业务拒绝自行返回 _fail，
        # 未捕获异常在此兜底为 UI_ERROR）
        try:
            result = self.execute(model)
        except Exception as e:
            self.logger.exception(f"{self.operation_name}执行异常", params=params)
            return self._fail(f"{self.operation_name}执行异常: {e}", ErrorCode.UI_ERROR)

        duration = (datetime.now() - start_time).total_seconds()
        self.logger.info(
            f"操作执行完成: {self.operation_name}",
            success=result.success,
            duration=duration,
        )
        return result

    @abstractmethod
    def execute(self, params: Ps) -> OperationResult:
        """执行核心操作 - 同步方法，参数已通过 Params 模型校验"""

    # ============ 辅助方法 ============

    def switch_left_menus(
        self, main_option: str, sub_option: str | None = None
    ) -> None:
        """切换左侧菜单栏

        重写参考easytrader原有的垃圾实现，目前已经做到0.7s，原来需要2.2s

        Args:
            main_option: 主选项，如 查询[F4]
            sub_option: 资金股票
        """
        main_window = self.get_main_window(wrapper_obj=True)
        # 获取左侧导航栏
        main_panel = self.get_control_with_children(
            main_window, control_type="Pane", auto_id="59648"
        )
        left_menu_panel = self.get_control_with_children(
            main_panel, class_name="AfxWnd140s"
        )
        # 只有一个元素
        HexinScrollWnd = left_menu_panel.children(title="HexinScrollWnd")[0]
        HexinScrollWnd2 = HexinScrollWnd.children(title="HexinScrollWnd2")[0]
        tree_view = HexinScrollWnd2.children(
            control_type="Tree", class_name="SysTreeView32"
        )[0]

        # 处理主选择
        main_option_control = self.get_control_with_children(
            tree_view, title=main_option
        )
        if main_option_control is None:
            logger.error(f"未找到主菜单{main_option}")
            raise Exception(f"未找到主菜单{main_option}")
        # 展开主菜单
        if main_option in ["通用回购", "双向委托"]:
            main_option_control.select()
            # 没有下级子菜单，也用不了expand()方法
            return
        main_option_control.expand()
        # 确保可见,实际测试不需要
        # self.sleep(0.05)
        # main_option_control.ensure_visible()

        # 等待子菜单渲染，内存变化，无需视图可见
        self.sleep(0.15)
        # 处理子选择
        if sub_option is not None:
            cc = self.get_control_with_children(main_option_control, title=sub_option)
            if cc:
                cc.select()
            else:
                logger.error(f"未找到子菜单{sub_option}")
                raise Exception(f"未找到子菜单{sub_option}")
        self.sleep(0.1)

    def get_main_window(self, wrapper_obj: bool = False) -> Any | None:
        """获取同花顺主窗口控件

        Args:
            wrapper_obj: 是否返回wrapper对象

        注意：
            wrapper对象是没有child_window方法的，相对的wrapper对象减少了实例化时间，能加快0.3s左右

        Returns:
            主窗口对象
        """
        if not self.automator or not self.automator.is_connected():
            return None

        try:
            if wrapper_obj:
                return self.automator.main_window_wrapper_object
            return self.automator.main_window
        except Exception as ex:
            logger.error("获取同花顺主窗口失败", error=str(ex))
            return None

    def sleep(self, seconds: float = 0.1) -> None:
        """睡眠指定秒数"""
        time.sleep(seconds)

    def wait_for_pop_dialog(self, timeout: float = 1.0) -> bool:
        """等待弹窗出现"""
        start = time.perf_counter()
        while time.perf_counter() - start < timeout:
            # 这里的检查是“大头”，如果它很慢，sleep 甚至可以不要
            if self.is_exist_pop_dialog():
                return True
            # 给 CPU 留一点点喘息机会即可
            time.sleep(0.001)
        return False

    def is_exist_pop_dialog(self) -> bool:
        """是否存在弹窗"""
        main_window = self.get_main_window(wrapper_obj=True)
        # 弹窗一般是这个Pane和#32770类型。如果后面有其他类型的弹窗再说，再修正
        childrens = main_window.children(control_type="Pane", class_name="#32770")
        # 另一种是独立的窗口
        win = self.get_control_with_children(main_window, control_type="Window")
        if win:
            return True
        return len(childrens) != 0

    def get_pop_dialog_content(self) -> str | None:
        """获取弹窗内容"""
        if not self.is_exist_pop_dialog():
            return None

        main_window = self.get_main_window(wrapper_obj=True)
        childrens = main_window.children(control_type="Pane", class_name="#32770")
        # 可能会出现多个（概率很小），但是不管，找到一个直接返回，由上层应用兜底和判断
        for children in childrens:
            sub_childrens = children.children(class_name="Static")
            content = "".join([child.window_text() for child in sub_childrens])
            return content
        return None

    def get_pop_dialog(self) -> tuple[str | None, Any | None]:
        """
        获取弹窗标题和对应弹窗控件，搭配get_control_in_children实现更细化的使用

        注意在这里新加入了弹窗判断逻辑后，记得去close_pop_dialog函数中添加对应的窗口关闭逻辑

        """
        if not self.is_exist_pop_dialog():
            return None, None

        main_window = self.get_main_window(wrapper_obj=True)
        childrens = main_window.children(control_type="Pane", class_name="#32770")
        # 可能会出现多个（概率很小），但是不管，找到一个直接返回，由上层应用兜底和判断
        for children in childrens:
            sub_childrens = children.children(class_name="Static")
            # 有些内嵌的浏览器窗口（也是弹窗）
            pane_childrens = children.children(control_type="Pane")
            content = "".join([child.window_text() for child in sub_childrens])
            if "您的风险承受能力等级即将过期" in content:
                return "风险测评提示", children
            elif "您输入的价格已超出涨跌停限制" in content:
                return "提示信息", children
            elif "先输入验证码" in content:
                return "验证码提示框", children
            elif "委托价格的小数部分应" in content:
                return "委托价格提示框", children
            elif "不支持历史委托查询" in content:
                return "不支持历史委托查询提示框", children
            # 买入、卖出时的弹窗
            elif "提交失败" in content:
                return "失败提示", children
            elif "一键打新" in content:
                return "一键打新提示框", children
            elif "通用回购" in content:
                return "通用回购", children
            elif "退出确认" in content:
                return "程序退出确认窗口", children
            elif "failed" in content:
                return "BeginFailed失败提示", children
            elif "数据发送错误" in content:
                return "数据发送错误提示", children
            elif "委托确认" in content:
                return "委托确认窗口", children
            else:
                pass

            # 特殊处理浏览器嵌入型弹窗,这里可能是 条件单的弹窗，class_name=ConditionToolBar
            if pane_childrens:
                return pane_childrens[0].class_name(), pane_childrens[0]

        # 处理可能出现的window类型的独立窗口,目前已知的有 条件单触发提醒、银证转账窗口
        win = self.get_control_with_children(main_window, control_type="Window")
        if win:
            return win.class_name(), win

        return "内嵌的浏览器窗口", None

    def set_main_window_focus(self) -> None:
        """设置主窗口焦点"""
        main_window = self.get_main_window(wrapper_obj=True)
        if not main_window.is_visible():
            main_window.restore()
        main_window.set_focus()

    def get_top_window(self) -> "pywinauto.application.WindowSpecification | None":
        """获取最顶层的窗口"""
        return self.automator.app.top_window()

    def close_pop_dialog(self) -> None:
        """关闭弹窗
        该函数实现各种弹窗的关闭，实现多重弹窗窗口关闭，为每一个业务操作提供一个干净的待操作状态
        """
        flag = self.is_exist_pop_dialog()
        if not flag:
            return
        count = 0
        while count < 4 and self.is_exist_pop_dialog():
            count += 1
            self.sleep(0.15)
            pop_dialog_title, pop_control = self.get_pop_dialog()
            if pop_dialog_title == "风险测评提示":
                self.get_control_with_children(
                    pop_control, control_type="Button", auto_id="7"
                ).click()
            elif pop_dialog_title in ["提示信息", "委托价格提示框"]:
                # 点击否
                self.get_control_with_children(
                    pop_control, control_type="Button", auto_id="7"
                ).click()

            elif pop_dialog_title == "验证码提示框":
                # 点击取消
                self.get_control_with_children(
                    pop_control, control_type="Button", auto_id="2"
                ).click()
            elif (
                pop_dialog_title == "不支持历史委托查询提示框"
                or pop_dialog_title == "失败提示"
            ):
                # 点击确定
                self.get_control_with_children(
                    pop_control, control_type="Button", auto_id="2", class_name="Button"
                ).click()
            elif pop_dialog_title == "一键打新提示框":
                # 点击窗口右上角的 X 触发关闭
                self.get_control_with_children(
                    pop_control,
                    control_type="Button",
                    auto_id="1008",
                    class_name="Button",
                ).click()
            elif pop_dialog_title == "通用回购":
                self.get_control_with_children(
                    pop_control,
                    control_type="Button",
                    auto_id="1008",
                    class_name="Button",
                ).click()
            elif pop_dialog_title == "BeginFailed失败提示":
                self.get_control_with_children(
                    pop_control, control_type="Button", auto_id="2", class_name="Button"
                ).click()
            # 条件单触发提醒
            elif (
                pop_dialog_title == "CDlgTriggeredConfitionTip"
                or pop_dialog_title == "TranferAccount"
            ):
                pop_control.close()
            # 条件单窗口
            elif pop_dialog_title == "ConditionToolBar":
                pop_control.type_keys("{ESC}")
            elif pop_dialog_title == "程序退出确认窗口":
                # 点击否关闭窗口
                self.get_control_with_children(
                    pop_control, control_type="Button", auto_id="7"
                ).click()
            elif pop_dialog_title == "数据发送错误提示":
                self.get_control_with_children(
                    pop_control, control_type="Button", auto_id="1009"
                ).click()

            elif pop_dialog_title == "委托确认窗口":
                self.get_control_with_children(
                    pop_control, control_type="Button", auto_id="7"
                ).click()
                # Alt+N 确认（% = Alt，^ = Ctrl，+ = Shift）
                # pop_control.type_keys("%n")

            else:
                try:
                    pop_control.type_keys("{ESC}")
                except Exception:
                    self.logger.warning("未知的弹窗类型，无法关闭")

        self.sleep(0.05)

    def process_captcha_dialog(self) -> None:
        """
        处理验证码弹窗
        """
        captcha_code_length = 0
        count = 0
        captcha_image = None
        while self.is_exist_pop_dialog() and count < 5:
            pop_dialog_title, pop_control = self.get_pop_dialog()
            if pop_dialog_title == "验证码提示框":
                if (
                    captcha_image is not None
                    and captcha_code_length != 0
                    and project_config_instance.save_error_captcha_image
                ):
                    # 保存错误的图片
                    error_dir = Path("~/easyths/captcha_error").expanduser()
                    error_dir.mkdir(parents=True, exist_ok=True)
                    captcha_image.save(str(error_dir / f"{uuid4().hex[:12]}.png"))

                code_edit = self.get_control_with_children(
                    pop_control, control_type="Edit", auto_id="2404", class_name="Edit"
                )
                # 尝试删除可能存在的旧验证码
                code_edit.type_keys(f"{{BACKSPACE {captcha_code_length}}}")
                code_image_control = self.get_control_with_children(
                    pop_control,
                    control_type="Image",
                    auto_id="2405",
                    class_name="Static",
                )
                if captcha_code_length != 0:
                    code_image_control.click_input()
                    # 等待刷新验证码
                    self.sleep(0.2)
                captcha_code, captcha_image = self.ocr_captcha(code_image_control)
                captcha_code_length = len(captcha_code)
                code_edit.type_keys(captcha_code)
                self.sleep(0.1)
                # 按确定键
                # self.get_control_with_children(pop_control,control_type="Button", auto_id="1", class_name="Button").click_input()
                pop_control.type_keys("{ENTER}")
                self.sleep(0.2)
            count += 1

    def get_control_with_children(
        self,
        parent_control: Any,
        class_name: str | None = None,
        title: str | None = None,
        title_contains: str | None = None,
        control_type: str | None = None,
        auto_id: str | None = None,
    ) -> Optional["BaseWrapper"]:
        """在子控件中查找控件,实现最快的控件查找方法, 比 使用child_window() 快很多倍，项目禁止使用child_window()方法来获取控件

        这里的函数返回类型只是辅助编码提示，并不是实际的类型，有些方法没提示不代表不能用，比如click方法

        项目实际就是使用这个进行加速，比如买入操作10s暴降至3s内
        一般返回的控件有以下方法：
        - click()   -> 必须是ButtonWrapper类型才可以调用
        - click_input()  -> 模拟物理点击，会移动鼠标，uia控件都会有
        - type_keys()
        - texts()
        - window_text()
        - element_info
        """
        # 1. 先拿到所有亲儿子,先使用支持的筛选参数进行
        all_children = parent_control.children(
            control_type=control_type, class_name=class_name, title=title
        )

        # 2. 手动筛选，处理内置不支持的情况
        for child in all_children:
            info = child.element_info
            # 逐项比对（如果参数不为 None 且不匹配，则跳过）
            if auto_id and info.automation_id != auto_id:
                continue
            # title_contains 按子串包含匹配
            if title_contains and title_contains not in info.name:
                continue
            # 匹配成功，立刻返回第一个
            return child
        return None

    def ocr_captcha(self, control: Any) -> tuple[str, Image.Image]:
        """根据控件获取OCR验证码结果"""
        code, image = get_captcha_ocr_server().recognize(control)
        return code, image

    def get_clipboard_data(self) -> str:
        """获取剪贴板数据"""
        return pyperclip.paste()

    def clear_clipboard(self) -> None:
        """清空剪贴板"""
        pyperclip.copy("")


# ============ 操作注册表 ============

#: 不注入 account_name 执行指令的操作名（对外契约：/operations/ 列表以此暴露
#: supports_account_directive 标志）
#: - account_switch：account_name 是其业务参数（切换目标），不是指令
#: - account_query：自身负责初始化账户缓存，指令执行依赖该缓存，
#:   重连后携带指令会因缓存为空而失败（死循环）
NO_ACCOUNT_DIRECTIVE_OPS = frozenset({"account_switch", "account_query"})


class OperationRegistry:
    """操作注册表 - 管理所有已注册的操作插件"""

    def __init__(self):
        self._operations: dict[str, type[BaseOperation]] = {}
        self._instances: dict[str, BaseOperation] = {}
        self._plugins_loaded = False
        self.logger = structlog.get_logger(__name__)

    def register(self, operation_class: type[BaseOperation]) -> None:
        """注册操作类（契约：必须声明 operation_name 与 Params）"""
        if not (
            isinstance(operation_class, type)
            and issubclass(operation_class, BaseOperation)
        ):
            raise ValueError(f"{operation_class} 必须继承自 BaseOperation")
        if not getattr(operation_class, "operation_name", None):
            raise ValueError(f"{operation_class.__name__} 缺少 operation_name 声明")
        if not getattr(operation_class, "Result", None):
            raise ValueError(f"{operation_class.__name__} 缺少 Result 声明")

        self._operations[operation_class.operation_name] = operation_class
        self.logger.info(
            f"注册操作: {operation_class.operation_name}",
            class_name=operation_class.__name__,
        )

    def get_operation_class(self, name: str) -> type[BaseOperation] | None:
        """获取操作类"""
        return self._operations.get(name)

    def get_operation_instance(self, name: str, automator=None) -> BaseOperation | None:
        """获取操作实例（同名实例缓存，automator 变化时重建）"""
        cached = self._instances.get(name)
        if cached is not None and cached.automator is automator:
            return cached

        operation_class = self.get_operation_class(name)
        if operation_class is None:
            return None

        instance = operation_class(automator)
        self._instances[name] = instance
        self.logger.info(f"创建操作实例: {name}")
        return instance

    def list_operations(self) -> dict[str, dict[str, Any]]:
        """列出所有已注册操作的描述信息（含参数/结果 schema）"""
        return {
            cls.operation_name: {
                "name": cls.operation_name,
                "description": cls.description,
                "parameters": cls.Params.model_json_schema(),
                "result_schema": cls.Result.model_json_schema(),
                "supports_account_directive": (
                    cls.operation_name not in NO_ACCOUNT_DIRECTIVE_OPS
                ),
            }
            for cls in self._operations.values()
        }

    def load_plugins(self) -> int:
        """自动扫描并加载 operations 包下的所有插件（幂等，仅首次调用实际加载）。

        Returns:
            int: 本次成功加载的插件数量（已加载过时为 0）
        """
        if self._plugins_loaded:
            return 0
        self._plugins_loaded = True

        import easyths.operations as operations_package

        loaded_count = 0

        for module_info in pkgutil.iter_modules(operations_package.__path__):
            if module_info.name.startswith("_"):
                continue

            module_name = f"easyths.operations.{module_info.name}"
            try:
                module = importlib.import_module(module_name)

                # 只注册定义在该模块内的 BaseOperation 子类，
                # 避免把 import 进来的其他操作类重复注册
                for attr_name, attr in vars(module).items():
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseOperation)
                        and attr is not BaseOperation
                        and attr.__module__ == module_name
                    ):
                        self.register(attr)
                        loaded_count += 1
                        logger.info(
                            "成功加载插件", file=module_info.name, class_name=attr_name
                        )

            except Exception as e:
                logger.error("加载插件文件失败", file=module_name, error=str(e))

        logger.info("插件加载完成", loaded_count=loaded_count)
        return loaded_count


# 全局操作注册表实例
operation_registry = OperationRegistry()
