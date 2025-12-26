"""
API密钥认证中间件
"""
from typing import Callable
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.security import HTTPBearer
import structlog
import json

from easyths.utils import project_config_instance

logger = structlog.get_logger(__name__)

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """API密钥认证中间件

    验证请求中的 Bearer Token 是否与配置的 API Key 一致
    """

    def __init__(self, app):
        """初始化中间件

        Args:
            app: FastAPI应用实例
        """
        super().__init__(app)
        self.expected_key = project_config_instance.api_key
        self.auth_enabled = bool(self.expected_key)

        if self.auth_enabled:
            logger.info("API密钥认证已启用")
        else:
            logger.warning("API_KEY环境变量未设置, 生产环境可能存在被非法调用的风险，请注意")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求

        Args:
            request: 请求对象
            call_next: 下一个中间件/路由处理器

        Returns:
            Response: 响应对象
        """
        # 如果未启用认证，直接放行
        if not self.auth_enabled:
            return await call_next(request)

        # 跳过文档路径的认证
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # 获取 Authorization 头
        credentials = await security(request)

        if credentials is None:
            logger.warning("缺少认证凭据", path=request.url.path)
            message = {
                "error": "Unauthorized",
                "message": "Missing authentication credentials",
                "detail": "请提供有效的 Bearer Token"
            }
            return Response(
                content=json.dumps(message),
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"}
            )

        api_key = credentials.credentials

        if api_key != self.expected_key:
            logger.warning("无效的API密钥访问尝试", path=request.url.path, provided_key=api_key[:8] + "...")
            message = {
                "error": "Unauthorized",
                "message": "Invalid API key",
                "detail": "API密钥无效"
            }
            return Response(
                content=json.dumps(message),
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"}
            )

        logger.info("API访问验证成功", path=request.url.path)
        return await call_next(request)
