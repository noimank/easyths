import toml
import os
from pathlib import Path

class ProjectConfig:

    # App配置
    app_name = os.getenv("APP_NAME", "同花顺交易自动化程序")
    app_version = os.getenv("APP_VERSION", "1.0.0")

    # Trading配置
    trading_app_path = os.getenv("TRADING_APP_PATH", "C:/同花顺远航版/transaction/xiadan.exe")
    # Queue
    queue_max_size = int(os.getenv("QUEUE_MAX_SIZE", 1000))
    queue_priority_levels = int(os.getenv("QUEUE_PRIORITY_LEVELS", 5))
    queue_batch_size = int(os.getenv("QUEUE_BATCH_SIZE", 10))

    # API配置
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", 7648))
    api_rate_limit = int(os.getenv("API_RATE_LIMIT", 10))
    api_cors_origins = os.getenv("API_CORS_ORIGINS", "*")
    api_key = os.getenv("API_KEY", None)
    api_ip_whitelist = os.getenv("API_IP_WHITELIST", None)  # None表示允许所有，逗号分隔如"127.0.0.1,192.168.1.*"

    # Logging配置
    logging_level = os.getenv("LOGGING_LEVEL", "INFO")
    # 默认为用户主目录下
    logging_file = str(Path("~/easyths/log.txt").expanduser()) if  os.getenv("LOGGING_FILE", "") == "" else  os.getenv("LOGGING_FILE")


    def __init__(self):
        pass

    def update_from_toml_file(self, toml_file_path: str, exe_path: str | None = None) -> None:
        """从 TOML 配置文件更新配置

        Args:
            toml_file_path: TOML 配置文件路径
            exe_path: 可选的交易程序路径，优先级高于配置文件中的设置
        """
        config = toml.load(toml_file_path)

        # 处理 [app] 部分
        if "app" in config:
            app_config = config["app"]
            if "name" in app_config:
                self.app_name = app_config["name"]
            if "version" in app_config:
                self.app_version = app_config["version"]

        # 处理 [trading] 部分
        if "trading" in config:
            trading_config = config["trading"]
            if "app_path" in trading_config:
                self.trading_app_path = trading_config["app_path"]

        # 处理 [queue] 部分
        if "queue" in config:
            queue_config = config["queue"]
            if "max_size" in queue_config:
                self.queue_max_size = queue_config["max_size"]
            if "priority_levels" in queue_config:
                self.queue_priority_levels = queue_config["priority_levels"]
            if "batch_size" in queue_config:
                self.queue_batch_size = queue_config["batch_size"]

        # 处理 [api] 部分
        if "api" in config:
            api_config = config["api"]
            if "host" in api_config:
                self.api_host = api_config["host"]
            if "port" in api_config:
                self.api_port = api_config["port"]
            if "rate_limit" in api_config:
                self.api_rate_limit = api_config["rate_limit"]
            if "cors_origins" in api_config:
                self.api_cors_origins = api_config["cors_origins"]
            if "key" in api_config:
                # 空字符串转换为 None
                self.api_key = api_config["key"] or None
            if "ip_whitelist" in api_config:
                # 空字符串转换为 None
                self.api_ip_whitelist = api_config["ip_whitelist"] or None

        # 处理 [logging] 部分
        if "logging" in config:
            logging_config = config["logging"]
            if "level" in logging_config:
                self.logging_level = logging_config["level"]
            if "file" in logging_config:
                self.logging_file = logging_config["file"]

        # exe_path 参数优先级最高
        if exe_path:
            self.trading_app_path = exe_path

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
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


project_config_instance = ProjectConfig()
