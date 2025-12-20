import asyncio
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import structlog
from pywinauto.application import Application, ProcessNotFoundError
from pywinauto.findwindows import ElementNotFoundError
from pywinauto import findwindows, timings

logger = structlog.get_logger(__name__)


class TonghuashunAutomator:
    """同花顺交易自动化器 - 核心GUI自动化类

    基于 pywinauto 的 Win32 backend 实现，提供完整的同花顺交易客户端自动化操作能力。
    该类封装了控件查找、缓存管理、窗口操作等核心功能，支持高效稳定的自动化交易。

    主要特性：
        - 智能控件缓存：自动缓存已查找的控件，大幅提升重复操作的性能
        - 灵活的查找策略：支持按标题、类名、索引、正则表达式等多种方式查找控件
        - 异常重试机制：内置重试逻辑，提高操作成功率
        - 异步支持：所有操作均为异步方法，支持高并发场景
        - 详细的日志记录：使用 structlog 记录详细操作日志，便于调试和追踪

    使用示例：
        # 初始化并连接
        config = {
            'app_path': 'C:\\同花顺\\xiadan.exe',
            'timeout': 30,
            'retry_count': 3,
            'retry_delay': 1.0
        }
        automator = TonghuashunAutomator(config)
        await automator.connect()

        # 执行操作
        await automator.switch_to_tab("买入")
        await automator.set_edit_text("600000", class_name="Edit", found_index=0)
        await automator.set_edit_text("10.50", class_name="Edit", found_index=1)

    注意：
        - 使用前请确保同花顺客户端已安装并可正常启动
        - 所有操作均基于 Windows UIAutomation，需要在 Windows 环境下运行
        - 交易操作涉及资金安全，请谨慎使用并做好充分测试

    Author: noimank
    Email: noimank@163.com
    """


    def __init__(self, config: Dict[str, Any]):
        """初始化自动化器

        Args:
            config: 配置字典，支持以下键：
                   - app_path: 同花顺应用程序路径
                   - timeout: 全局超时时间（秒）
                   - retry_count: 重试次数
                   - retry_delay: 重试间隔（秒）
                   - backend: GUI自动化后端类型
        """
        self.config = config
        self.app_path = config.get('app_path', '')
        self.timeout = config.get('timeout', 30)
        self.retry_count = config.get('retry_count', 3)
        self.retry_delay = config.get('retry_delay', 1.0)
        self.backend = config.get('backend', 'win32')

        self.app: Optional[Application] = None
        self.main_window = None
        self._connected = False
        self._logged_in = False

        self.logger = structlog.get_logger(__name__)

        # 控件缓存 - 支持多种查找条件
        self._control_cache: Dict[str, Dict[str, Any]] = {}

    async def connect(self) -> bool:
        """连接到同花顺交易客户端

        该方法执行完整的连接流程：
        1. 检查应用程序路径是否存在
        2. 启动或连接到同花顺进程（使用 _start_application）
        3. 查找并连接到主窗口（使用 _connect_to_main_window）
        4. 更新连接状态

        Returns:
            bool: 如果成功连接到同花顺应用返回 True，否则返回 False

        Example:
            # 连接同花顺
            success = await automator.connect()
            if success:
                print("成功连接到同花顺")
                # 继续执行登录等操作
            else:
                print("连接失败")

        Note:
            - 该方法会自动处理应用未启动的情况，自动启动新进程
            - 如果同花顺已经在运行，则连接到现有进程
            - 连接成功后会自动缓存主窗口对象
            - 建议在执行任何操作前先调用此方法建立连接
        """
        try:
            self.logger.info("正在连接同花顺...")

            # 检查应用路径
            if not self.app_path or not Path(self.app_path).exists():
                self.logger.error("同花顺应用路径不存在", path=self.app_path)
                return False

            # 启动应用
            await self._run_with_retry(self._start_application)

            if self.app:
                # 连接到主窗口
                await self._run_with_retry(self._connect_to_main_window)
                if self.main_window:
                    self._connected = True
                    self.logger.info("成功连接到同花顺")
                    return True

            return False

        except Exception as e:
            self.logger.exception("连接同花顺失败", error=str(e))
            return False


    async def _start_application(self) -> None:
        """启动同花顺应用"""
        try:
            # 尝试连接现有进程
            self.app = Application(backend="win32").connect(
                path=self.app_path,
                timeout=5
            )
            self.logger.info("连接到现有同花顺进程")
        except (ProcessNotFoundError, ElementNotFoundError):
            # 启动新进程
            self.app = Application(backend="win32").start(self.app_path)
            self.logger.info("启动新的同花顺进程")

    async def _connect_to_main_window(self) -> None:
        """连接到主窗口"""
        # 等待窗口出现
        # time.sleep(3)  # 给应用启动时间
        # 如果找不到，尝试使用类名
        try:
            self.main_window = self.app.window(title_re=".*网上股票交易.*")
            if self.main_window.exists():
                self._control_cache["main_window"] = self.main_window
                return
        except Exception:
            pass

        raise ElementNotFoundError("无法找到同花顺主窗口")


    def click_menu(self, menu_path: str) -> bool:
        """点击菜单项

        Args:
            menu_path: 菜单路径，例如 "查询->持仓" 或 "File->Open"

        Returns:
            bool: 是否成功点击
        """
        main_window =  self.get_main_window()
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
            cache_key: str = None,
            parent: Any = None,
            class_name: str = None,
            title: str = None,
            title_re: str = None,
            control_id: int = None,
            found_index: int = None,
    ) -> Optional[Any]:
        """获取控件 - 核心查找方法

        这是所有控件查找操作的核心方法，提供灵活的控件查找和缓存机制。
        支持多种查找方式的组合，优先使用缓存提高效率。

        Args:
            cache_key: 缓存键，用于缓存和复用已查找的控件。建议使用有意义的名称，
                      如 "buy_button"、"stock_code_edit" 等
            parent: 父控件对象，None 表示从主窗口开始查找
            class_name: Win32 控件类名，如 "Edit"、"Button"、"ComboBox" 等
            title: 控件标题文本，精确匹配，如 "确定"、"取消" 等
            title_re: 控件标题正则表达式，用于模糊匹配，如 ".*买入.*" 匹配包含"买入"的标题
            control_id: 控件的自动化 ID（AutomationId）属性，如果软件支持的话
            found_index: 如果有多个控件匹配条件，指定返回第几个控件，从0开始
        Returns:
            Optional[Any]: 返回控件对象或 None（如果查找失败）。返回的控件对象可以
                         用于后续的点击、输入等操作


        Note:
            - 建议始终提供 cache_key 以提高性能
            - 查找条件可以组合使用，条件越多匹配越精确
            - 如果有多个控件匹配条件，会尝试使用 found_index 或返回第一个
            - 缓存的控件会定期验证有效性，无效控件会自动从缓存中清除
            - 支持十进制和十六进制的 control_id
        """
        # 生成缓存键
        if not cache_key:
            cache_key = self._generate_cache_key(
                class_name, title, title_re,
                control_id
            )

        # 检查缓存
        if cache_key in self._control_cache:
            cached_control = self._control_cache[cache_key]["control"]
            # 验证缓存控件是否仍然有效
            try:
                if cached_control.exists():
                    return cached_control
                else:
                    # 控件已失效，清除缓存
                    del self._control_cache[cache_key]
            except:
                del self._control_cache[cache_key]

        # 获取父控件
        if parent is None:
            parent =  self.get_main_window()
            if not parent:
                return None

        # 查找控件
        # 构建查找参数
        kwargs = {}
        if class_name:
            kwargs['class_name'] = class_name
        if title:
            kwargs['title'] = title
        if title_re:
            kwargs['title_re'] = title_re
        if control_id:
            kwargs['control_id'] = control_id

        control = None
        if found_index is not None:
            all_controls = parent.children(**kwargs)
            if found_index < len(all_controls):
                control = all_controls[found_index]
        else:
            control = parent.child_window(**kwargs)


        if control:
            # 缓存控件
            self._control_cache[cache_key] = {
                "control": control,
                "timestamp": time.time(),
                "kwargs": kwargs
            }
            return control
        return None


    def get_main_window(self) -> Optional[Any]:
        """获取同花顺主窗口控件

        获取当前连接的同花顺主窗口对象。该方法优先返回缓存的主窗口，
        如果缓存失效则重新查找并更新缓存。


        Returns:
            Optional[Any]: 返回主窗口对象或 None（如果未连接或找不到主窗口）

        Note:
            - 该方法自动缓存主窗口对象，多次调用性能开销很小
            - 如果主窗口被关闭或切换，缓存会自动失效并重新获取
            - 使用前建议先调用 is_connected() 确认连接状态

        Example:
            # 获取主窗口并执行操作
            main_window = await automator.get_main_window()
            if main_window:
                # 在主窗口下查找子控件
                button = await automator.get_control(
                    parent=main_window,
                    title="买入",
                )
        """
        if "main_window" in self._control_cache:
            main_window = self._control_cache["main_window"]
            try:
                if main_window.exists():
                    return main_window
            except:
                del self._control_cache["main_window"]

        # 查找主窗口
        if not self.app or not self.main_window:
            return None

        try:
            if self.main_window.exists() and self.main_window.is_visible():
                self._control_cache["main_window"] = self.main_window
                return self.main_window
        except:
            pass

        return None

    def _generate_cache_key(
            self,
            class_name: str,
            title: str,
            title_re: str,
            control_id: int
    ) -> str:
        """生成缓存键"""
        parts = []
        if class_name:
            parts.append(f"cn={class_name}")
        if title:
            parts.append(f"t={title}")
        if title_re:
            parts.append(f"tr={title_re}")
        if control_id:
            parts.append(f"cid={control_id}")

        return "|".join(parts) or f"auto_{int(time.time() * 1000)}"

    def clear_cache(self, pattern: str = None):
        """清除控件缓存

        清除控件缓存，可以清除全部缓存或只清除匹配指定模式的缓存项。
        在界面结构发生变化或需要刷新控件引用时调用。

        Args:
            pattern: 清除匹配指定模式的缓存。如果为 None（默认值），清除所有缓存；
                    如果提供字符串，只清除缓存键包含该字符串的缓存项

        Returns:
            None

        Example:
            # 清除所有缓存
            automator.clear_cache()

            # 只清除与 "button" 相关的缓存
            automator.clear_cache("button")

            # 只清除与 "edit" 相关的缓存
            automator.clear_cache("edit")

        Note:
            - 在界面刷新、页面切换或控件重建后，建议清除相关缓存
            - 不清除缓存可能导致获取到已失效的控件引用
            - 该方法执行后会记录日志，显示清除了多少缓存项
        """
        if pattern is None:
            self._control_cache.clear()
            self.logger.info("控件缓存已全部清除")
        else:
            # 清除匹配模式的缓存
            keys_to_remove = [k for k in self._control_cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._control_cache[key]
            self.logger.info(f"已清除 {len(keys_to_remove)} 个匹配的缓存项")

    async def _run_with_retry(self, func, *args, **kwargs):
        """带重试的执行函数"""
        last_error = None

        for attempt in range(self.retry_count):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    self.logger.warning(
                        f"操作失败，正在重试... ({attempt + 1}/{self.retry_count})",
                        error=str(e)
                    )
                    await asyncio.sleep(self.retry_delay)

        raise last_error

    async def is_connected(self) -> bool:
        """检查是否已连接"""
        if not self.app or not self.main_window:
            return False

        try:
            return self.main_window.exists() and self.main_window.is_visible()
        except:
            return False






    async def disconnect(self):
        """断开连接"""
        self._connected = False
        self._logged_in = False
        self._control_cache.clear()
        self.main_window = None
        self.app = None
        self.logger.info("已断开同花顺连接")
