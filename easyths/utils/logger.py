import structlog
import logging
import sys
from pathlib import Path
from .config import project_config_instance

def setup_logging():
    """设置日志系统
    """
    level = project_config_instance.logging_level
    log_file = project_config_instance.logging_file

    # 确保日志目录存在
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # 基础处理器（不包含最终渲染器）
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    # 控制台处理器：使用带颜色的渲染
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
    )

    # 文件处理器：使用无颜色的纯文本渲染
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(getattr(logging, level.upper()))
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer() if level.upper() == 'DEBUG'
        else structlog.processors.KeyValueRenderer(sort_keys=False, key_order=['timestamp', 'level', 'event', 'logger'])
    )
    file_handler.setFormatter(file_formatter)

    # 配置标准库logging根日志记录器
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, level.upper()))

    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 添加文件处理器
    root_logger.addHandler(file_handler)

    # 配置structlog
    structlog.configure(
        processors=shared_processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )