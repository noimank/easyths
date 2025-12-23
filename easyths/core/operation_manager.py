import importlib
import importlib.util
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

import structlog

from easyths.core.base_operation import BaseOperation, operation_registry

logger = structlog.get_logger(__name__)


class OperationManager:
    """操作管理器

    负责插件的加载、管理和生命周期控制
    """

    def __init__(self):
        self.plugin_dirs = ["easyths/operations"]
        self.whitelist = [] #暂未使用该功能
        self.logger = structlog.get_logger(__name__)
        self._loaded_plugins: Dict[str, str] = {}  # 插件名 -> 文件路径

    def load_plugins(self) -> None:
        """加载所有插件"""

        self.logger.info("开始加载插件", plugin_dirs=self.plugin_dirs)

        for plugin_dir in self.plugin_dirs:
            self._load_plugins_from_dir(plugin_dir)

        loaded_count = len(self._loaded_plugins)
        self.logger.info("插件加载完成", loaded_count=loaded_count)

    def _load_plugins_from_dir(self, plugin_dir: str) -> None:
        """从目录加载插件

        Args:
            plugin_dir: 插件目录路径
        """
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            self.logger.warning("插件目录不存在", plugin_dir=plugin_dir)
            return

        # 遍历Python文件
        for py_file in plugin_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            self._load_plugin_from_file(str(py_file))

    def _load_plugin_from_file(self, file_path: str) -> None:
        """从文件加载插件

        Args:
            file_path: 插件文件路径
        """
        try:
            # 动态导入模块
            spec = importlib.util.spec_from_file_location("plugin_module", file_path)
            if not spec or not spec.loader:
                self.logger.error("无法创建模块规范", file_path=file_path)
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找BaseOperation子类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                        issubclass(attr, BaseOperation) and
                        attr != BaseOperation):

                    # 创建实例获取元数据
                    try:
                        instance = attr()
                        plugin_name = instance.metadata.operation_name

                        # 检查白名单
                        if self.whitelist and plugin_name not in self.whitelist:
                            self.logger.info("插件不在白名单中，跳过加载", plugin_name=plugin_name)
                            continue

                        # 注册插件
                        operation_registry.register(attr)
                        self._loaded_plugins[plugin_name] = file_path
                        self.logger.info("成功加载插件", plugin_name=plugin_name, file=file_path)

                    except Exception as e:
                        self.logger.error("加载插件失败", attr_name=attr_name, error=str(e))

        except Exception as e:
            self.logger.error("加载插件文件失败", file_path=file_path, error=str(e))

    def reload_plugin(self, plugin_name: str) -> bool:
        """重新加载插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否成功重新加载
        """
        if plugin_name not in self._loaded_plugins:
            self.logger.error("插件未找到", plugin_name=plugin_name)
            return False

        file_path = self._loaded_plugins[plugin_name]

        # 先卸载插件
        self.unload_plugin(plugin_name)

        # 重新加载
        self._load_plugin_from_file(file_path)

        return plugin_name in self._loaded_plugins

    def unload_plugin(self, plugin_name: str) -> bool:
        """卸载插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否成功卸载
        """
        try:
            # 从注册表移除
            operation_registry.unregister(plugin_name)

            # 从已加载列表移除
            if plugin_name in self._loaded_plugins:
                del self._loaded_plugins[plugin_name]

            self.logger.info("成功卸载插件", plugin_name=plugin_name)
            return True

        except Exception as e:
            self.logger.error("卸载插件失败", plugin_name=plugin_name, error=str(e))
            return False

    def get_loaded_plugins(self) -> List[str]:
        """获取已加载的插件列表

        Returns:
            List[str]: 插件名称列表
        """
        return list(self._loaded_plugins.keys())

    def get_plugin_info(self) -> Dict[str, Any]:
        """获取插件信息

        Returns:
            Dict[str, Any]: 插件信息
        """
        return {
            "loaded_plugins": self.get_loaded_plugins(),
            "plugin_details": operation_registry.list_operations(),
            "plugin_count": len(self._loaded_plugins)
        }

    def validate_plugin(self, plugin_file: str) -> Dict[str, Any]:
        """验证插件文件

        Args:
            plugin_file: 插件文件路径

        Returns:
            Dict[str, Any]: 验证结果
        """
        result = {
            "valid": False,
            "error": None,
            "metadata": None
        }

        try:
            # 动态导入模块
            spec = importlib.util.spec_from_file_location("test_plugin", plugin_file)
            if not spec or not spec.loader:
                result["error"] = "无法创建模块规范"
                return result

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找BaseOperation子类
            operation_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                        issubclass(attr, BaseOperation) and
                        attr != BaseOperation):
                    operation_class = attr
                    break

            if not operation_class:
                result["error"] = "未找到BaseOperation子类"
                return result

            # 创建实例验证
            instance = operation_class()
            result["metadata"] = instance.metadata.dict()
            result["valid"] = True

        except Exception as e:
            result["error"] = str(e)

        return result

    def install_plugin(self, plugin_file: str, target_dir: Optional[str] = None) -> bool:
        """安装插件

        Args:
            plugin_file: 插件文件路径
            target_dir: 目标目录（默认为第一个插件目录）

        Returns:
            bool: 是否成功安装
        """
        try:
            # 验证插件
            validation = self.validate_plugin(plugin_file)
            if not validation["valid"]:
                self.logger.error("插件验证失败", error=validation['error'])
                return False

            # 确定目标目录
            if not target_dir and self.plugin_dirs:
                target_dir = self.plugin_dirs[0]

            if not target_dir:
                self.logger.error("未指定目标目录")
                return False

            # 复制文件
            target_path = Path(target_dir)
            target_path.mkdir(parents=True, exist_ok=True)

            plugin_name = Path(plugin_file).name
            dest_path = target_path / plugin_name

            import shutil
            shutil.copy2(plugin_file, dest_path)

            # 加载插件
            self._load_plugin_from_file(str(dest_path))

            self.logger.info("成功安装插件", plugin_name=plugin_name)
            return True

        except Exception as e:
            self.logger.error("安装插件失败", plugin_file=plugin_file, error=str(e))
            return False

    def export_plugin_config(self, output_file: str) -> bool:
        """导出插件配置

        Args:
            output_file: 输出文件路径

        Returns:
            bool: 是否成功导出
        """
        try:
            config = {
                "plugins": {}
            }

            for plugin_name in self.get_loaded_plugins():
                plugin_info = operation_registry.list_operations().get(plugin_name)
                if plugin_info:
                    config["plugins"][plugin_name] = plugin_info.dict()

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            self.logger.info("成功导出插件配置", output_file=output_file)
            return True

        except Exception as e:
            self.logger.error("导出插件配置失败", output_file=output_file, error=str(e))
            return False
