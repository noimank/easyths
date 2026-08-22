"""TOML 配置加载逻辑的单元测试（无需 GUI/服务端）。

模板 easyths/assets/config_example.toml 即默认值文档，受双契约约束：
- 结构契约：模板的 section/key 与 TEMPLATE_FIELDS 映射完全一致
- 取值契约：加载模板后所有配置与内置默认值一致
加载器行为（文件值覆盖、缺省保默认、非法值拒绝）由最小合成文件验证。
"""

import tomllib
from pathlib import Path

import pytest

from easyths.utils.config import DEFAULT_LOG_FILE, ProjectConfig

# 模板 section/key → ProjectConfig 属性的完整映射（模板即配置契约，两边需同步维护）
TEMPLATE_FIELDS: dict[str, dict[str, str]] = {
    "app": {
        "onnx_model_dir": "onnx_model_dir",
        "save_error_captcha_image": "save_error_captcha_image",
    },
    "trading": {"app_path": "trading_app_path"},
    "queue": {
        "max_size": "queue_max_size",
        "operation_timeout": "queue_operation_timeout",
    },
    "api": {
        "host": "api_host",
        "port": "api_port",
        "rate_limit": "api_rate_limit",
        "cors_origins": "api_cors_origins",
        "key": "api_key",
        "ip_whitelist": "api_ip_whitelist",
        "mcp_server_type": "api_mcp_server_type",
    },
    "logging": {"level": "logging_level", "file": "logging_file"},
}


def read_template(example_config_path: Path) -> dict:
    """解析内置模板为原始 dict"""
    with open(example_config_path, "rb") as f:
        return tomllib.load(f)


def test_defaults():
    """未加载任何文件时的内置默认值"""
    config = ProjectConfig()
    assert config.onnx_model_dir is None
    assert config.save_error_captcha_image is True
    assert config.queue_max_size == 1000
    assert config.queue_operation_timeout == 10.0
    assert config.api_rate_limit == 100
    assert config.api_key is None
    assert config.api_ip_whitelist is None
    assert config.api_mcp_server_type == "streamable-http"
    assert config.logging_file == DEFAULT_LOG_FILE


def test_template_structure_matches_contract(example_config_path):
    """模板的 section 与 key 必须与字段映射完全一致，模板增删改键而未同步契约即失败"""
    raw = read_template(example_config_path)
    assert {s: sorted(keys) for s, keys in raw.items()} == {
        s: sorted(keys) for s, keys in TEMPLATE_FIELDS.items()
    }


def test_template_matches_defaults(example_config_path):
    """模板即默认值：加载模板后，每个配置属性都与内置默认值一致"""
    config = ProjectConfig()
    config.load_toml_file(example_config_path)
    defaults = ProjectConfig()

    for fields in TEMPLATE_FIELDS.values():
        for attr in fields.values():
            assert getattr(config, attr) == getattr(defaults, attr), (
                f"{attr} 的模板值与默认值不一致"
            )


def test_file_values_override_defaults(tmp_path):
    """文件出现的键按文件值加载（含空字符串归一化），未出现的键保持默认值"""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[app]\nonnx_model_dir = ""\nsave_error_captcha_image = false\n'
        '[trading]\napp_path = "C:/ths/xiadan.exe"\n'
        "[queue]\nmax_size = 5\noperation_timeout = 3.0\n"
        '[api]\nport = 9000\nrate_limit = 99\ncors_origins = "http://a.com"\n'
        'key = "secret"\nip_whitelist = "127.0.0.1,192.168.1.*"\n'
        'mcp_server_type = "sse"\n'
        '[logging]\nlevel = "DEBUG"\nfile = "D:/logs/ths.log"\n',
        encoding="utf-8",
    )

    config = ProjectConfig()
    config.load_toml_file(config_file)

    assert config.onnx_model_dir is None  # 空字符串视为未配置
    assert config.save_error_captcha_image is False
    assert config.trading_app_path == "C:/ths/xiadan.exe"
    assert config.queue_max_size == 5
    assert config.queue_operation_timeout == 3.0
    assert config.api_port == 9000
    assert config.api_rate_limit == 99
    assert config.api_cors_origins_list == ["http://a.com"]
    assert config.api_key == "secret"
    assert config.api_ip_whitelist_list == ["127.0.0.1", "192.168.1.*"]
    assert config.api_mcp_server_type == "sse"
    assert config.logging_level == "DEBUG"
    assert config.logging_file == "D:/logs/ths.log"
    # 未在文件中出现的键保持默认值
    assert config.api_host == "0.0.0.0"


def test_list_properties():
    """IP白名单与CORS源列表属性的解析规则"""
    config = ProjectConfig()
    config.api_ip_whitelist = "127.0.0.1, 192.168.1.*"
    config.api_cors_origins = "http://a.com,http://b.com"
    assert config.api_ip_whitelist_list == ["127.0.0.1", "192.168.1.*"]
    assert config.api_cors_origins_list == ["http://a.com", "http://b.com"]

    config.api_ip_whitelist = None
    assert config.api_ip_whitelist_list is None
    config.api_cors_origins = "*"
    assert config.api_cors_origins_list == ["*"]


def test_invalid_mcp_server_type_rejected(tmp_path):
    """非法 mcp_server_type 拒绝加载"""
    config_file = tmp_path / "config.toml"
    config_file.write_text('[api]\nmcp_server_type = "websocket"\n', encoding="utf-8")

    config = ProjectConfig()
    with pytest.raises(ValueError, match="mcp_server_type"):
        config.load_toml_file(config_file)
