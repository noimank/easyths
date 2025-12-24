import toml
import os

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
    api_port = int(os.getenv("API_PORT", 8000))
    api_rate_limit = int(os.getenv("API_RATE_LIMIT", 10))
    api_cors_origins = os.getenv("API_CORS_ORIGINS", "*")
    api_key = os.getenv("API_KEY", None)
    api_ip_whitelist = os.getenv("API_IP_WHITELIST", None)  # None表示允许所有，逗号分隔如"127.0.0.1,192.168.1.*"

    # Logging配置
    logging_level = os.getenv("LOGGING_LEVEL", "INFO")
    logging_file = os.getenv("LOGGING_FILE", "logs/trading.log")


    def __init__(self):
        pass

    def update_form_toml_file(self, toml_file_path):
        config = toml.load(toml_file_path)
        for key, value in config.items():
            setattr(self, key, value)

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
