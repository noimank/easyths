import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, Type

import structlog

from src.automation.tonghuashun_automator import TonghuashunAutomator
from src.models.operations import OperationResult, PluginMetadata

logger = structlog.get_logger(__name__)


class BaseOperation(ABC):
    """操作插件基类

    所有操作插件必须继承此类并实现相应方法
    """

    def __init__(self, automator: TonghuashunAutomator = None, config: Optional[Dict[str, Any]] = None):
        """初始化操作

        Args:
            automator: 同花顺自动化器实例
            config: 配置参数
        """
        self.automator: TonghuashunAutomator = automator
        self.config = config or {}
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
    async def validate(self, params: Dict[str, Any]) -> bool:
        """验证操作参数

        Args:
            params: 操作参数

        Returns:
            bool: 验证是否通过
        """
        pass

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行操作

        Args:
            params: 操作参数

        Returns:
            OperationResult: 操作结果
        """
        pass

    async def pre_execute(self, params: Dict[str, Any]) -> bool:
        """执行前钩子

        Args:
            params: 操作参数

        Returns:
            bool: 是否继续执行
        """
        # 默认实现：检查同花顺是否已连接
        if self.automator and not await self.automator.is_connected():
            self.logger.error("同花顺未连接，无法执行操作")
            return False
        # 默认尝试关闭存在的弹窗，为执行操作准备统一的操作环境
        self.close_pop_dialog()

        return True

    async def post_execute(self, params: Dict[str, Any], result: OperationResult) -> OperationResult:
        """执行后钩子

        Args:
            params: 操作参数
            result: 执行结果

        Returns:
            OperationResult: 最终结果
        """
        # 默认实现：直接返回结果
        return result

    async def rollback(self, params: Dict[str, Any]) -> bool:
        """回滚操作（可选实现）

        Args:
            params: 操作参数

        Returns:
            bool: 回滚是否成功
        """
        self.logger.info(f"操作 {self.metadata.operation_name} 不支持回滚")
        return False

    async def run(self, params: Dict[str, Any]) -> OperationResult:
        """运行操作的完整流程

        Args:
            params: 操作参数

        Returns:
            OperationResult: 操作结果
        """
        start_time = datetime.now()
        try:
            self.logger.info(f"开始执行操作: {self.metadata.operation_name}", params=params)

            # 参数验证
            if not await self.validate(params):
                error_msg = "参数验证失败"
                self.logger.error(error_msg, params=params)
                return OperationResult(success=False, error=error_msg, timestamp=start_time)

            # 执行前钩子
            if not await self.pre_execute(params):
                error_msg = "执行前检查失败"
                self.logger.error(error_msg, params=params)
                return OperationResult(success=False, error=error_msg, timestamp=start_time)

            # 执行操作
            result = await self.execute(params)

            # 执行后钩子
            result = await self.post_execute(params, result)

            # 记录执行结果
            end_time = datetime.now()
            self.logger.info(
                f"操作执行完成: {self.metadata.operation_name}",
                success=result.success,
                duration=(end_time - start_time).total_seconds()
            )

            return result

        except Exception as e:
            error_msg = f"操作执行异常: {str(e)}"
            self.logger.exception(error_msg, params=params)
            return OperationResult(success=False, error=error_msg, timestamp=start_time)

    def get_parameter_schema(self) -> Dict[str, Any]:
        """获取参数Schema

        Returns:
            Dict[str, Any]: 参数Schema定义
        """
        return self.metadata.parameters

    @classmethod
    def get_operation_name(cls) -> str:
        """获取操作名称

        Returns:
            str: 操作名称
        """
        # 从类名推导操作名称
        class_name = cls.__name__
        if class_name.endswith('Operation'):
            return class_name[:-10].lower()
        return class_name.lower()

    def active_main_window(self):
        """激活窗口"""
        main_window = self.automator.get_main_window()
        if main_window:
            main_window.set_focus()

    def is_exist_pop_dialog(self):
        """是否存在弹窗"""
        # 标准的弹出窗口id
        standard_pop_dialog_cid = 1365
        top_window = self.get_top_window()
        childrens = top_window.children()
        return len(childrens) > 0

    def get_pop_dialog_title(self):
        # 标准的弹出窗口id
        standard_pop_dialog_cid = 1365
        top_window = self.get_top_window()
        childrens = top_window.children()
        # 空控件，就说明没有弹窗
        if len(childrens) == 0:
            return None

        for children in childrens:
            if children.control_id() == standard_pop_dialog_cid:
                return children.window_text()

        return "内嵌的浏览器窗口"

    def set_main_window_focus(self):
        """
        设置主窗口焦点
        """
        main_window = self.automator.get_main_window()
        if main_window:
            main_window.set_focus()

    def get_top_window(self):
        """
        获取最顶层的窗口
        """
        return self.automator.app.top_window()

    def close_pop_dialog(self):
        top_window = self.get_top_window()
        childrens = top_window.children()
        # 空控件，就说明没有弹窗
        if len(childrens) == 0:
            return
        # 不调用close，优雅的关闭就好，以免有些web view类型的弹窗关闭后无法二次打开
        # 而且随便输入esc键也不会造成任何其他影响，反而可以提高稳定性，避免控件被意外关闭
        while True:
            time.sleep(0.1)
            top_window = self.get_top_window()
            childrens = top_window.children()
            if len(childrens) == 0:
                main_window = self.automator.get_main_window()
                # 这里再多按两下 esc，让软件处于重置状态，不然可能无法再次打开窗口，比如说 在 资金股票中，可以先打开止盈止损，在打开银证转账就可以得到两个弹窗窗口
                main_window.type_keys("{ESC}")
                time.sleep(0.1)
                main_window.type_keys("{ESC}")
                return
            top_window.type_keys("{ESC}")

    def get_control(self,
                    cache_key: str = None,
                    parent: Any = None,
                    class_name: str = None,
                    title: str = None,
                    title_re: str = None,
                    control_id: int = None,
                    found_index: int = None):
        """获取控件"""
        return self.automator.get_control(cache_key=cache_key,
                                          parent=parent,
                                          class_name=class_name,
                                          title=title,
                                          title_re=title_re,
                                          control_id=control_id,
                                          found_index=found_index)


class OperationRegistry:
    """操作注册表

    用于管理所有已注册的操作插件
    """

    def __init__(self):
        self._operations: Dict[str, Type[BaseOperation]] = {}
        self._instances: Dict[str, BaseOperation] = {}
        self.logger = structlog.get_logger(__name__)
        # 添加实例锁，防止并发创建实例时的竞态条件
        self._instance_lock = asyncio.Lock()

    def register(self, operation_class: Type[BaseOperation]) -> None:
        """注册操作类

        Args:
            operation_class: 操作类
        """
        # 验证是否是BaseOperation的子类
        if not issubclass(operation_class, BaseOperation):
            raise ValueError(f"{operation_class.__name__} 必须继承自 BaseOperation")

        # 创建临时实例获取元数据
        temp_instance = operation_class()
        operation_name = temp_instance.metadata.operation_name

        self._operations[operation_name] = operation_class
        self.logger.info(f"注册操作: {operation_name}", class_name=operation_class.__name__)

    def get_operation_class(self, name: str) -> Optional[Type[BaseOperation]]:
        """获取操作类

        Args:
            name: 操作名称

        Returns:
            Optional[Type[BaseOperation]]: 操作类
        """
        return self._operations.get(name)

    async def get_operation_instance(self, name: str, automator=None, config=None) -> Optional[BaseOperation]:
        """获取操作实例（单例模式）

        Args:
            name: 操作名称
            automator: 自动化器实例
            config: 配置参数

        Returns:
            Optional[BaseOperation]: 操作实例
        """
        # 先检查实例是否已存在，避免不必要的锁获取
        if name in self._instances:
            return self._instances[name]

        # 使用锁保护实例创建过程，防止并发创建多个实例
        async with self._instance_lock:
            # 双重检查锁定模式，再次检查实例是否已被其他线程创建
            if name in self._instances:
                return self._instances[name]

            operation_class = self.get_operation_class(name)
            if operation_class:
                self._instances[name] = operation_class(automator, config)
                self.logger.info(f"创建操作实例: {name}")

            return self._instances.get(name)

    def list_operations(self) -> Dict[str, PluginMetadata]:
        """列出所有已注册的操作

        Returns:
            Dict[str, PluginMetadata]: 操作元数据字典
        """
        result = {}
        for name, operation_class in self._operations.items():
            temp_instance = operation_class()
            result[name] = temp_instance.metadata
        return result

    def unregister(self, name: str) -> bool:
        """注销操作

        Args:
            name: 操作名称

        Returns:
            bool: 是否成功注销
        """
        if name in self._operations:
            del self._operations[name]
            if name in self._instances:
                del self._instances[name]
            self.logger.info(f"注销操作: {name}")
            return True
        return False


# 全局操作注册表实例
operation_registry = OperationRegistry()


def register_operation(operation_class: Type[BaseOperation]) -> Type[BaseOperation]:
    """操作注册装饰器

    Args:
        operation_class: 操作类

    Returns:
        Type[BaseOperation]: 原操作类
    """
    operation_registry.register(operation_class)
    return operation_class
