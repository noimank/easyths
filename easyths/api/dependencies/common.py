"""
通用依赖项
"""

from easyths.core import TonghuashunAutomator
from easyths.core.operation_queue import OperationQueue

# 全局实例存储
_global_state = {
    "automator": None,
    "operation_queue": None
}


def set_global_instances(operation_queue: OperationQueue, automator: TonghuashunAutomator):
    """设置全局实例"""
    _global_state["operation_queue"] = operation_queue
    _global_state["automator"] = automator


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

