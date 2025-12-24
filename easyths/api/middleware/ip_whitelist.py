"""
IP白名单中间件
"""
from typing import Callable, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
import json

logger = structlog.get_logger(__name__)


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """IP白名单中间件

    只有在白名单中的IP地址才能访问API，默认允许所有IP访问
    """

    def __init__(self, app, allowed_hosts: List[str] | None = None):
        """初始化中间件

        Args:
            app: FastAPI应用实例
            allowed_hosts: 允许访问的IP/域名列表，None或空列表表示允许所有
        """
        super().__init__(app)
        # 将None转换为空列表
        self.allowed_hosts = set(allowed_hosts) if allowed_hosts else set()
        self.allow_all = len(self.allowed_hosts) == 0

        if not self.allow_all:
            logger.info("IP白名单已启用", allowed_hosts=list(self.allowed_hosts))
        else:
            logger.info("IP白名单未启用，允许所有IP访问")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求

        Args:
            request: 请求对象
            call_next: 下一个中间件/路由处理器

        Returns:
            Response: 响应对象
        """
        # 如果允许所有，直接放行
        if self.allow_all:
            return await call_next(request)

        # 获取客户端IP
        client_host = self._get_client_host(request)

        # 检查IP是否在白名单中
        if self._is_host_allowed(client_host):
            return await call_next(request)

        # IP不在白名单中，记录并返回403
        logger.error("IP访问被拒绝", client_ip=client_host, path=request.url.path)
        message = {
            "error": "Access denied",
            "message": "Your IP is not in the whitelist",
            "ip": client_host
        }
        return Response(
            content=json.dumps(message),
            status_code=403,
            media_type="application/json"
        )

    def _get_client_host(self, request: Request) -> str:
        """获取客户端真实IP

        支持代理服务器转发的真实IP

        Args:
            request: 请求对象

        Returns:
            str: 客户端IP地址
        """
        # 检查是否通过代理，优先从X-Forwarded-For获取真实IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For可能包含多个IP，取第一个
            return forwarded_for.split(",")[0].strip()

        # 检查X-Real-IP头
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # 从直接连接获取IP
        return request.client.host if request.client else "unknown"

    def _is_host_allowed(self, host: str) -> bool:
        """检查主机是否允许访问

        Args:
            host: 主机地址

        Returns:
            bool: 是否允许访问
        """
        if not host:
            return False

        # 精确匹配
        if host in self.allowed_hosts:
            return True

        # 检查通配符匹配
        for allowed in self.allowed_hosts:
            if allowed.startswith("*"):
                # 后缀匹配，如 *.example.com
                suffix = allowed[1:]
                if host.endswith(suffix):
                    return True
            elif allowed.endswith("*"):
                # 前缀匹配，如 192.168.*
                prefix = allowed[:-1]
                if host.startswith(prefix):
                    return True

        return False
