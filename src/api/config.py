"""
API配置相关
"""
from typing import Dict, Any
from pydantic import BaseSettings


class APISettings(BaseSettings):
    """API配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    title: str = "同花顺交易自动化API"
    description: str = "提供同花顺交易软件自动化操作接口"
    version: str = "1.0.0"
    debug: bool = False
    cors_origins: list = ["*"]
    rate_limit: int = 10  # 每秒请求数
    api_key: str = None  # API密钥（可选）

    class Config:
        env_file = ".env"
        env_prefix = "API_"


class OperationSettings(BaseSettings):
    """操作相关配置"""
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    batch_size: int = 10

    class Config:
        env_file = ".env"
        env_prefix = "OP_"