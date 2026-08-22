"""数据模型：操作状态/错误码/统一响应信封/操作与参数基类。

对外统一响应形状（REST / MCP / SDK 三端一致）::

    {
        "success": bool | null,     # 终态业务结果；非终态（排队/执行中）为 null
        "status": "queued|running|completed|failed|cancelled" | null,
        "message": str,
        "error_code": ErrorCode | null,
        "data": Any,
        "timestamp": "2026-08-22 06:46:56"   # 北京时间，秒级
    }
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_serializer

#: 对外时间戳统一使用北京时间
BEIJING_TZ = ZoneInfo("Asia/Shanghai")

#: 对外时间戳格式（GUI 操作秒级精度足够）
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_beijing() -> datetime:
    """当前北京时间"""
    return datetime.now(BEIJING_TZ)


def _timestamp_text(value: datetime) -> str:
    """时间戳序列化为北京时间秒级文本"""
    return value.astimezone(BEIJING_TZ).strftime(TIMESTAMP_FORMAT)


class OperationStatus(StrEnum):
    """操作状态"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: 终态集合
TERMINAL_STATUSES = (
    OperationStatus.COMPLETED,
    OperationStatus.FAILED,
    OperationStatus.CANCELLED,
)


class ErrorCode(StrEnum):
    """统一错误码：操作失败分类与 API 错误共用同一词表，调用方可据此编程处理"""

    INVALID_PARAMS = "invalid_params"  # 参数校验未过（提交时即为 422）
    NOT_CONNECTED = "not_connected"  # 同花顺未连接
    CLIENT_REJECTED = "client_rejected"  # 同花顺拒绝：涨跌停/资金不足/标的不支持等
    UI_ERROR = "ui_error"  # 控件定位失败等界面异常
    CANCELLED = "cancelled"  # 排队中被取消
    TIMEOUT = "timeout"  # 等待结果超时（操作仍在执行）
    NOT_FOUND = "not_found"  # 操作 ID 不存在或已淘汰
    INTERNAL = "internal"  # 内部错误


class OperationResult(BaseModel):
    """操作终态结果"""

    status: OperationStatus
    success: bool
    data: Any = None
    message: str | None = None
    error_code: ErrorCode | None = None
    timestamp: datetime = Field(default_factory=now_beijing)

    @field_serializer("timestamp")
    def _serialize_timestamp(self, value: datetime) -> str:
        return _timestamp_text(value)


class Operation(BaseModel):
    """一次排队执行的操作"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=10)
    status: OperationStatus = OperationStatus.QUEUED
    result: OperationResult | None = None
    created_at: datetime = Field(default_factory=now_beijing)
    completed_at: datetime | None = None

    def update_status(self, status: OperationStatus) -> None:
        """更新状态，进入终态时记录完成时间（TTL 淘汰依据）"""
        self.status = status
        if status in TERMINAL_STATUSES:
            self.completed_at = datetime.now()


class APIResponse[DataT](BaseModel):
    """对外统一响应信封（REST 全端点 / MCP 工具返回 / SDK 解析目标）。

    泛型参数用于 OpenAPI 契约（如 ``APIResponse[SubmitResult]``）；
    未参数化时 ``data`` 为 Any。
    """

    success: bool | None = None
    status: OperationStatus | None = None
    message: str = ""
    error_code: ErrorCode | None = None
    data: DataT | None = None
    timestamp: datetime = Field(default_factory=now_beijing)

    @field_serializer("timestamp")
    def _serialize_timestamp(self, value: datetime) -> str:
        return _timestamp_text(value)

    @classmethod
    def from_result(cls, result: OperationResult) -> "APIResponse[Any]":
        """由操作终态结果构造响应（业务数据直接放 data，不再双层嵌套）"""
        return cls(
            success=result.success,
            status=result.status,
            message=result.message or "",
            error_code=result.error_code,
            data=result.data,
            timestamp=result.timestamp,
        )


class OperationParams(BaseModel):
    """操作参数基类：参数契约的唯一来源（REST 提交校验、执行期校验、接口文档共用）"""

    model_config = ConfigDict(extra="forbid")


class EmptyParams(OperationParams):
    """无参数操作占位"""
