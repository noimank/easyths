"""
API密钥认证中间件
"""

import secrets
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from easyths.api.responses import error_response
from easyths.models.operations import ErrorCode
from easyths.utils import project_config_instance

logger = structlog.get_logger(__name__)

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """API密钥认证中间件

    验证请求中的 Bearer Token 是否与配置的 API Key 一致。
    认证只覆盖 API 数据面（``/api/*``，REST 与 MCP）；内嵌控制台页面、
    静态资源与接口文档不含敏感数据，公开访问，凭 API Key 取数。
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
            logger.warning(
                "配置文件 [api] key 未设置, 生产环境可能存在被非法调用的风险，请注意"
            )

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

        # 页面/静态资源/文档不在数据面，跳过认证
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        # 获取 Authorization 头
        credentials = await security(request)

        if credentials is None:
            logger.warning("缺少认证凭据", path=request.url.path)
            response = error_response(
                401, "缺少认证凭据，请提供有效的 Bearer Token", ErrorCode.UNAUTHORIZED
            )
            response.headers["WWW-Authenticate"] = "Bearer"
            return response

        api_key = credentials.credentials

        # 常数时间比较，避免时序侧信道（auth_enabled 已保证 expected_key 非空）
        if not secrets.compare_digest(api_key.encode(), self.expected_key.encode()):
            # 只记长度不记内容，避免真实密钥片段落入日志文件
            logger.warning(
                "无效的API密钥访问尝试",
                path=request.url.path,
                key_length=len(api_key),
            )
            response = error_response(401, "API密钥无效", ErrorCode.UNAUTHORIZED)
            response.headers["WWW-Authenticate"] = "Bearer"
            return response

        logger.info("API访问验证成功", path=request.url.path)
        return await call_next(request)
