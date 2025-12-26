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
    # 修改为 正则匹配 网上股票交易系统.*  避免可能未来版本更新导致找不到窗口的问题
    # APP_TITLE_NAME = "网上股票交易系统5.0"

    def __init__(self):
        """初始化自动化器"""
        self.app_path = project_config_instance.trading_app_path
        self.app: Optional[Application] = None
        self.main_window = None
        self.main_window_wrapper_object = None
        self._connected = False
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
            self.main_window = self.app.window(title_re="网上股票交易系统.*", control_type="Window", visible_only=False, depth=1)
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
        self.main_window = None
        self.app = None
        self.logger.info("已断开同花顺连接")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self.app is not None



