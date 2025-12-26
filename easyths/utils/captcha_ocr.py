import threading
import structlog
from .screen_capture import get_mss_instance
from PIL import Image
import ddddocr

# 线程局部存储 - 每个线程缓存独立的 ddddocr 实例
_thread_local = threading.local()

class CaptchaOCR:
    def __init__(self):
        self.logger = structlog.get_logger(__name__)

    def _get_ocr(self):
        """获取当前线程的 ddddocr 实例（每个线程只创建一次，后续复用）"""
        if not hasattr(_thread_local, 'ocr'):
            _thread_local.ocr = ddddocr.DdddOcr(show_ad=False)
            self.logger.debug(f"线程 {threading.current_thread().name} 创建新的 ddddocr 实例")
        return _thread_local.ocr

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
            # 获取当前线程的 OCR 实例并识别
            ocr = self._get_ocr()
            result = ocr.classification(image)
            return result

        except Exception as e:
            self.logger.error(f"验证码识别失败: {e}")
            return ""

captcha_ocr_server = CaptchaOCR()
def get_captcha_ocr_server():
    return captcha_ocr_server