"""
速率限制中间件
"""

import time
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单的速率限制中间件"""

    def __init__(self, app, calls: int = 100, period: int = 1):
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
        self.clients: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 获取客户端IP
        client_ip = request.client.host if request.client else "unknown"

        # 获取当前时间
        now = time.time()

        # 清理过期记录，并淘汰已无近期请求的IP，防止字典无限增长
        for ip in list(self.clients):
            self.clients[ip] = [
                timestamp
                for timestamp in self.clients[ip]
                if now - timestamp < self.period
            ]
            if not self.clients[ip]:
                del self.clients[ip]

        # 检查是否超过限制
        recent = self.clients.setdefault(client_ip, [])
        if len(recent) >= self.calls:
            logger.warning(
                "速率限制触发",
                ip=client_ip,
                requests=len(recent),
                limit=self.calls,
            )
            # 注意：BaseHTTPMiddleware 中 raise HTTPException 会变成 500，
            # 必须直接返回响应
            return JSONResponse(
                status_code=429, content={"detail": "Too many requests"}
            )

        # 记录当前请求
        recent.append(now)

        # 执行请求
        response = await call_next(request)

        # 添加速率限制响应头
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.calls - len(self.clients[client_ip]))
        )
        response.headers["X-RateLimit-Reset"] = str(int(now + self.period))

        return response
