"""
API路由
"""
from .system import router as system_router
from .operations import router as operations_router
from .queue import router as queue_router

__all__ = [
    "system_router",
    "operations_router",
    "queue_router"
]