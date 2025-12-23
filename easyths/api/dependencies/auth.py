"""
API密钥认证依赖项
"""
import os
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

logger = structlog.get_logger(__name__)

# HTTP Bearer 认证方案
security = HTTPBearer()


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> bool:
    """验证API密钥

    Args:
        credentials: HTTP认证凭据

    Returns:
        bool: 验证结果

    Raises:
        HTTPException: 认证失败
    """
    api_key = credentials.credentials
    expected_key = os.getenv("API_KEY")

    if not expected_key:
        logger.error("API_KEY环境变量未设置")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器配置错误"
        )

    if api_key != expected_key:
        logger.warning("无效的API密钥访问尝试", provided_key=api_key[:8] + "...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的API密钥",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("API访问验证成功")
    return True