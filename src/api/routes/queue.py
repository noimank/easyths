"""
队列相关路由
"""
from fastapi import APIRouter, Depends, HTTPException

from src.models.operations import APIResponse
from src.api.dependencies.common import get_operation_queue
from src.api.dependencies.auth import verify_api_key

router = APIRouter(prefix="/api/v1/queue", tags=["队列"])


@router.get("/stats")
async def get_queue_stats(
    api_valid: bool = Depends(verify_api_key),
    queue = Depends(get_operation_queue)
) -> APIResponse:
    """获取队列统计信息"""
    stats = queue.get_queue_stats()

    return APIResponse(
        success=True,
        message="查询成功",
        data=stats
    )


@router.post("/clear")
async def clear_queue(
    api_valid: bool = Depends(verify_api_key),
    queue = Depends(get_operation_queue)
) -> APIResponse:
    """清空队列"""
    await queue.clear()

    return APIResponse(
        success=True,
        message="队列已清空"
    )