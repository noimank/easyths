"""
日志中间件
"""

import time
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

# 敏感请求头：明文记录会泄漏凭据，统一脱敏
_SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key"}


def _sanitize_headers(headers) -> dict[str, str]:
    return {
        key: "***" if key.lower() in _SENSITIVE_HEADERS else value
        for key, value in headers.items()
    }


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 记录请求开始
        start_time = time.time()

        # 记录请求信息（敏感头脱敏）
        logger.info(
            "API请求开始",
            method=request.method,
            url=str(request.url),
            headers=_sanitize_headers(request.headers),
            query_params=dict(request.query_params),
        )

        # 执行请求
        response = await call_next(request)

        # 计算处理时间
        process_time = time.time() - start_time

        # 记录响应信息
        logger.info(
            "API请求完成",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=round(process_time, 4),
        )

        # 添加响应头
        response.headers["X-Process-Time"] = str(round(process_time, 4))

        return response
