import functools

import ddddocr
import structlog
from PIL import Image

from .screen_capture import get_mss_instance


@functools.lru_cache(maxsize=1)
def _get_ocr_instance()->ddddocr.DdddOcr:
    """获取 ddddocr 实例（全局单例）"""
    ocr = ddddocr.DdddOcr(show_ad=False,beta=True)
    # 小写英文 + 大写英文 + 数字
    ocr.set_ranges("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    return ocr


class CaptchaOCR:
    def __init__(self):
        self.logger = structlog.get_logger(__name__)

    def recognize(self, captcha_control) -> str:
        """识别验证码
        Args:
            captcha_control : 验证码控件

        Returns:
            str: 识别结果
        """
        try:
            # 判断控件是否有效
            if captcha_control is None:
                raise Exception("控件对象为空")
            # 1. 获取控件位置和大小
            rect = captcha_control.element_info.rectangle
            left = rect.left
            top = rect.top
            right = rect.right
            bottom = rect.bottom
            width = right - left
            height = bottom - top
            # 2. 截取控件区域的屏幕截图
            # 定义截图区域
            monitor = {"top": top, "left": left, "width": width, "height": height}
            # 截取屏幕区域
            sct_img = get_mss_instance().grab(monitor)
            # 转换为PIL Image
            image = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            # 获取 OCR 实例并识别
            ocr = _get_ocr_instance()
            result = ocr.classification(image)
            self.logger.debug(f"验证码识别结果: {result}")
            return result

        except Exception as e:
            self.logger.error(f"验证码识别失败: {e}")
            return ""


@functools.lru_cache(maxsize=1)
def get_captcha_ocr_server() -> CaptchaOCR:
    return CaptchaOCR()
