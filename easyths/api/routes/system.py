"""系统相关路由"""

from fastapi import APIRouter, Depends

from easyths import __version__
from easyths.api.dependencies.common import get_automator
from easyths.api.responses import error_response
from easyths.core import operation_registry
from easyths.models.operations import APIResponse, ErrorCode, OperationStatus

router = APIRouter(prefix="/api/v1/system", tags=["系统"])


@router.get("/health", response_model=None)
async def health_check(automator=Depends(get_automator)):
    """健康检查（真实探活：连接标志 + 同花顺进程存活）"""
    connected = automator.is_connected()
    process_alive = automator.is_process_alive()

    if connected and process_alive:
        return APIResponse(
            success=True,
            message="系统运行正常",
            data={
                "status": "healthy",
                "automator": "connected",
                "plugins": {"loaded": len(operation_registry.list_operations())},
            },
        )
    reason = "同花顺未连接" if not connected else "同花顺进程已退出"
    return APIResponse(
        success=False,
        message=f"系统异常: {reason}",
        error_code=ErrorCode.NOT_CONNECTED if not connected else ErrorCode.UI_ERROR,
        data={
            "status": "unhealthy",
            "automator": "connected" if connected else "disconnected",
            "process_alive": process_alive,
            "plugins": {"loaded": len(operation_registry.list_operations())},
        },
    )


@router.get("/status", response_model=APIResponse)
async def get_system_status(automator=Depends(get_automator)) -> APIResponse:
    """获取系统详细状态（含插件清单与参数 schema）"""
    operations = operation_registry.list_operations()
    is_connected = automator.is_connected()

    return APIResponse(
        success=True,
        message="查询成功",
        data={
            "name": "同花顺交易自动化系统",
            "version": __version__,
            "description": "基于pywinauto的同花顺交易软件自动化系统",
            "automator": {
                "connected": is_connected,
                "process_alive": automator.is_process_alive(),
                "app_path": automator.app_path,
                "backend": "uia",
            },
            "plugins": {
                "loaded_plugins": list(operations.keys()),
                "plugin_count": len(operations),
                "plugin_details": operations,
            },
        },
    )


@router.post("/reconnect", response_model=None)
async def reconnect(automator=Depends(get_automator)):
    """重连同花顺（客户端重启后恢复服务）"""
    if automator.reconnect():
        return APIResponse(
            success=True, message="同花顺重连成功", status=OperationStatus.COMPLETED
        )
    return error_response(
        503, "同花顺重连失败，请检查客户端是否已启动", ErrorCode.NOT_CONNECTED
    )
