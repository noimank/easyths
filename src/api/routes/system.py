"""
系统相关路由
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from typing import Dict, Any

from src.api.dependencies.common import get_automator, get_operation_manager
from src.api.dependencies.auth import verify_api_key
from src.models.operations import APIResponse

router = APIRouter(prefix="/api/v1/system", tags=["系统"])


@router.get("/health")
async def health_check(
    api_valid: bool = Depends(verify_api_key),
    automator = Depends(get_automator),
    operation_manager = Depends(get_operation_manager)
) -> APIResponse:
    """健康检查"""
    # 检查各个组件状态
    is_connected = await automator.is_connected()

    return APIResponse(
        success=True,
        message="系统运行正常",
        data={
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "automator": "connected" if is_connected else "disconnected",
                "logged_in": automator._logged_in if is_connected else False,
                "plugins": {
                    "loaded": len(operation_manager.get_loaded_plugins())
                }
            }
        }
    )


@router.get("/status")
async def get_system_status(
    api_valid: bool = Depends(verify_api_key),
    automator = Depends(get_automator),
    operation_manager = Depends(get_operation_manager)
) -> APIResponse:
    """获取系统详细状态"""
    is_connected = await automator.is_connected()

    return APIResponse(
        success=True,
        message="查询成功",
        data={
            "timestamp": datetime.now().isoformat(),
            "automator": {
                "connected": is_connected,
                "logged_in": automator._logged_in if is_connected else False,
                "app_path": automator.app_path,
                "backend": "win32"
            },
            "plugins": operation_manager.get_plugin_info()
        }
    )


@router.get("/info")
async def get_system_info(
    api_valid: bool = Depends(verify_api_key)
) -> APIResponse:
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
                "插件化架构",
                "RESTful API",
                "实时监控"
            ]
        }
    )