"""
操作相关路由 - 适配同步队列
"""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from easyths.api.dependencies.common import get_operation_queue
from easyths.core import operation_registry
from easyths.models.operations import Operation, APIResponse

router = APIRouter(prefix="/api/v1/operations", tags=["操作"])


# 请求/响应模型
class ExecuteOperationRequest(BaseModel):
    """执行操作请求"""
    params: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=10)


@router.post("/{operation_name}")
async def execute_operation(
        operation_name: str,
        request: ExecuteOperationRequest,
        queue=Depends(get_operation_queue)
) -> APIResponse:
    """执行操作"""
    # 验证操作是否存在
    operation_class = operation_registry.get_operation_class(operation_name)
    if not operation_class:
        raise HTTPException(
            status_code=404,
            detail=f"操作 '{operation_name}' 不存在"
        )

    # 创建操作
    operation = Operation(
        name=operation_name,
        params=request.params,
        priority=request.priority
    )

    # 添加到队列（同步方法）
    try:
        operation_id = queue.submit(operation)
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    return APIResponse(
        success=True,
        message="操作已添加到队列",
        data={
            "operation_id": operation_id,
            "status": operation.status.value,
            "queue_position": queue.get_queue_stats()["queued_count"]
        }
    )


@router.get("/{operation_id}/status")
async def get_operation_status(
        operation_id: str,
        queue=Depends(get_operation_queue)
) -> APIResponse:
    """获取操作状态"""
    operation = queue.get_operation(operation_id)

    if not operation:
        raise HTTPException(
            status_code=404,
            detail="操作不存在"
        )

    return APIResponse(
        success=True,
        message="查询成功",
        data={
            "operation_id": operation_id,
            "name": operation.name,
            "status": operation.status.value if operation.status else None,
            "result": operation.result.dict() if operation.result else None,
            "error": operation.error,
            "timestamp": operation.timestamp.isoformat() if operation.timestamp else None,
            "retry_count": operation.retry_count
        }
    )


@router.get("/{operation_id}/result")
async def get_operation_result(
        operation_id: str,
        timeout: float = None,
        queue=Depends(get_operation_queue)
) -> APIResponse:
    """获取操作结果（阻塞等待）"""
    result = queue.get_result(operation_id, timeout=timeout)

    if result is None:
        raise HTTPException(
            status_code=408,
            detail="操作未完成或超时"
        )

    return APIResponse(
        success=True,
        message="查询成功",
        data={
            "operation_id": operation_id,
            "result": result.dict()
        }
    )


@router.delete("/{operation_id}")
async def cancel_operation(
        operation_id: str,
        queue=Depends(get_operation_queue)
) -> APIResponse:
    """取消操作"""
    # 同步方法
    success = queue.cancel_operation(operation_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail="操作不存在或无法取消"
        )

    return APIResponse(
        success=True,
        message="操作已取消"
    )


@router.get("/")
async def list_operations() -> APIResponse:
    """获取所有可用操作"""
    operations = operation_registry.list_operations()

    return APIResponse(
        success=True,
        message="查询成功",
        data={
            "operations": operations,
            "count": len(operations)
        }
    )
