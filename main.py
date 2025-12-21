#!/usr/bin/env python3
"""
同花顺交易自动化系统主入口
"""

import asyncio
import sys
from pathlib import Path
import structlog
from dotenv import load_dotenv
load_dotenv()
# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.automation.operation_manager import OperationManager
from src.automation.tonghuashun_automator import TonghuashunAutomator
from src.core.operation_queue import OperationQueue
from src.api.app import TradingAPIApp
from src.utils.env_config import get_settings



async def initialize_components(config: dict):
    """初始化组件

    Args:
        config: 配置数据

    Returns:
        tuple: (automator, operation_queue, operation_manager)
    """
    # 创建自动化器
    automator = TonghuashunAutomator(config.get('trading', {}))

    # 连接到同花顺
    await automator.connect()

    # 创建操作队列
    operation_queue = OperationQueue(
        config.get('queue', {}),
        automator
    )

    # 创建操作管理器
    operation_manager = OperationManager(config.get('plugins', {}))

    return automator, operation_queue, operation_manager


def main():
    """主函数"""
    # 加载配置
    settings = get_settings()
    config = settings.to_dict()

    # 初始化日志
    logger = structlog.get_logger(__name__)
    logger.info("系统启动", version="1.0.0")

    # 初始化组件
    automator, operation_queue, operation_manager = asyncio.run(
        initialize_components(config)
    )

    # 创建并运行API服务
    api_app = TradingAPIApp(config, automator, operation_queue, operation_manager)
    app = api_app.create_app()

    try:
        api_app.run()
    except KeyboardInterrupt:
        print("\n正在关闭系统...")
    except Exception as e:
        logger.exception("系统运行异常", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()