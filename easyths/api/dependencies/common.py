"""
通用依赖项
"""

from easyths.core import TonghuashunAutomator
from easyths.core.operation_queue import OperationQueue

# 全局实例存储
_automator: TonghuashunAutomator | None = None
_operation_queue: OperationQueue | None = None


def set_global_instances(
    operation_queue: OperationQueue, automator: TonghuashunAutomator
):
    """设置全局实例"""
    global _automator, _operation_queue
    _operation_queue = operation_queue
    _automator = automator


def get_automator() -> TonghuashunAutomator:
    """获取自动化器实例"""
    if _automator is None:
        raise RuntimeError("自动化器未初始化")
    return _automator


def get_operation_queue() -> OperationQueue:
    """获取操作队列实例"""
    if _operation_queue is None:
        raise RuntimeError("操作队列未初始化")
    return _operation_queue
