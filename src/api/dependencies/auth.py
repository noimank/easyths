"""
认证相关依赖项
"""
from typing import Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

logger = structlog.get_logger(__name__)

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


async def get_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """获取API密钥

    Args:
        credentials: HTTP认证凭据

    Returns:
        Optional[str]: API密钥或None
    """
    if credentials:
        return credentials.credentials
    return None


async def get_current_user(
    api_key: Optional[str] = Depends(get_api_key)
) -> dict:
    """获取当前用户信息

    Args:
        api_key: API密钥

    Returns:
        dict: 用户信息

    Raises:
        HTTPException: 认证失败
    """
    # 这里可以实现更复杂的用户认证逻辑
    # 例如：从数据库验证API密钥

    # 暂时返回默认用户
    if api_key:
        logger.info(f"API访问", api_key=api_key[:8] + "...")
        return {
            "user_id": "default",
            "api_key": api_key,
            "permissions": ["read", "write"]
        }
    else:
        # 允许无密钥访问（仅开发环境）
        logger.warning("无API密钥访问")
        return {
            "user_id": "anonymous",
            "api_key": None,
            "permissions": ["read"]
        }