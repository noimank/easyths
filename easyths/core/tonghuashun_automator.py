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
    APP_TITLE_NAME = "网上股票交易系统5.0"

    def __init__(self):
        """初始化自动化器"""
        self.app_path = project_config_instance.trading_app_path
        self.app: Optional[Application] = None
        self.main_window = None
        self.main_window_wrapper_object = None
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
            self.main_window = self.app.window(title=self.APP_TITLE_NAME, control_type="Window", visible_only=False, depth=1)
            self.main_window_wrapper_object = self.main_window.wrapper_object()
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


