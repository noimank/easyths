"""
系统相关路由
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from typing import Dict, Any

from easyths.api.dependencies.common import get_automator
from easyths.models.operations import APIResponse
from easyths.core import operation_registry

router = APIRouter(prefix="/api/v1/system", tags=["系统"])


@router.get("/health")
async def health_check(
    automator = Depends(get_automator)
) -> APIResponse:
    """健康检查"""
    # 检查各个组件状态
    is_connected = automator.is_connected()

    # 获取已加载的插件数量
    operations = operation_registry.list_operations()

    return APIResponse(
        success=True,
        message="系统运行正常",
        data={
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "automator": "connected" if is_connected else "disconnected",
                "plugins": {
                    "loaded": len(operations)
                }
            }
        }
    )


@router.get("/status")
async def get_system_status(
    automator = Depends(get_automator)
) -> APIResponse:
    """获取系统详细状态"""
    is_connected = automator.is_connected()

    # 获取插件信息
    operations = operation_registry.list_operations()

    return APIResponse(
        success=True,
        message="查询成功",
        data={
            "timestamp": datetime.now().isoformat(),
            "automator": {
                "connected": is_connected,
                "app_path": automator.app_path,
                "backend": "win32"
            },
            "plugins": {
                "loaded_plugins": list(operations.keys()),
                "plugin_count": len(operations),
                "plugin_details": operations
            }
        }
    )


@router.get("/info")
async def get_system_info() -> APIResponse:
    """获取系统信息"""
    return APIResponse(
        success=True,
        message="查询成功",
        data={
            "name": "同花顺交易自动化系统",
            "version": "1.0.0",
            "description": "基于pywinauto的同花顺交易软件自动化系统",
            "features": [
                "操作串行化",
                "优先级队列",
                "插件化架构",
                "RESTful API",
                "实时监控"
            ]
        }
    )