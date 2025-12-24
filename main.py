#!/usr/bin/env python3
"""同花顺交易自动化系统主入口

架构说明：
    - 操作队列：后台线程串行执行所有业务操作（支持优先级）
    - 自动化器：基于 pywinauto UIA backend 的 GUI 自动化
    - 对外接口：异步高并发 API

Author: noimank
Email: noimank@163.com
"""

import sys
import platform
from pathlib import Path

import psutil
import structlog
from dotenv import load_dotenv

load_dotenv()

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))
from easyths.utils.logger import setup_logging
setup_logging()
from easyths.core.tonghuashun_automator import TonghuashunAutomator
from easyths.core.operation_queue import OperationQueue
from easyths.api.app import TradingAPIApp
from easyths.utils import project_config_instance


def check_running_env():
    """检查运行环境是否可用

    检查：
    1. 是否为 Windows 系统
    2. 下单 exe 是否存在
    3. 是否存在对应的进程

    Returns:
        bool: 如果运行环境可用返回 True，否则返回 False
    """
    logger = structlog.get_logger(__name__)

    # 检查是否为 Windows 系统
    if platform.system() != "Windows":
        logger.error(
            "系统不支持，仅支持 Windows 系统",
            current_system=platform.system()
        )
        return False

    app_path = project_config_instance.trading_app_path

    # 检查 exe 是否存在
    if not app_path or not Path(app_path).exists():
        logger.error(
            "同花顺交易程序不存在，无法启动系统",
            app_path=app_path
        )
        return False

    # 获取进程名
    process_name = Path(app_path).name

    # 检查进程是否运行
    is_running = False
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] == process_name:
                is_running = True
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not is_running:
        logger.error(
            "同花顺交易程序未运行，无法启动系统",
            process_name=process_name
        )
        return False

    logger.info(
        "运行环境检查通过",
        app_path=app_path,
        process_name=process_name
    )
    return True


def initialize_components():
    """初始化组件 - 同步初始化

    Returns:
        tuple: (automator, operation_queue)
    """
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接到同花顺
    automator.connect()

    # 创建操作队列
    operation_queue = OperationQueue(automator)
    operation_queue.start()

    return automator, operation_queue


def main():
    """主函数"""
    # 初始化日志
    logger = structlog.get_logger(__name__)
    logger.info("系统启动", version="1.0.0")

    # 检查运行环境
    if not check_running_env():
        logger.error("运行环境检查失败，系统退出")
        sys.exit(1)

    # 初始化组件
    automator, operation_queue = initialize_components()

    # 创建并运行API服务
    api_app = TradingAPIApp(operation_queue)
    app = api_app.create_app()

    try:
        api_app.run()
    except KeyboardInterrupt:
        print("\n正在关闭系统...")
    except Exception as e:
        logger.exception("系统运行异常", error=str(e))
    finally:
        # 清理资源
        logger.info("正在清理资源...")
        operation_queue.stop()
        automator.disconnect()
        logger.info("系统已关闭")


if __name__ == "__main__":
    main()
