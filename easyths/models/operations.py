import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OperationStatus(Enum):
    """操作状态枚举"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class OperationResult(BaseModel):
    """操作结果模型"""

    success: bool
    data: Any = None
    message: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class Operation(BaseModel):
    """操作模型"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=10)
    status: OperationStatus = OperationStatus.QUEUED
    result: OperationResult | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return self.model_dump(exclude_none=True)

    def update_status(self, status: OperationStatus, error: str | None = None):
        """更新状态"""
        self.status = status
        if error:
            self.error = error
        self.timestamp = datetime.now()


class PluginMetadata(BaseModel):
    """插件元数据模型"""

    name: str
    version: str = "1.0.0"
    description: str | None = None
    author: str | None = None
    operation_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class APIResponse(BaseModel):
    """API响应模型"""

    success: bool
    message: str
    data: Any | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
