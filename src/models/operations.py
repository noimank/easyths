from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class OperationStatus(Enum):
    """操作状态枚举"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class OperationType(Enum):
    """操作类型枚举"""
    CONNECT = "connect"
    LOGIN = "login"
    BUY = "buy"
    SELL = "sell"
    CANCEL = "cancel"
    QUERY_POSITIONS = "query_positions"
    QUERY_ORDERS = "query_orders"
    QUERY_FUNDS = "query_funds"
    CUSTOM = "custom"


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
    type: OperationType
    params: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=10)
    dependencies: List[str] = Field(default_factory=list)
    status: OperationStatus = OperationStatus.PENDING
    result: Optional[OperationResult] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    timeout: Optional[float] = Field(default=30.0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            OperationStatus: lambda v: v.value,
            OperationType: lambda v: v.value
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

    def can_retry(self) -> bool:
        """检查是否可以重试"""
        return self.retry_count < self.max_retries and self.status == OperationStatus.FAILED

    def increment_retry(self):
        """增加重试次数"""
        self.retry_count += 1
        self.status = OperationStatus.RETRYING


class PluginMetadata(BaseModel):
    """插件元数据模型"""
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    author: Optional[str] = None
    operation_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    enabled: bool = True

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


class BatchOperationRequest(BaseModel):
    """批量操作请求模型"""
    operations: List[Dict[str, Any]]
    mode: str = Field(default="sequential", pattern="^(sequential|parallel)$")
    stop_on_error: bool = False

    class Config:
        json_encoders = {
            type: lambda v: v.__name__ if hasattr(v, '__name__') else str(v)
        }