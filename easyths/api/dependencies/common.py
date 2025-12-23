"""
通用依赖项
"""
from typing import Generator
from fastapi import Depends

from easyths.core.operation_queue import OperationQueue
from easyths.core import OperationManager
from easyths.core import TonghuashunAutomator


# 全局实例存储
_global_state = {
    "automator": None,
    "operation_queue": None,
    "operation_manager": None
}


def set_global_instances(
    automator: TonghuashunAutomator,
    operation_queue: OperationQueue,
    operation_manager: OperationManager
):
    """设置全局实例"""
    _global_state["automator"] = automator
    _global_state["operation_queue"] = operation_queue
    _global_state["operation_manager"] = operation_manager


def get_automator() -> TonghuashunAutomator:
    """获取自动化器实例"""
    automator = _global_state.get("automator")
    if not automator:
        raise RuntimeError("自动化器未初始化")
    return automator


def get_operation_queue() -> OperationQueue:
    """获取操作队列实例"""
    queue = _global_state.get("operation_queue")
    if not queue:
        raise RuntimeError("操作队列未初始化")
    return queue


def get_operation_manager() -> OperationManager:
    """获取操作管理器实例"""
    manager = _global_state.get("operation_manager")
    if not manager:
        raise RuntimeError("操作管理器未初始化")
    return manager