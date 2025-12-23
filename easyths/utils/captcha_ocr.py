import structlog
from .screen_capture import mss_screen_capture_instance
from PIL import Image
import ddddocr
class CaptchaOCR:
    def __init__(self):
        self.ocr = ddddocr.DdddOcr(show_ad=False)
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
            sct_img = mss_screen_capture_instance.grab(monitor)
            # 转换为PIL Image
            image = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            result = self.ocr.classification(image)
            return result

        except Exception as e:
            self.logger.error(f"验证码识别失败: {e}")
            return ""

captcha_ocr_server = CaptchaOCR()
def get_captcha_ocr_server():
    return captcha_ocr_server