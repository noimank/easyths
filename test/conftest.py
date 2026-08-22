"""测试公共前置准备。

- 项目根目录存在 config.toml 时自动加载到全局配置实例，为后续测试提供统一环境
- 提供内置配置模板路径，配置相关用例直接读取模板，不手写完整 TOML
"""

from pathlib import Path

import pytest

from easyths.utils import project_config_instance

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
# 内置配置模板
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "easyths" / "assets" / "config_example.toml"


@pytest.fixture(scope="session", autouse=True)
def unified_config_env():
    """项目根目录存在 config.toml 时加载，为后续测试提供统一的配置环境

    不存在时保持内置默认值。
    """
    config_file = PROJECT_ROOT / "config.toml"
    if config_file.exists():
        project_config_instance.load_toml_file(config_file)


@pytest.fixture
def example_config_path() -> Path:
    """内置配置模板路径"""
    return EXAMPLE_CONFIG_PATH
