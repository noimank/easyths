from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class OperationStatus(Enum):
    """操作状态枚举"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class OperationResult(BaseModel):
    """操作结果模型"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Operation(BaseModel):
    """操作模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=10)
    status: OperationStatus = OperationStatus.QUEUED
    result: Optional[OperationResult] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            OperationStatus: lambda v: v.value
        }

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump(exclude_none=True)

    def update_status(self, status: OperationStatus, error: Optional[str] = None):
        """更新状态"""
        self.status = status
        if error:
            self.error = error
        self.timestamp = datetime.now()


class PluginMetadata(BaseModel):
    """插件元数据模型"""
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    author: Optional[str] = None
    operation_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            type: lambda v: v.__name__ if hasattr(v, '__name__') else str(v)
        }


class APIResponse(BaseModel):
    """API响应模型"""
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }