from pathlib import Path

from .captcha_ocr import get_captcha_ocr_server
from .config import project_config_instance
from .screen_capture import grab_screen
from .table_text_handler import df_to_records, text2df


def get_asset_path() -> Path:
    """获取 assets 目录路径（随包分发的静态资源根，含示例配置与 Web 控制台）"""
    return Path(__file__).resolve().parent.parent / "assets"
