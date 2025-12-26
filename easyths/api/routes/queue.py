"""
队列相关路由
"""
from fastapi import APIRouter, Depends

from easyths.models.operations import APIResponse
from easyths.api.dependencies.common import get_operation_queue

router = APIRouter(prefix="/api/v1/queue", tags=["队列"])


@router.get("/stats")
async def get_queue_stats(
    queue = Depends(get_operation_queue)
) -> APIResponse:
    """获取队列统计信息"""
    stats = queue.get_queue_stats()

    return APIResponse(
        success=True,
        message="查询成功",
        data=stats
    )