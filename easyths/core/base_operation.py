"""操作插件基类 - 同步执行模式

Author: noimank
Email: noimank@163.com
"""

import importlib.util
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, TYPE_CHECKING

import pyperclip
import pywinauto
import structlog

if TYPE_CHECKING:
    from pywinauto.base_wrapper import BaseWrapper

from easyths.core.tonghuashun_automator import TonghuashunAutomator
from easyths.models.operations import OperationResult, PluginMetadata
from easyths.utils import captcha_ocr_server
logger = structlog.get_logger(__name__)


class BaseOperation(ABC):
    """操作插件基类 - 同步执行模式

    所有业务操作都是同步函数，由队列负责调度执行。
    """

    def __init__(self, automator: TonghuashunAutomator = None):
        """初始化操作

        Args:
            automator: 同花顺自动化器实例
        """
        self.automator: TonghuashunAutomator = automator
        self.metadata = self._get_metadata()
        self.logger = structlog.get_logger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def _get_metadata(self) -> PluginMetadata:
        """获取插件元数据

        Returns:
            PluginMetadata: 插件元数据信息
        """
        pass

    @abstractmethod
    def validate(self, params: Dict[str, Any]) -> bool:
        """验证操作参数

        Args:
            params: 操作参数

        Returns:
            bool: 验证是否通过
        """
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行操作 - 同步方法

        Args:
            params: 操作参数

        Returns:
            OperationResult: 操作结果
        """
        pass

    def pre_execute(self, params: Dict[str, Any]) -> bool:
        """执行前钩子 - 同步方法

        Args:
            params: 操作参数

        Returns:
            bool: 是否继续执行
        """
        # 默认实现：检查同花顺是否已连接
        if self.automator and not self.automator.is_connected():
            self.logger.error("同花顺未连接，无法执行操作")
            return False

        # 设置主窗口焦点
        self.set_main_window_focus()
        # 关闭存在的弹窗
        self.close_pop_dialog()

        return True

    def post_execute(self, params: Dict[str, Any], result: OperationResult) -> OperationResult:
        """执行后钩子 - 同步方法

        Args:
            params: 操作参数
            result: 执行结果

        Returns:
            OperationResult: 最终结果
        """
        return result

    def run(self, params: Dict[str, Any]) -> OperationResult:
        """运行操作的完整流程 - 同步方法

        Args:
            params: 操作参数

        Returns:
            OperationResult: 操作结果
        """
        start_time = datetime.now()
        operation_name = self.metadata.operation_name
        stage = "初始化"

        try:
            self.logger.info(f"开始执行操作: {operation_name}", params=params)

            # 阶段1：参数验证
            stage = "参数验证"
            try:
                is_param_valid = self.validate(params)
                if not is_param_valid:
                    error_msg = f"{stage}失败：参数验证失败，请检查接口参数"
                    self.logger.error(error_msg, params=params)
                    return OperationResult(success=False, error=error_msg, timestamp=start_time)
            except Exception as e:
                error_msg = f"{stage}异常: {str(e)}"
                self.logger.error(error_msg, params=params, exc_info=True)
                return OperationResult(success=False, error=error_msg, timestamp=start_time)

            # 阶段2：执行前检查
            stage = "执行前检查"
            try:
                pre_execute_result = self.pre_execute(params)
                if not pre_execute_result:
                    error_msg = f"{stage}失败：同花顺未连接或环境准备失败"
                    self.logger.error(error_msg, params=params)
                    return OperationResult(success=False, error=error_msg, timestamp=start_time)
            except Exception as e:
                error_msg = f"{stage}异常: {str(e)}"
                self.logger.error(error_msg, params=params, exc_info=True)
                return OperationResult(success=False, error=error_msg, timestamp=start_time)

            # 阶段3：执行核心操作
            stage = "核心操作执行"
            try:
                result = self.execute(params)
            except Exception as e:
                error_msg = f"{stage}异常: {str(e)}"
                self.logger.error(error_msg, params=params, exc_info=True)
                return OperationResult(success=False, error=error_msg, timestamp=start_time)

            # 阶段4：执行后处理
            stage = "执行后处理"
            try:
                result = self.post_execute(params, result)
            except Exception as e:
                error_msg = f"{stage}异常: {str(e)}"
                self.logger.error(error_msg, params=params, exc_info=True)
                if result.success:
                    self.logger.warning(f"操作成功但{stage}失败: {error_msg}")
                else:
                    return OperationResult(success=False, error=error_msg, timestamp=start_time)

            # 记录执行结果
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self.logger.info(
                f"操作执行完成: {operation_name}",
                success=result.success,
                duration=duration
            )

            return result

        except Exception as e:
            error_msg = f"操作执行异常（{stage}阶段）: {str(e)}"
            self.logger.exception(error_msg, params=params)
            return OperationResult(success=False, error=error_msg, timestamp=start_time)

    # ============ 辅助方法 ============

    def switch_left_menus(self, main_option: str, sub_option: Optional[str] = None) -> None:
        """切换左侧菜单栏

        重写参考easytrader原有的垃圾实现，目前已经做到0.7s，原来需要2.2s

        Args:
            main_option: 主选项，如 查询[F4]
            sub_option: 资金股票
        """
        main_window = self.get_main_window(wrapper_obj=True)
        # 获取左侧导航栏
        main_panel = self.get_control_with_children(main_window, control_type="Pane", auto_id="59648")
        left_menu_panel = self.get_control_with_children(main_panel,  class_name="AfxWnd140s")
        # 只有一个元素
        HexinScrollWnd = left_menu_panel.children(title="HexinScrollWnd")[0]
        HexinScrollWnd2 = HexinScrollWnd.children(title="HexinScrollWnd2")[0]
        tree_view = HexinScrollWnd2.children(control_type="Tree", class_name="SysTreeView32")[0]

        # 处理主选择
        main_option_control = self.get_control_with_children(tree_view, title=main_option)
        if main_option_control is None:
            logger.error(f"未找到主菜单{main_option}")
            raise Exception(f"未找到主菜单{main_option}")
        # 展开主菜单
        if main_option in ["国债逆回购","双向委托"]:
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


    def get_main_window(self, wrapper_obj: bool = False) -> Optional[Any]:
        """获取同花顺主窗口控件

        Args:
            wrapper_obj: 是否返回wrapper对象

        注意：
            wrapper对象是没有child_window方法的，相对的wrapper对象减少了实例化时间，能加快0.3s左右

        Returns:
            主窗口对象
        """
        if not self.automator.is_connected():
            return None

        try:
            if wrapper_obj:
                return self.automator.main_window_wrapper_object
            return self.automator.main_window
        except Exception as ex:
            logger.error("获取同花顺主窗口失败: ", ex)
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

    def get_pop_dialog(self) -> Tuple[Optional[str], Optional[Any]]:
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
            # 根据
            sub_childrens = children.children(class_name="Static")
            # 有些内嵌的浏览器窗口（也是弹窗）
            pane_childrens = children.children(control_type="Pane")
            content = "".join([child.window_text() for child in sub_childrens])
            if "您的风险承受能力等级即将过期" in content:
                return "风险测评提示",children
            elif "您输入的价格已超出涨跌停限制" in content:
                return "提示信息", children
            elif "先输入验证码" in content:
                return "验证码提示框",children
            # 买入、卖出时的弹窗
            elif "提交失败" in content:
                return "失败提示", children
            elif "一键打新" in content:
                return "一键打新提示框", children
            elif "国债逆回购" in content:
                return "国债逆回购窗口", children
            elif "退出确认" in content:
                return "程序退出确认窗口", children
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

    def get_top_window(self)->"Optional[pywinauto.application.WindowSpecification]":
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
            count+=1
            self.sleep(0.15)
            pop_dialog_title, pop_control = self.get_pop_dialog()
            if pop_dialog_title == "风险测评提示":
                self.get_control_with_children(pop_control, control_type="Button", auto_id="7").click()
            elif pop_dialog_title == "提示信息":
                #点击否
                self.get_control_with_children(pop_control, control_type="Button", auto_id="7").click()

            elif pop_dialog_title == "验证码提示框":
                #点击取消
                self.get_control_with_children(pop_control, control_type="Button", auto_id="2").click()
            elif pop_dialog_title == "失败提示":
                #点击确定
                self.get_control_with_children(pop_control, control_type="Button", auto_id="2", class_name="Button").click()
            elif pop_dialog_title == "一键打新提示框":
                # 点击窗口右上角的 X 触发关闭
                self.get_control_with_children(pop_control, control_type="Button", auto_id="1008", class_name="Button").click()
            elif pop_dialog_title == "国债逆回购窗口":
                self.get_control_with_children(pop_control, control_type="Button", auto_id="1008", class_name="Button").click()

            #条件单触发提醒
            elif pop_dialog_title == 'CDlgTriggeredConfitionTip':
                pop_control.close()
            elif pop_dialog_title == 'TranferAccount':
                pop_control.close()
            # 条件单窗口
            elif pop_dialog_title == "ConditionToolBar":
                pop_control.type_keys("{ESC}")
            elif pop_dialog_title == "程序退出确认窗口":
                # 点击否关闭窗口
                self.get_control_with_children(pop_control, control_type="Button", auto_id="7").click()


        self.sleep(0.05)

    def process_captcha_dialog(self) -> None:
        """
        处理验证码弹窗
        """
        count = 0
        while self.is_exist_pop_dialog() and count < 3:
            pop_dialog_title, pop_control = self.get_pop_dialog()
            if pop_dialog_title == "验证码提示框":
                code_edit = self.get_control_with_children(pop_control, control_type="Edit", auto_id="2404",
                                                           class_name="Edit")
                # 尝试删除可能存在的旧验证码
                code_edit.type_keys('{BACKSPACE 4}')
                code_image_control = self.get_control_with_children(pop_control, control_type="Image", auto_id="2405",
                                                                    class_name="Static")
                code_image_control.click_input()
                # 等待刷新验证码
                self.sleep(0.2)
                captcha_code = self.ocr_captcha(code_image_control)
                code_edit.type_keys(captcha_code)
                self.sleep(0.1)
                # 按确定键
                # self.get_control_with_children(pop_control,control_type="Button", auto_id="1", class_name="Button").click_input()
                # self.get_control_with_children(pop_control,control_type="Button", auto_id="1", class_name="Button").click_input()
                pop_control.type_keys("{ENTER}")
                self.sleep(0.2)
            count += 1

    def get_control_with_children(self, parent_control: Any, class_name: Optional[str] = None,
                                  title: Optional[str] = None, title_re: Optional[str] = None,
                                  control_type: Optional[str] = None, auto_id: Optional[str] = None) -> Optional["BaseWrapper"]:
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
        all_children = parent_control.children(control_type=control_type, class_name=class_name,title=title)

        # 2. 手动筛选，处理内置不支持的情况
        for child in all_children:
            info = child.element_info
            # 逐项比对（如果参数不为 None 且不匹配，则跳过）
            if auto_id and info.automation_id != auto_id:
                continue
            # title_re 需要用到 re.match， 包含就是匹配
            if title_re and not (title_re in info.name):
                continue
            # 匹配成功，立刻返回第一个
            return child
        return None


    def ocr_captcha(self, control: Any) -> str:
        """根据控件获取OCR验证码结果"""
        code = captcha_ocr_server.recognize(control)
        #同花顺验证码一般是4位，防止出现大于4位的code，这个概率几乎没有
        if len(code) > 4:
            code = code[:4]
        return code


    def get_clipboard_data(self) -> str:
        """获取剪贴板数据"""
        return pyperclip.paste()


    def clear_clipboard(self) -> None:
        """清空剪贴板"""
        pyperclip.copy("")

# ============ 操作注册表 ============

class OperationRegistry:
    """操作注册表 - 管理所有已注册的操作插件"""

    def __init__(self):
        self._operations: Dict[str, type] = {}
        self._instances: Dict[str, BaseOperation] = {}
        self.logger = structlog.get_logger(__name__)

    def register(self, operation_class: type) -> None:
        """注册操作类

        Args:
            operation_class: 操作类
        """

        if not issubclass(operation_class, BaseOperation):
            raise ValueError(f"{operation_class.__name__} 必须继承自 BaseOperation")

        temp_instance = operation_class()
        operation_name = temp_instance.metadata.operation_name

        self._operations[operation_name] = operation_class
        self.logger.info(f"注册操作: {operation_name}", class_name=operation_class.__name__)

    def get_operation_class(self, name: str) -> Optional[type]:
        """获取操作类

        Args:
            name: 操作名称

        Returns:
            操作类
        """
        return self._operations.get(name)

    def get_operation_instance(self, name: str, automator=None) -> Optional[BaseOperation]:
        """获取操作实例（单例模式）

        Args:
            name: 操作名称
            automator: 自动化器实例

        Returns:
            操作实例
        """
        if name in self._instances:
            return self._instances[name]

        operation_class = self.get_operation_class(name)
        if operation_class:
            self._instances[name] = operation_class(automator)
            self.logger.info(f"创建操作实例: {name}")

        return self._instances.get(name)

    def list_operations(self) -> Dict[str, PluginMetadata]:
        """列出所有已注册的操作

        Returns:
            操作元数据字典
        """
        result = {}
        for name, operation_class in self._operations.items():
            temp_instance = operation_class()
            result[name] = temp_instance.metadata
        return result

    @staticmethod
    def load_plugins() -> int:
        """自动扫描并加载目录下的所有插件

        Returns:
            int: 成功加载的插件数量
        """
        # 使用包内 operations 目录
        plugin_path = Path(__file__).parent.parent / "operations"
        if not plugin_path.exists():
            structlog.get_logger(__name__).warning("插件目录不存在", plugin_dir=str(plugin_path))
            return 0

        loaded_count = 0

        # 遍历Python文件
        for py_file in plugin_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                # 动态导入模块
                spec = importlib.util.spec_from_file_location("plugin_module", str(py_file))
                if not spec or not spec.loader:
                    logger.error("无法创建模块规范", file_path=str(py_file))
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # 查找BaseOperation子类并注册
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                            issubclass(attr, BaseOperation) and
                            attr != BaseOperation):
                        operation_registry.register(attr)
                        loaded_count += 1
                        logger.info("成功加载插件", file=py_file.name, class_name=attr_name)

            except Exception as e:
                logger.error("加载插件文件失败", file=str(py_file), error=str(e))

        logger.info("插件加载完成", loaded_count=loaded_count)
        return loaded_count


# 全局操作注册表实例
operation_registry = OperationRegistry()
