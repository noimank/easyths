"""Environment-based configuration management for QuantTrader.

This module replaces the YAML-based configuration system with environment variables,
providing better security for sensitive data and improved deployment flexibility.
"""

import os
import sys
from pathlib import Path
from typing import List, Literal, Optional, Union

from dotenv import load_dotenv
from pydantic import Field, field_validator, computed_field
from pydantic_settings import BaseSettings


def _load_env_file() -> None:
    """Load .env file if it exists (for development)."""
    # Try to load .env from the project root
    env_file = Path(__file__).parent.parent.parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)


class AppSettings(BaseSettings):
    """Application settings."""

    name: str = Field(default="同花顺交易自动化", description="Application name")
    version: str = Field(default="1.0.0", description="Application version")

    model_config = {"env_prefix": "APP_"}


class TradingSettings(BaseSettings):
    """Trading application settings."""

    app_path: str = Field(..., description="Path to the trading application executable")
    backend: Literal["win32"] = Field(default="win32", description="GUI automation backend")
    timeout: int = Field(default=30, gt=0, description="Operation timeout in seconds")
    retry_count: int = Field(default=3, ge=0, description="Default retry count")
    retry_delay: float = Field(default=1.0, ge=0, description="Retry delay in seconds")

    @field_validator('app_path')
    @classmethod
    def validate_app_path(cls, v: str) -> str:
        """Validate that the trading app path exists."""
        if not os.path.exists(v):
            raise ValueError(f"Trading app path does not exist: {v}")
        if not v.endswith('.exe'):
            raise ValueError(f"Trading app path must point to an .exe file: {v}")
        return v

    model_config = {"env_prefix": "TRADING_"}


class QueueSettings(BaseSettings):
    """Operation queue settings."""

    max_size: int = Field(default=1000, gt=0, description="Maximum queue size")
    priority_levels: int = Field(default=5, gt=0, description="Number of priority levels")
    batch_size: int = Field(default=10, gt=0, description="Batch processing size")

    model_config = {"env_prefix": "QUEUE_"}


class APISettings(BaseSettings):
    """API server settings."""

    host: str = Field(default="0.0.0.0", description="API server host")
    port: int = Field(default=8000, ge=1, le=65535, description="API server port")
    rate_limit: int = Field(default=10, gt=0, description="Rate limit per second")
    api_key: Optional[str] = Field(default=None, description="API authentication key")

    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins from environment or use default."""
        cors_origins_env = os.getenv("API_CORS_ORIGINS", "*")
        return [origin.strip() for origin in cors_origins_env.split(",")]

    model_config = {"env_prefix": "API_"}




class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level"
    )
    format: Literal["json", "text"] = Field(
        default="json",
        description="Log format"
    )
    file: str = Field(default="logs/trading.log", description="Main log file path")
    audit_file: str = Field(default="logs/audit.log", description="Audit log file path")
    max_size: str = Field(default="100MB", description="Maximum log file size")
    backup_count: int = Field(default=10, ge=0, description="Number of backup files")

    model_config = {"env_prefix": "LOGGING_"}


class MonitoringSettings(BaseSettings):
    """Monitoring and health check settings."""

    metrics: bool = Field(default=True, description="Enable metrics collection")
    health_check_interval: int = Field(
        default=60,
        gt=0,
        description="Health check interval in seconds"
    )
    state_sync_interval: int = Field(
        default=30,
        gt=0,
        description="State sync interval in seconds"
    )

    model_config = {"env_prefix": "MONITORING_"}


class Settings:
    """Main configuration manager that aggregates all settings."""

    def __init__(self):
        # Load .env file for development
        _load_env_file()

        # Initialize all settings sections
        self.app = AppSettings()
        self.trading = TradingSettings()
        self.queue = QueueSettings()
        self.api = APISettings()
        # Plugin configuration is hardcoded
        self.plugin_dirs = ["src/automation/operations"]
        self.plugin_auto_load = True
        self.plugin_whitelist = []
        self.logging = LoggingSettings()
        self.monitoring = MonitoringSettings()

    def validate_all(self) -> None:
        """Validate all configuration settings."""
        # Pydantic automatically validates on initialization
        # Add any additional cross-section validation here
        pass

    def to_dict(self) -> dict:
        """Convert all settings to a dictionary for backward compatibility."""
        return {
            'app': {
                'name': self.app.name,
                'version': self.app.version,
            },
            'trading': {
                'app_path': self.trading.app_path,
                'backend': self.trading.backend,
                'timeout': self.trading.timeout,
                'retry_count': self.trading.retry_count,
                'retry_delay': self.trading.retry_delay,
            },
            'queue': {
                'max_size': self.queue.max_size,
                'priority_levels': self.queue.priority_levels,
                'batch_size': self.queue.batch_size,
            },
            'api': {
                'host': self.api.host,
                'port': self.api.port,
                'rate_limit': self.api.rate_limit,
                'cors_origins': self.api.cors_origins,
                'api_key': self.api.api_key,
            },
            'plugins': {
                'plugin_dirs': self.plugin_dirs,
                'auto_load': self.plugin_auto_load,
                'whitelist': self.plugin_whitelist,
            },
            'logging': {
                'level': self.logging.level,
                'format': self.logging.format,
                'file': self.logging.file,
                'audit_file': self.logging.audit_file,
                'max_size': self.logging.max_size,
                'backup_count': self.logging.backup_count,
            },
            'monitoring': {
                'metrics': self.monitoring.metrics,
                'health_check_interval': self.monitoring.health_check_interval,
                'state_sync_interval': self.monitoring.state_sync_interval,
            },
        }


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()