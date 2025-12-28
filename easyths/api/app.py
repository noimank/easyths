"""FastAPI应用主文件 - 同步架构适配

Author: noimank
Email: noimank@163.com
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from easyths.api.middleware import LoggingMiddleware, RateLimitMiddleware, IPWhitelistMiddleware, APIKeyAuthMiddleware
from easyths.api.routes import system_router, operations_router, queue_router
from easyths.api.dependencies.common import set_global_instances
from easyths.utils import project_config_instance
from easyths.core.base_operation import operation_registry
from easyths.api.routes.mcp_server import set_queue, mcp_asgi_app

logger = structlog.get_logger(__name__)


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
        # 创建应用实例
        self.app = FastAPI(
            title="同花顺交易自动化API",
            description="提供同花顺交易软件自动化操作接口",
            version=project_config_instance.app_version,
            lifespan=self.lifespan
        )

        # 设置全局实例
        set_global_instances(self.operation_queue, self.automator)

        # 添加中间件
        self._add_middleware()

        # 添加路由
        self._add_routes()

        return self.app

    def _add_middleware(self):
        """添加中间件"""
        # IP白名单中间件（最先执行）
        self.app.add_middleware(
            IPWhitelistMiddleware,
            allowed_hosts=project_config_instance.api_ip_whitelist_list
        )

        # API密钥认证中间件
        self.app.add_middleware(APIKeyAuthMiddleware)

        # CORS中间件
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=project_config_instance.api_cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )

        # 日志中间件
        self.app.add_middleware(LoggingMiddleware)
        rate_limit = project_config_instance.api_rate_limit
        # 速率限制中间件
        if rate_limit > 0:
            self.app.add_middleware(
                RateLimitMiddleware,
                calls=rate_limit,
                period=1
            )

    def _add_routes(self):
        """添加路由"""
        # 根路径
        @self.app.get("/")
        async def root():
            return {
                "message": "同花顺交易自动化API",
                "version": project_config_instance.app_version,
                "docs": "/docs"
            }

        # API路由
        self.app.include_router(system_router)
        self.app.include_router(operations_router)
        self.app.include_router(queue_router)

        # MCP 服务器路由 (在插件加载后挂载)
        # 注意：MCP 应用需要在插件加载完成后初始化，因此在 lifespan 中挂载
        self._mcp_app = None

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """应用生命周期管理 - 整合 FastAPI 和 MCP 服务器的生命周期"""

        # ========== 启动阶段 ==========
        logger.info("正在启动交易API服务...")
        # 加载插件
        operation_registry.load_plugins()

        # 设置 MCP 服务器的队列引用并挂载
        set_queue(self.operation_queue)
        self.app.mount("/api", mcp_asgi_app)
        logger.info(f"MCP 服务器已挂载到 /api/mcp-server (传输类型: {project_config_instance.api_mcp_server_type})")

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

        uvicorn.run(
            self.app,
            host=project_config_instance.api_host,
            port=project_config_instance.api_port,
            log_level="info",
            ws="wsproto"  # 使用 wsproto 替代 websockets，避免弃用警告
        )
