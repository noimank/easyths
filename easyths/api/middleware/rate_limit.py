"""
速率限制中间件
"""
import time
from typing import Callable, Dict
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单的速率限制中间件"""

    def __init__(self, app, calls: int = 10, period: int = 1):
        """
        初始化速率限制

        Args:
            app: ASGI应用
            calls: 允许的请求数
            period: 时间窗口（秒）
        """
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients: Dict[str, list] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 获取客户端IP
        client_ip = request.client.host

        # 获取当前时间
        now = time.time()

        # 清理过期记录
        if client_ip in self.clients:
            self.clients[client_ip] = [
                timestamp for timestamp in self.clients[client_ip]
                if now - timestamp < self.period
            ]
        else:
            self.clients[client_ip] = []

        # 检查是否超过限制
        if len(self.clients[client_ip]) >= self.calls:
            logger.warning(
                "速率限制触发",
                ip=client_ip,
                requests=len(self.clients[client_ip]),
                limit=self.calls
            )
            raise HTTPException(
                status_code=429,
                detail="Too many requests"
            )

        # 记录当前请求
        self.clients[client_ip].append(now)

        # 执行请求
        response = await call_next(request)

        # 添加速率限制响应头
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.calls - len(self.clients[client_ip]))
        )
        response.headers["X-RateLimit-Reset"] = str(
            int(now + self.period)
        )

        return response