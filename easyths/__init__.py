"""EasyTHS - 同花顺交易自动化系统"""

from importlib.metadata import PackageNotFoundError, version

try:
    # 版本唯一来源是 pyproject.toml（经安装元数据读取），
    # 源码直跑（python main.py）未安装包时退回占位值
    __version__ = version("easyths")
except PackageNotFoundError:
    __version__ = "0.0.0"

from .trade_client import APIResponse, TradeClient, TradeClientError

__all__ = ["APIResponse", "TradeClient", "TradeClientError", "__version__"]
