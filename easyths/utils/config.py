"""项目配置：TOML 配置文件是唯一配置来源，未配置的项使用内置默认值。"""

import tomllib
from pathlib import Path

# MCP 服务器传输类型可选值
VALID_MCP_SERVER_TYPES = ("http", "streamable-http", "sse")

# 日志文件默认路径（用户主目录下）
DEFAULT_LOG_FILE = str(Path("~/easyths/log.txt").expanduser())


class ProjectConfig:
    """项目配置

    类属性即默认值，可通过 load_toml_file 加载 TOML 配置文件覆盖。
    """

    # App配置
    onnx_model_dir: str | None = None
    # 默认保存
    save_error_captcha_image: bool = True

    # Trading配置
    trading_app_path: str = "C:/同花顺远航版/transaction/xiadan.exe"

    # Queue配置
    queue_max_size: int = 1000
    # 单操作执行硬超时（秒），界面卡死时以 TIMEOUT 收尾并断开同花顺连接
    queue_operation_timeout: float = 10.0

    # API配置
    api_host: str = "0.0.0.0"
    api_port: int = 7648
    api_rate_limit: int = 100
    api_cors_origins: str = "*"
    api_key: str | None = None
    api_ip_whitelist: str | None = (
        None  # None表示允许所有，逗号分隔如"127.0.0.1,192.168.1.*"
    )
    api_mcp_server_type: str = "streamable-http"

    # Logging配置
    logging_level: str = "INFO"
    logging_file: str = DEFAULT_LOG_FILE

    def load_toml_file(self, toml_file_path: str | Path) -> None:
        """从 TOML 配置文件加载配置

        文件中未出现的配置项保持当前值；字符串配置项的空字符串视为未配置。

        Args:
            toml_file_path: TOML 配置文件路径
        """
        with open(toml_file_path, "rb") as f:
            config = tomllib.load(f)

        # 处理 [app] 部分
        app = config.get("app", {})
        self.onnx_model_dir = app.get("onnx_model_dir") or None
        self.save_error_captcha_image = app.get("save_error_captcha_image", True)

        # 处理 [trading] 部分
        trading = config.get("trading", {})
        self.trading_app_path = trading.get("app_path") or self.trading_app_path

        # 处理 [queue] 部分
        queue = config.get("queue", {})
        self.queue_max_size = queue.get("max_size", self.queue_max_size)
        self.queue_operation_timeout = queue.get(
            "operation_timeout", self.queue_operation_timeout
        )

        # 处理 [api] 部分
        api = config.get("api", {})
        self.api_host = api.get("host", self.api_host)
        self.api_port = api.get("port", self.api_port)
        self.api_rate_limit = api.get("rate_limit", self.api_rate_limit)
        self.api_cors_origins = api.get("cors_origins", self.api_cors_origins)
        self.api_key = api.get("key") or None
        self.api_ip_whitelist = api.get("ip_whitelist") or None
        mcp_type = api.get("mcp_server_type", self.api_mcp_server_type)
        if mcp_type not in VALID_MCP_SERVER_TYPES:
            raise ValueError(
                f"无效的 mcp_server_type: {mcp_type}，可选值: {VALID_MCP_SERVER_TYPES}"
            )
        self.api_mcp_server_type = mcp_type

        # 处理 [logging] 部分
        logging_config = config.get("logging", {})
        self.logging_level = logging_config.get("level", self.logging_level)
        self.logging_file = logging_config.get("file") or DEFAULT_LOG_FILE

    @property
    def api_ip_whitelist_list(self) -> list[str] | None:
        """获取IP白名单列表

        Returns:
            list[str] | None: IP白名单列表，None或空列表表示允许所有
        """
        if not self.api_ip_whitelist:
            return None
        return [ip.strip() for ip in self.api_ip_whitelist.split(",") if ip.strip()]

    @property
    def api_cors_origins_list(self) -> list[str]:
        """获取CORS允许的源列表

        Returns:
            list[str]: CORS允许的源列表，支持逗号分隔的字符串
        """
        if not self.api_cors_origins:
            return ["*"]
        # 如果是通配符，直接返回
        if self.api_cors_origins == "*":
            return ["*"]
        # 逗号分隔多个源
        return [
            origin.strip()
            for origin in self.api_cors_origins.split(",")
            if origin.strip()
        ]


project_config_instance = ProjectConfig()
