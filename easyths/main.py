#!/usr/bin/env python3
"""同花顺交易自动化系统主入口

架构说明：
    - 操作队列：后台线程串行执行所有业务操作（支持优先级）
    - 自动化器：基于 pywinauto UIA backend 的 GUI 自动化
    - 对外接口：异步高并发 API

Author: noimank
Email: noimank@163.com
"""

import argparse
import shutil
import sys
import platform
from pathlib import Path

import psutil
import structlog

from easyths.utils.logger import setup_logging
from easyths.utils import project_config_instance
from easyths.core.tonghuashun_automator import TonghuashunAutomator
from easyths.core.operation_queue import OperationQueue
from easyths.api.app import TradingAPIApp

# 项目元信息
PROJECT_NAME = "EasyTHS"
PROJECT_AUTHOR = "noimank"
PROJECT_EMAIL = "noimank@163.com"
PROJECT_VERSION = "1.4.0"
PROJECT_REPO = "https://github.com/noimank/easyths"
PROJECT_DOCS = "https://noimank.github.io/easyths/"
PROJECT_ISSUES = "https://github.com/noimank/easyths/issues"


def get_asset_path() -> Path:
    """获取 assets 目录路径

    对于已安装的包，返回包内的 assets 目录
    对于开发环境，返回包内的 assets 目录

    Returns:
        Path: assets 目录路径
    """
    # 获取当前模块所在的目录（easyths 包目录）
    current_dir = Path(__file__).parent
    assets_path = current_dir / "assets"
    return assets_path


def print_project_info():
    """打印项目信息"""
    info_text = f"""
{'='*50}
  {PROJECT_NAME}
  同花顺交易自动化系统
{'='*50}
  版本:     {PROJECT_VERSION}
  作者:     {PROJECT_AUTHOR} <{PROJECT_EMAIL}>
  文档:     {PROJECT_DOCS}
  仓库:     {PROJECT_REPO}
  问题反馈: {PROJECT_ISSUES}
{'='*50}
"""
    print(info_text)


def print_help():
    """打印帮助信息"""
    help_text = """
同花顺交易自动化系统 (EasyTHS)

用法:
    uvx easyths[server] [选项]
    python main.py [选项]

选项:
    --exe_path <path>      指定同花顺交易程序路径（优先级高于配置文件）
    --config <file>        指定 TOML 配置文件路径
    --get_config           将示例配置文件复制到当前目录
    --version, -v          显示版本信息
    --help                 显示此帮助信息

示例:
    # 使用默认配置启动
    uvx easyths[server]

    # 使用自定义配置文件启动
    uvx easyths[server] --config my_config.toml

    # 指定交易程序路径启动（优先级最高）
    uvx easyths[server] --exe_path "C:/同花顺/xiadan.exe"

    # 查看版本
    uvx easyths[server] --version

    # 生成示例配置文件
    uvx easyths[server] --get_config

    # 组合使用
    uvx easyths[server] --config my_config.toml --exe_path "C:/同花顺/xiadan.exe"

配置文件:
    配置文件采用 TOML 格式，包含以下部分：
    - [app]: 应用程序配置
    - [trading]: 交易程序配置
    - [queue]: 队列配置
    - [api]: API 服务配置
    - [logging]: 日志配置
"""
    print(help_text)


def get_config():
    """将示例配置文件复制到当前目录"""
    assets_path = get_asset_path()
    example_config = assets_path / "config_example.toml"
    target_config = Path.cwd() / "config.toml"

    if not example_config.exists():
        print(f"错误: 示例配置文件不存在: {example_config}")
        sys.exit(1)

    if target_config.exists():
        response = input(f"配置文件 {target_config} 已存在，是否覆盖？(y/N): ")
        if response.lower() != 'y':
            print("操作已取消")
            return

    shutil.copy(example_config, target_config)
    print(f"配置文件已复制到: {target_config}")
    print("请根据实际情况修改配置文件中的参数")


def parse_args():
    """解析命令行参数

    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description="同花顺交易自动化系统",
        add_help=False  # 禁用默认的 --help，使用自定义的帮助
    )

    parser.add_argument(
        "--exe_path",
        type=str,
        default=None,
        help="指定同花顺交易程序路径（优先级高于配置文件）"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="指定 TOML 配置文件路径"
    )
    parser.add_argument(
        "--get_config",
        action="store_true",
        help="将示例配置文件复制到当前目录"
    )
    parser.add_argument(
        "--help",
        action="store_true",
        help="显示帮助信息"
    )
    parser.add_argument(
        "--version",
        "-v",
        action="store_true",
        help="显示版本信息"
    )

    return parser.parse_args()


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
    # 解析命令行参数
    args = parse_args()

    # 处理 --help 参数
    if args.help:
        print_help()
        return

    # 处理 --version 参数
    if args.version:
        print(f"{PROJECT_NAME} v{PROJECT_VERSION}")
        return

    # 处理 --get_config 参数
    if args.get_config:
        get_config()
        return

    # 加载配置文件
    config_loaded = False
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"错误: 配置文件不存在: {config_path}")
            sys.exit(1)
        project_config_instance.update_from_toml_file(
            str(config_path),
            exe_path=args.exe_path
        )
        config_loaded = True
    elif args.exe_path:
        # 只指定了 exe_path，不使用配置文件
        project_config_instance.trading_app_path = args.exe_path

    # 初始化日志（在配置加载后）
    setup_logging()
    logger = structlog.get_logger(__name__)

    if config_loaded:
        logger.info("已加载配置文件", config_file=args.config)

    logger.info("系统启动", version=project_config_instance.app_version)

    # 打印项目信息
    print_project_info()

    # 检查运行环境
    if not check_running_env():
        logger.error("运行环境检查失败，系统退出")
        sys.exit(1)

    # 初始化组件
    automator, operation_queue = initialize_components()

    # 创建并运行API服务
    api_app = TradingAPIApp(operation_queue, automator)
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
