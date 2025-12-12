"""
操作相关路由
"""
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from src.models.operations import (
    Operation, OperationStatus, OperationType, APIResponse,
    BatchOperationRequest
)
from src.api.dependencies.common import get_operation_queue, get_operation_manager
from src.automation.base_operation import operation_registry

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
    background_tasks: BackgroundTasks,
    queue = Depends(get_operation_queue)
) -> APIResponse:
    """执行操作"""
    # 验证操作是否存在
    operation_class = queue.operation_registry.get_operation_class(operation_name)
    if not operation_class:
        raise HTTPException(
            status_code=404,
            detail=f"操作 '{operation_name}' 不存在"
        )

    # 创建操作
    operation = Operation(
        name=operation_name,
        type=OperationType.CUSTOM,
        params=request.params,
        priority=request.priority
    )

    # 添加到队列
    success = await queue.put(operation)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="队列已满或操作无效"
        )

    return APIResponse(
        success=True,
        message="操作已添加到队列",
        data={
            "operation_id": operation.id,
            "status": operation.status.value,
            "queue_position": len(queue._queue)
        }
    )


@router.post("/batch")
async def execute_batch_operations(
    request: BatchOperationRequest,
    background_tasks: BackgroundTasks,
    queue = Depends(get_operation_queue)
) -> APIResponse:
    """执行批量操作"""
    operations = []

    for op_info in request.operations:
        # 验证操作是否存在
        operation_class = queue.operation_registry.get_operation_class(op_info["name"])
        if not operation_class:
            raise HTTPException(
                status_code=404,
                detail=f"操作 '{op_info['name']}' 不存在"
            )

        operation = Operation(
            name=op_info["name"],
            type=OperationType.CUSTOM,
            params=op_info.get("params", {}),
            priority=op_info.get("priority", 0)
        )

        # 如果是顺序执行，添加依赖关系
        if request.mode == "sequential" and operations:
            operation.dependencies.append(operations[-1].id)

        operations.append(operation)

    # 添加到队列
    success_count = 0
    for operation in operations:
        if await queue.put(operation):
            success_count += 1
        elif request.stop_on_error:
            break

    return APIResponse(
        success=True,
        message=f"批量操作已提交，成功添加 {success_count}/{len(operations)} 个操作",
        data={
            "operations": [
                {
                    "operation_id": op.id,
                    "name": op.name,
                    "status": op.status.value
                }
                for op in operations
            ],
            "success_count": success_count,
            "total_count": len(operations)
        }
    )


@router.get("/{operation_id}/status")
async def get_operation_status(
    operation_id: str,
    queue = Depends(get_operation_queue)
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
            "status": operation.status.value,
            "result": operation.result.dict() if operation.result else None,
            "error": operation.error,
            "timestamp": operation.timestamp.isoformat(),
            "retry_count": operation.retry_count
        }
    )


@router.delete("/{operation_id}")
async def cancel_operation(
    operation_id: str,
    queue = Depends(get_operation_queue)
) -> APIResponse:
    """取消操作"""
    success = await queue.cancel_operation(operation_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail="操作不存在或无法取消"
        )

    return APIResponse(
        success=True,
        message="操作已取消"
    )


@router.post("/{operation_id}/retry")
async def retry_operation(
    operation_id: str,
    queue = Depends(get_operation_queue)
) -> APIResponse:
    """重试失败的操作"""
    success = await queue.retry_operation(operation_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail="操作不存在或无法重试"
        )

    return APIResponse(
        success=True,
        message="操作已重新入队"
    )


@router.get("/")
async def list_operations(
    manager = Depends(get_operation_manager)
) -> APIResponse:
    """获取所有可用操作"""
    operations = manager.get_plugin_info()

    return APIResponse(
        success=True,
        message="查询成功",
        data=operations
    )