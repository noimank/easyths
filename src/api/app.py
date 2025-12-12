"""
FastAPI应用主文件
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from src.api.config import APISettings
from src.api.middleware import LoggingMiddleware, RateLimitMiddleware
from src.api.routes import system_router, operations_router, queue_router
from src.api.dependencies.common import set_global_instances
from src.utils.logger import init_audit_logger

logger = structlog.get_logger(__name__)


class TradingAPIApp:
    """交易API应用类"""

    def __init__(self, config: dict, automator, operation_queue, operation_manager):
        self.config = config
        self.settings = APISettings(**config.get('api', {}))
        self.automator = automator
        self.operation_queue = operation_queue
        self.operation_manager = operation_manager
        self.app = None

    def create_app(self) -> FastAPI:
        """创建FastAPI应用"""
        # 创建应用实例
        self.app = FastAPI(
            title=self.settings.title,
            description=self.settings.description,
            version=self.settings.version,
            lifespan=self.lifespan
        )

        # 设置全局实例
        set_global_instances(
            self.automator,
            self.operation_queue,
            self.operation_manager
        )

        # 添加中间件
        self._add_middleware()

        # 添加路由
        self._add_routes()

        return self.app

    def _add_middleware(self):
        """添加中间件"""
        # CORS中间件
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 日志中间件
        self.app.add_middleware(LoggingMiddleware)

        # 速率限制中间件
        if self.settings.rate_limit > 0:
            self.app.add_middleware(
                RateLimitMiddleware,
                calls=self.settings.rate_limit,
                period=1
            )

    def _add_routes(self):
        """添加路由"""
        # 根路径
        @self.app.get("/")
        async def root():
            return {
                "message": "同花顺交易自动化API",
                "version": self.settings.version,
                "docs": "/docs"
            }

        # API路由
        self.app.include_router(system_router)
        self.app.include_router(operations_router)
        self.app.include_router(queue_router)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """应用生命周期管理"""
        # 启动时执行
        logger.info("正在启动交易API服务...")

        # 初始化审计日志
        init_audit_logger(self.config.get('logging', {}))

        # 加载插件
        self.operation_manager.load_plugins()

        # 启动队列处理
        import asyncio
        asyncio.create_task(self.operation_queue.process_queue())

        logger.info("交易API服务启动完成")
        yield

        # 关闭时执行
        logger.info("正在关闭交易API服务...")
        await self.operation_queue.stop()
        await self.automator.disconnect()
        logger.info("交易API服务已关闭")

    def run(self):
        """运行API服务"""
        import uvicorn

        uvicorn.run(
            self.app,
            host=self.settings.host,
            port=self.settings.port,
            log_level="info" if not self.settings.debug else "debug"
        )