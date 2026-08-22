"""FastAPI应用主文件 - 同步架构适配

Author: noimank
Email: noimank@163.com
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

from easyths import __version__
from easyths.api.dependencies.common import set_global_instances
from easyths.api.middleware import (
    APIKeyAuthMiddleware,
    IPWhitelistMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
)
from easyths.api.responses import error_response
from easyths.api.routes import queue_router, system_router
from easyths.api.routes.mcp_server import mcp_asgi_app, set_queue
from easyths.api.routes.operations import create_operations_router
from easyths.core.base_operation import operation_registry
from easyths.models.operations import ErrorCode
from easyths.utils import get_asset_path, project_config_instance

logger = structlog.get_logger(__name__)

#: 内嵌 Web 控制台的静态资源目录（认证豁免，数据请求凭 API Key 访问 /api）
WEB_DIR = get_asset_path() / "web"


class TradingAPIApp:
    """交易API应用类"""

    def __init__(self, operation_queue, automator=None):
        """初始化API应用

        Args:
            operation_queue: 操作队列实例
            automator: 自动化器实例（可选）
        """
        self.operation_queue = operation_queue
        self.automator = automator
        self.app = None

    def create_app(self) -> FastAPI:
        """创建FastAPI应用"""
        # 操作路由按注册表生成，必须先加载插件
        # （幂等：main 启动流程已加载过则此处为 no-op，独立创建应用时自动加载）
        operation_registry.load_plugins()

        self.app = FastAPI(
            title="同花顺交易自动化API",
            description="提供同花顺交易软件自动化操作接口",
            version=__version__,
            lifespan=self.lifespan,
        )

        # 设置全局实例
        set_global_instances(self.operation_queue, self.automator)

        # 参数校验失败也用统一信封返回
        @self.app.exception_handler(RequestValidationError)
        async def validation_error_handler(
            request: Request, exc: RequestValidationError
        ):
            return error_response(422, "请求参数校验失败", ErrorCode.INVALID_PARAMS)

        # 添加中间件
        self._add_middleware()

        # 添加路由
        self._add_routes()

        return self.app

    def _add_middleware(self):
        """添加中间件

        Starlette 中后 add_middleware 的中间件位于外层，实际请求处理顺序与
        添加顺序相反。目标执行顺序（外→内）：
            IPWhitelist → Logging → RateLimit → CORS → APIKeyAuth
        - 白名单最外层：非法IP不消耗任何后续处理
        - CORS 在认证外层：预检 OPTIONS 请求不携带凭据，不会被 401 拦截
        """
        self.app.add_middleware(APIKeyAuthMiddleware)

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=project_config_instance.api_cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        rate_limit = project_config_instance.api_rate_limit
        if rate_limit > 0:
            self.app.add_middleware(RateLimitMiddleware, calls=rate_limit, period=1)

        self.app.add_middleware(LoggingMiddleware)

        self.app.add_middleware(
            IPWhitelistMiddleware,
            allowed_hosts=project_config_instance.api_ip_whitelist_list,
        )

    def _add_routes(self):
        """添加路由"""

        # 根路径：内嵌 Web 控制台（页面公开，数据请求由认证中间件校验 API Key）
        @self.app.get("/", include_in_schema=False)
        async def root():
            return FileResponse(WEB_DIR / "index.html")

        # 静态资源（前缀与 /api 隔离，不干扰 REST/MCP 路由匹配）
        self.app.mount("/static", StaticFiles(directory=WEB_DIR), name="web")

        # API路由
        self.app.include_router(system_router)
        self.app.include_router(create_operations_router())
        self.app.include_router(queue_router)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """应用生命周期管理 - 整合 FastAPI 和 MCP 服务器的生命周期"""

        logger.info("正在启动交易API服务...")

        # 设置 MCP 服务器的队列引用并挂载
        set_queue(self.operation_queue)
        self.app.mount("/api", mcp_asgi_app)
        logger.info(
            f"MCP 服务器已挂载到 /api/mcp-server (传输类型: {project_config_instance.api_mcp_server_type})"
        )

        # 使用 FastMCP 的 lifespan 管理 session_manager (最佳实践)
        # mcp_asgi_app.lifespan 会正确初始化和管理 MCP session manager
        async with mcp_asgi_app.lifespan(app):
            # 队列已经在main.py中启动，这里不需要再次启动
            logger.info("交易API服务启动完成")
            yield

        # ========== 关闭阶段 ==========
        # mcp_asgi_app.lifespan 的上下文退出时会自动清理 session_manager
        logger.info("正在关闭交易API服务...")
        logger.info("交易API服务已关闭")

    def run(self):
        """运行API服务"""
        import uvicorn

        assert self.app is not None, "必须先调用 create_app() 创建应用"
        uvicorn.run(
            self.app,
            host=project_config_instance.api_host,
            port=project_config_instance.api_port,
            log_level="info",
            ws="wsproto",  # 使用 wsproto 替代 websockets，避免弃用警告
        )
