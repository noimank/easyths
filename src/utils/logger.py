import structlog
import logging
import sys
import os
from pathlib import Path
from typing import Any, Dict
import json
from datetime import datetime

# 确保日志目录存在
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

def setup_logging(config: Dict[str, Any]):
    """设置日志系统

    Args:
        config: 日志配置
    """
    level = config.get('level', 'INFO')
    log_format = config.get('format', 'text')
    log_file = config.get('file', 'logs/trading.log')
    audit_file = config.get('audit_file', 'logs/audit.log')

    # 确保日志目录存在
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    Path(audit_file).parent.mkdir(parents=True, exist_ok=True)

    # 配置structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if log_format == 'json':
        processors.append(structlog.processors.JSONRenderer(ensure_ascii=False))
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 配置标准库logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # 添加文件处理器
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, level.upper()))

    # 设置审计日志
    audit_logger = logging.getLogger('audit')
    audit_handler = logging.FileHandler(audit_file)
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    audit_logger.addHandler(audit_handler)
    audit_logger.propagate = False

    return audit_logger


class AuditLogger:
    """审计日志记录器"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._logger = structlog.get_logger('audit')

    def log_operation(self, operation_name: str, params: Dict[str, Any],
                     user_id: str = None, result: Any = None, error: str = None):
        """记录操作日志

        Args:
            operation_name: 操作名称
            params: 操作参数
            user_id: 用户ID
            result: 操作结果
            error: 错误信息
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation_name,
            'user_id': user_id,
            'params': self._sanitize_params(params),
            'result': 'success' if not error else 'failed',
            'error': error
        }

        # 记录到审计日志文件
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))

        # 记录到结构化日志
        self._logger.info(
            "操作审计",
            operation=operation_name,
            user_id=user_id,
            params=log_entry['params'],
            result=log_entry['result'],
            error=error
        )

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """清理参数中的敏感信息

        Args:
            params: 原始参数

        Returns:
            Dict[str, Any]: 清理后的参数
        """
        sensitive_keys = ['password', 'token', 'secret', 'key']
        sanitized = {}

        for key, value in params.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = '***'
            else:
                sanitized[key] = value

        return sanitized

    def log_trade(self, stock_code: str, operation: str, price: float,
                  quantity: int, user_id: str = None, order_id: str = None):
        """记录交易日志

        Args:
            stock_code: 股票代码
            operation: 操作类型（buy/sell）
            price: 价格
            quantity: 数量
            user_id: 用户ID
            order_id: 委托编号
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'trade',
            'stock_code': stock_code,
            'operation': operation,
            'price': price,
            'quantity': quantity,
            'amount': price * quantity,
            'user_id': user_id,
            'order_id': order_id
        }

        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
        self._logger.info(
            "交易记录",
            stock_code=stock_code,
            operation=operation,
            price=price,
            quantity=quantity,
            amount=log_entry['amount'],
            user_id=user_id,
            order_id=order_id
        )

    def log_error(self, error_type: str, error_msg: str, context: Dict[str, Any] = None):
        """记录错误日志

        Args:
            error_type: 错误类型
            error_msg: 错误消息
            context: 上下文信息
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'error',
            'error_type': error_type,
            'error_msg': error_msg,
            'context': context or {}
        }

        self.logger.error(json.dumps(log_entry, ensure_ascii=False))
        self._logger.error(
            "系统错误",
            error_type=error_type,
            error_msg=error_msg,
            context=log_entry['context']
        )


# 全局审计日志实例
audit_logger: AuditLogger = None


def init_audit_logger(config: Dict[str, Any]):
    """初始化审计日志

    Args:
        config: 日志配置
    """
    logger = setup_logging(config)
    global audit_logger
    audit_logger = AuditLogger(logger)
    return audit_logger