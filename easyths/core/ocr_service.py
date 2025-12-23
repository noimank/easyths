"""
OCR图像识别模块

基于pytesseract的图像文字识别服务，使用单例模式确保全局唯一实例
"""

import os
import threading
from pathlib import Path
from typing import Optional, Union, Dict, Any

import pytesseract
from PIL import Image
import structlog
logger = structlog.get_logger(__name__)

from easyths.utils.screen_capture import mss_screen_capture_instance


class OCRService:
    """OCR图像识别服务类
    """
    def __init__(self):
        """初始化OCR服务"""
        self._logger = structlog.get_logger(__name__)
        self._logger.info("OCR服务初始化完成")

    def recognize_text(
        self,
        image_or_loc: Union[str, Path, Image.Image, dict],
        config: Optional[str] = None,
        post_process_type = None,
        **kwargs
    ) -> str:
        """识别图像中的文字

        Args:
            image_or_loc: 图像路径、PIL Image对象或numpy数组， 如果是字典，则表示屏幕截图区域如：{"top": top, "left": left, "width": width, "height": height}
            config: tesseract配置字符串
            post_process_type: 识别结果后处理类型
            **kwargs: 其他pytesseract参数

        Returns:
            str: 识别出的文字
        """
        try:
            # 配置参数
            custom_config = config or r'--oem 3 --psm 6'
            # lang: 语言设置，默认中文简体
            # lang: str = 'chi_sim+eng'
            lang: str = 'chi_sim'
            image = None

            # 如果是路径，转换为PIL Image
            if isinstance(image_or_loc, (str, Path)):
                image_path = str(image_or_loc)
                if not os.path.exists(image_path):
                    raise FileNotFoundError(f"图像文件不存在: {image_path}")
                image = Image.open(image_path)
            if isinstance(image_or_loc, dict):
                # 截取屏幕区域
                sct_img = mss_screen_capture_instance.grab(image_or_loc)
                # 转换为PIL Image
                image = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            # 执行OCR识别
            text = pytesseract.image_to_string(
                image,
                lang=lang,
                config=custom_config,
                **kwargs
            )

            #调用后处理
            result = self.post_process_text(text, post_process_type)

            self._logger.info(
                "文字识别完成",
                image_type=type(image).__name__,
                lang=lang,
                text_length=len(result)
            )
            return result

        except Exception as e:
            self._logger.error("文字识别失败", error=str(e))
            raise

    def _clear_special_chars(self, text: str, special_char_list) -> str:
        """根据特殊字符列表将文本中的特殊字符替换为空格

        Args:
            text: 输入文本
            special_char_list: 需要替换的特殊字符列表

        Returns:
            str: 替换后的文本
        """
        if not special_char_list:
            return text

        # 遍历特殊字符列表，将每个字符替换为空格
        for char in special_char_list:
            text = text.replace(char, ' ')
        return text


    def post_process_text(self, text: str, post_process_type: str) -> str:
        """对识别结果进行后处理

        Args:
            text: 识别结果
            post_process_type: 后处理类型

        Returns:
            str: 后处理后的结果
        """
        # 清理结果
        result = text.strip()
        if post_process_type is None:
            return result

        if post_process_type == "验证码":
            # 仅保留数字和字母，过滤掉其他字符
            filtered_result = ''.join(char for char in result if char.isalnum())
            # 截取后4个字符，目前验证码类型就 4个，确保返回4个长度，免得其他情况发生
            if len(filtered_result) > 4:
                filtered_result = filtered_result[-4:]
            result = filtered_result

        return result


    def get_available_languages(self) -> list:
        """获取可用的语言列表

        Returns:
            list: 可用语言代码列表
        """
        try:
            languages = pytesseract.get_languages(config='')
            self._logger.info("获取可用语言列表", languages=languages)
            return languages
        except Exception as e:
            self._logger.error("获取语言列表失败", error=str(e))
            return []

ocr_service = OCRService()

# 创建全局单例实例
def get_ocr_service() -> OCRService:
    """获取OCR服务实例

    Returns:
        OCRService: OCR服务单例实例
    """
    return ocr_service


if __name__ == '__main__':
    ocr_service = get_ocr_service()
    img_path = r"C:\Users\noima\Desktop\1.png"
    # text = ocr_service.recognize_text(ocr_service.preprocess_image(img_path, resize_factor=2),config="--oem 3 --psm 6  -c tessedit_char_whitelist=0123456789.%+-*/")
    text = ocr_service.recognize_text(img_path, post_process_type="委托列表")
    # text = ocr_service.recognize_text(img_path, post_process_type="持仓列表")
    # 读取图片并识别文本
    print(text)