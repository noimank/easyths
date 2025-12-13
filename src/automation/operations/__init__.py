"""
操作插件包初始化文件
自动导入并注册所有操作插件
"""

import structlog

logger = structlog.get_logger(__name__)

# 插件列表
__all__ = [
    "buy_operation",
    "sell_operation",
    "funds_query_operation"
]

try:
    # 导入所有插件
    from .buy_operation import BuyOperation
    from .sell_operation import SellOperation
    from .funds_query_operation import FundsQueryOperation

    logger.info("操作插件包加载成功")

except ImportError as e:
    logger.warning(f"部分操作插件加载失败: {str(e)}")