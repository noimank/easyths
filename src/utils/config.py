import toml
import os

class ProjectConfig:

    # App配置
    app_name = os.getenv("APP_NAME", "同花顺交易自动化程序")
    app_version = os.getenv("APP_VERSION", "1.0.0")

    # Trading配置
    trading_app_path = os.getenv("TRADING_APP_PATH", "C:/同花顺远航版/transaction/xiadan.exe")
    trading_backend = os.getenv("TRADING_BACKEND", "win32")
    trading_timeout = int(os.getenv("TRADING_TIMEOUT", 30))
    trading_retry_count = int(os.getenv("TRADING_RETRY_COUNT", 3))
    trading_retry_delay = float(os.getenv("TRADING_RETRY_DELAY", 1.0))
    # Queue
    queue_max_size = int(os.getenv("QUEUE_MAX_SIZE", 1000))
    queue_priority_levels = int(os.getenv("QUEUE_PRIORITY_LEVELS", 5))
    queue_batch_size = int(os.getenv("QUEUE_BATCH_SIZE", 10))

    # API配置
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", 8000))
    api_rate_limit = int(os.getenv("API_RATE_LIMIT", 10))
    api_cors_origins = os.getenv("API_CORS_ORIGINS", "*")
    api_key = os.getenv("API_KEY", "your_secure_api_key_here")

    # Logging配置
    logging_level = os.getenv("LOGGING_LEVEL", "INFO")
    logging_format = os.getenv("LOGGING_FORMAT", "json")
    logging_file = os.getenv("LOGGING_FILE", "logs/trading.log")
    logging_audit_file = os.getenv("LOGGING_AUDIT_FILE", "logs/audit.log")


    def __init__(self):
        pass

    def update_form_toml_file(self, toml_file_path):
        config = toml.load(toml_file_path)
        for key, value in config.items():
            setattr(self, key, value)


project_config_instance = ProjectConfig()
