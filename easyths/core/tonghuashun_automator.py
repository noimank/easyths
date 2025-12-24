"""同花顺交易自动化器 - 核心GUI自动化类

基于 pywinauto 的 UI Automation backend 实现，提供完整的同花顺交易客户端自动化操作能力。

Author: noimank
Email: noimank@163.com
"""

from pathlib import Path
from typing import Optional, Any

import structlog
from pywinauto.application import Application

from easyths.utils import project_config_instance

logger = structlog.get_logger(__name__)


class TonghuashunAutomator:
    """同花顺交易自动化器 - 核心GUI自动化类

    所有方法都是同步的，由调用方决定执行方式（直接调用或通过COM执行器）
    """

    def __init__(self):
        """初始化自动化器"""
        self.app_path = project_config_instance.trading_app_path
        self.app: Optional[Application] = None
        self.main_window = None
        self._connected = False
        self._logged_in = False
        self.logger = structlog.get_logger(__name__)

    def connect(self) -> bool:
        """连接到同花顺交易客户端

        Returns:
            bool: 如果成功连接到同花顺应用返回 True，否则返回 False
        """
        try:
            self.logger.info("正在连接同花顺...")

            # 检查应用路径
            if not self.app_path or not Path(self.app_path).exists():
                self.logger.error("同花顺应用路径不存在", path=self.app_path)
                return False

            # 连接应用
            self.app = Application(backend="uia").connect(path=self.app_path, timeout=5)
            self.main_window = self.app.window(title="网上股票交易系统5.0", control_type="Window", visible_only=False)
            self.logger.info("连接到同花顺进程")
            self._connected = True

            return True

        except Exception as e:
            self.logger.exception("连接同花顺失败", error=str(e))
            return False

    def disconnect(self) -> None:
        """断开连接"""
        self._connected = False
        self._logged_in = False
        self.main_window = None
        self.app = None
        self.logger.info("已断开同花顺连接")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self.app is not None

    def click_menu(self, menu_path: str) -> bool:
        """点击菜单项

        Args:
            menu_path: 菜单路径，例如 "查询->持仓" 或 "File->Open"

        Returns:
            bool: 是否成功点击
        """
        main_window = self.main_window
        if not main_window:
            return False

        try:
            # 分割菜单路径
            menu_items = [item.strip() for item in menu_path.split("->")]
            # 构建pywinauto的菜单路径格式
            menu_string = "->".join(menu_items)
            # 执行菜单选择
            main_window.menu_select(menu_string)
            return True
        except Exception as e:
            self.logger.error(f"点击菜单失败: {menu_path}", error=str(e))
            return False

    def get_control(
            self,
            parent: Any = None,
            class_name: str = None,
            title: str = None,
            title_re: str = None,
            control_type: str = None,
            auto_id: str = None,
            found_index: int = None,
    ) -> Optional[Any]:
        """获取控件 - 核心查找方法

        Args:
            parent: 父控件对象，None 表示从主窗口开始查找
            class_name: 控件类名，如 "Edit"、"Button"、"ComboBox" 等
            title: 控件名称/标题文本，精确匹配
            title_re: 控件名称正则表达式，用于模糊匹配
            control_type: UIA 控件类型，如 "Button"、"Edit"、"ComboBox" 等
            auto_id: 控件的自动化 ID 属性
            found_index: 如果有多个控件匹配条件，指定返回第几个控件，从0开始

        Returns:
            Optional[Any]: 返回控件的 wrapper_object 或 None（如果查找失败）
        """
        # 获取父控件
        if parent is None:
            parent = self.main_window
            if not parent:
                return None

        # 构建查找参数
        kwargs = {}
        if class_name:
            kwargs['class_name'] = class_name
        if title:
            kwargs['title'] = title
        if title_re:
            kwargs['title_re'] = title_re
        if control_type:
            kwargs['control_type'] = control_type
        if auto_id:
            kwargs['auto_id'] = auto_id
        if found_index:
            kwargs['found_index'] = found_index

        control = parent.child_window(**kwargs)

        if control:
            return control.wrapper_object()
        return None

    def get_top_window(self, wrapper_obj: bool = False) -> Optional[Any]:
        """获取最顶层的窗口

        Args:
            wrapper_obj: 是否返回wrapper对象

        Returns:
            顶层窗口对象
        """
        if wrapper_obj:
            return self.app.top_window().wrapper_object()
        return self.app.top_window()
