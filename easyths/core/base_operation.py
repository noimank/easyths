"""操作插件基类 - 同步执行模式

Author: noimank
Email: noimank@163.com
"""

import importlib.util
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import pyperclip
import structlog

from easyths.core.tonghuashun_automator import TonghuashunAutomator
from easyths.core.ocr_service import get_ocr_service
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

    def rollback(self, params: Dict[str, Any]) -> bool:
        """回滚操作（可选实现）

        Args:
            params: 操作参数

        Returns:
            bool: 回滚是否成功
        """
        self.logger.info(f"操作 {self.metadata.operation_name} 不支持回滚")
        return False

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

    def _get_left_menus_handle(self):
        """获取左侧菜单树句柄"""
        count = 2
        while True:
            try:
                handle = self.automator.main_window.child_window(
                    control_id=129, class_name="SysTreeView32"
                )
                if count <= 0:
                    return handle
                handle.wait("ready", 2)
                return handle
            except Exception as ex:
                logger.exception("获取左侧菜单失败")
            count = count - 1

    def switch_left_menus(self, path, sleep=0.2):
        """切换左侧菜单栏

        Args:
            path: 菜单路径
            sleep: 等待秒数
        """
        self._get_left_menus_handle().get_item(path).select()
        self.get_top_window().type_keys('{F5}')
        time.sleep(sleep)

    def get_main_window(self, wrapper_obj: bool = False) -> Optional[Any]:
        """获取同花顺主窗口控件

        Args:
            wrapper_obj: 是否返回wrapper对象

        Returns:
            主窗口对象
        """
        if not self.automator.is_connected():
            return None

        try:
            if wrapper_obj:
                return self.automator.wrapper_object()
            return self.automator.main_window
        except:
            pass

        return None

    def sleep(self, seconds: float = 0.1):
        """睡眠指定秒数"""
        time.sleep(seconds)

    def is_exist_pop_dialog(self):
        """是否存在弹窗"""
        top_window = self.get_top_window()
        childrens = top_window.children()
        return len(childrens) != 3

    def get_pop_dialog_title(self):
        """获取弹窗标题"""
        standard_pop_dialog_cid = 1365
        top_window = self.get_top_window()
        childrens = top_window.children()

        if len(childrens) == 0:
            return None

        for children in childrens:
            if children.control_id() == standard_pop_dialog_cid:
                return children.window_text()

        return "内嵌的浏览器窗口"

    def set_main_window_focus(self):
        """设置主窗口焦点"""
        main_window = self.automator.main_window
        if not main_window.is_visible():
            main_window.set_focus()

    def get_top_window(self, wrapper_obj: bool = False):
        """获取最顶层的窗口"""
        if wrapper_obj:
            return self.automator.app.top_window().wrapper_object()
        return self.automator.app.top_window()

    def close_pop_dialog(self):
        """关闭弹窗"""
        flag = self.is_exist_pop_dialog()
        if not flag:
            return

        count = 0
        main_window = self.get_main_window()
        while count < 3 and self.is_exist_pop_dialog():
            self.sleep(0.1)
            childrens = main_window.children(control_type="Pane", class_name="#32770")
            for children in childrens:
                children.close()
                self.sleep(0.1)
            count += 1
        self.sleep(0.1)

    def process_captcha_dialog(self):
        """处理验证码弹窗"""
        retry_count = 3
        time.sleep(0.05)
        while self.is_exist_pop_dialog() and retry_count > 0:
            pop_dialog_title = self.get_pop_dialog_title()
            top_window = self.get_top_window()
            if pop_dialog_title == "提示":
                captcha_pic_control = self.get_control(parent=top_window, control_id=0x965, class_name="Static")
                captcha_edit = self.get_control(parent=top_window, control_id=0x964, class_name="Edit")
                old_captcha_value = captcha_edit.texts()[1]

                if len(old_captcha_value) > 0:
                    captcha_pic_control.click()
                    time.sleep(0.05)
                    captcha_edit.type_keys("{BACKSPACE 5}")

                captcha_code = self.ocr_target_control_to_text(captcha_pic_control, "验证码")
                captcha_edit.type_keys(captcha_code)
                self.get_control(parent=top_window, control_id=0x1, class_name="Button").click()
                time.sleep(0.15)
            else:
                break
            retry_count -= 1

    def get_control(self, parent: Any = None, class_name: str = None, title: str = None,
                    title_re: str = None, control_type: str = None, auto_id: str = None,
                    found_index: int = None):
        """获取控件"""
        return self.automator.get_control(
            parent=parent, class_name=class_name, title=title, title_re=title_re,
            control_type=control_type, auto_id=auto_id, found_index=found_index
        )

    def ocr_target_control_to_text(self, control, post_process_type=None):
        """根据控件获取OCR文本结果"""
        try:
            if control is None:
                raise Exception("控件对象为空")

            rect = control.element_info.rectangle
            left = rect.left
            top = rect.top
            right = rect.right
            bottom = rect.bottom
            width = right - left
            height = bottom - top

            monitor = {"top": top, "left": left, "width": width, "height": height}

            ocr_service = get_ocr_service()
            recognized_text = ocr_service.recognize_text(
                image_or_loc=monitor,
                post_process_type=post_process_type
            )
            return recognized_text
        except Exception as e:
            self.logger.error(
                "OCR识别失败",
                control=control,
                post_process_type=post_process_type,
                error=str(e)
            )
            raise

    def get_clipboard_data(self):
        """获取剪贴板数据"""
        return pyperclip.paste()


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
    def load_plugins(plugin_dir: str = "easyths/operations") -> int:
        """自动扫描并加载目录下的所有插件

        Args:
            plugin_dir: 插件目录路径

        Returns:
            int: 成功加载的插件数量
        """
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            structlog.get_logger(__name__).warning("插件目录不存在", plugin_dir=plugin_dir)
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
