"""
Utility functions for captcha recognition.

Author: noimank (康康)
Email: noimank@163.com
"""

import os
from pathlib import Path
from typing import Optional

import yaml


# Default configuration
DEFAULT_CONFIG = {
    "charset": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "captcha_length": {"min": 4, "max": 6},
    "case_sensitive": False,
    "image": {
        "width": 200,
        "height": 60
    },
    "lower_scale": {
        "min": 0.7,
        "max": 0.85
    }
}


def load_config(config_path: Optional[str] = None) -> dict:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, returns default config.

    Returns:
        Configuration dictionary.
    """
    if config_path is None:
        return DEFAULT_CONFIG.copy()

    config_file = Path(config_path)
    if not config_file.exists():
        print(f"Config file not found: {config_path}, using default config")
        return DEFAULT_CONFIG.copy()

    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}

    # Merge with defaults
    result = DEFAULT_CONFIG.copy()
    result.update(config)

    return result


def get_charset(config: dict) -> str:
    """Get character set from config."""
    return config.get("charset", DEFAULT_CONFIG["charset"])


def get_image_size(config: dict) -> tuple:
    """Get image size (width, height) from config."""
    image_cfg = config.get("image", DEFAULT_CONFIG["image"])
    return image_cfg.get("width", 200), image_cfg.get("height", 60)
