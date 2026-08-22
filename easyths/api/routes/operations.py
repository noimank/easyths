"""操作路由 - 按注册表为每个操作生成带参数校验的执行端点。

POST /api/v1/operations/{name} 的请求体即该操作的参数模型字段
（可附带可选的 priority 与 account_name 字段），非法/未知参数在提交时
即返回 422，而不是排队执行后才失败。

account_name 为执行前指令：队列在执行目标操作前先切换到该账户
（不指定则用当前账户）。account_switch 自身的 account_name 是业务参数，
该端点不注入此指令字段。
"""

import asyncio
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import Field, create_model
from starlette.responses import Response

from easyths.api.dependencies.common import get_operation_queue
from easyths.api.responses import error_response, json_response
from easyths.core import operation_registry
from easyths.models.operations import (
    APIResponse,
    ErrorCode,
    Operation,
    OperationStatus,
)
from easyths.operations.results import SubmitResult


def _build_execute_route(router: APIRouter, name: str) -> None:
    """为单个操作生成类型化的 POST 端点（继承参数模型 + priority + account_name）"""
    operation_class = operation_registry.get_operation_class(name)
    fields: dict[str, Any] = {
        "priority": (
            int,
            Field(default=0, ge=0, le=10, description="优先级，越大越先执行"),
        ),
    }
    # account_switch 的 account_name 是业务参数，不注入执行指令字段
    inject_account = "account_name" not in operation_class.Params.model_fields
    if inject_account:
        fields["account_name"] = (
            str | None,
            Field(
                default=None,
                min_length=1,
                description="执行前切换到该账户（不指定则用当前账户）",
            ),
        )
    request_model = create_model(
        f"Execute{''.join(part.title() for part in name.split('_'))}Request",
        **fields,
        __base__=operation_class.Params,
    )

    @router.post(
        f"/{name}",
        response_model=APIResponse[SubmitResult],
        name=f"execute_{name}",
        summary=operation_class.description or name,
    )
    async def execute_operation(
        request: request_model,  # type: ignore[valid-type]
        queue=Depends(get_operation_queue),
    ) -> Response | APIResponse[SubmitResult]:
        exclude = {"priority", "account_name"} if inject_account else {"priority"}
        operation = Operation(
            name=name,
            params=request.model_dump(exclude=exclude),  # type: ignore[attr-defined]
            priority=request.priority,  # type: ignore[attr-defined]
            account_name=request.account_name if inject_account else None,  # type: ignore[attr-defined]
        )
        try:
            operation_id = queue.submit(operation)
        except ValueError as e:
            # 队列满属服务端过载
            return error_response(503, str(e), ErrorCode.INTERNAL)

        # 仅受理，尚未到终态，success 保持 null（约定：非终态为 null）
        return APIResponse(
            status=operation.status,
            message="操作已添加到队列",
            data=SubmitResult(
                operation_id=operation_id,
                queue_position=queue.get_queue_stats()["queued_count"],
            ),
        )


def create_operations_router() -> APIRouter:
    """构建操作路由（需在插件加载完成后调用）"""
    router = APIRouter(prefix="/api/v1/operations", tags=["操作"])

    for operation_name in operation_registry.list_operations():
        _build_execute_route(router, operation_name)

    @router.get("/", response_model=APIResponse, name="list_operations")
    async def list_operations() -> APIResponse:
        """获取所有可用操作（含参数 schema）"""
        operations = operation_registry.list_operations()
        return APIResponse(
            success=True,
            message="查询成功",
            data={"operations": operations, "count": len(operations)},
        )

    @router.get("/{operation_id}/status", response_model=None)
    async def get_operation_status(
        operation_id: str, queue=Depends(get_operation_queue)
    ):
        """获取操作状态快照（非阻塞）"""
        operation = queue.get_state(operation_id)
        if not operation:
            return error_response(404, "操作不存在", ErrorCode.NOT_FOUND)

        result = operation.result
        return APIResponse(
            success=result.success if result else None,
            status=operation.status,
            message=result.message if result else "",
            error_code=result.error_code if result else None,
            data=result.data if result else None,
        )

    @router.get("/{operation_id}/result", response_model=None)
    async def get_operation_result(
        operation_id: str,
        timeout: float | None = None,
        queue=Depends(get_operation_queue),
    ):
        """阻塞等待并获取操作终态结果

        - 404: 操作不存在（或结果已被淘汰）
        - 408: 等待超时，操作仍在排队/执行（响应体含当前 status）
        """
        if not queue.get_state(operation_id):
            return error_response(404, "操作不存在", ErrorCode.NOT_FOUND)

        # get_result 是同步阻塞等待，放到线程池避免卡死事件循环
        try:
            result = await asyncio.to_thread(
                queue.get_result, operation_id, timeout=timeout
            )
        except KeyError:
            return error_response(404, "操作不存在", ErrorCode.NOT_FOUND)

        if result is None:
            current = queue.get_state(operation_id)
            status_text = current.status.value if current else "unknown"
            return json_response(
                APIResponse(
                    success=None,
                    status=current.status if current else None,
                    message=f"等待超时，操作仍在{status_text}",
                    error_code=ErrorCode.TIMEOUT,
                ),
                408,
            )

        return APIResponse.from_result(result)

    @router.delete("/{operation_id}", response_model=APIResponse)
    async def cancel_operation(
        operation_id: str, queue=Depends(get_operation_queue)
    ) -> Response | APIResponse:
        """取消排队中的操作"""
        if not queue.cancel_operation(operation_id):
            return error_response(
                404, "操作不存在或已开始执行，无法取消", ErrorCode.NOT_FOUND
            )
        return APIResponse(
            success=True, message="操作已取消", status=OperationStatus.CANCELLED
        )

    return router
