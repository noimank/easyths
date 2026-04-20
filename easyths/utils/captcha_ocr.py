import functools
from pathlib import Path
from typing import Tuple

import numpy as np
import onnx
import onnxruntime as ort
import structlog
from PIL import Image
from easyths.utils import project_config_instance
from .screen_capture import get_mss_instance

logger = structlog.get_logger(f"{__file__}")

class ONNXCaptchaRecognizer:
    """ONNX-based captcha recognizer with self-contained parameters."""

    def __init__(self, model_path: str, provider: str = "CPUExecutionProvider"):
        # Load ONNX model and extract metadata
        onnx_model = onnx.load(model_path)
        metadata = {p.key: p.value for p in onnx_model.metadata_props}

        # Read parameters from model metadata
        self.character = metadata.get("character")
        self.img_h = int(metadata.get("img_h"))
        self.img_w = int(metadata.get("img_w"))
        self.nc = int(metadata.get("nc", 1))  # Default to grayscale
        self.blank = len(self.character)

        # Create inference session
        providers = [self._get_provider(provider)]
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name

        logger.info(f"------成功加载验证码识别模型: {model_path}---------")
        logger.info(f"图片大小: {self.img_h}x{self.img_w} (channels: {self.nc})")
        logger.info(f"验证码字符集: {self.character[:20]}... ({len(self.character)} chars)")
        logger.info(f"使用推理设备: {provider}")


    def _get_provider(self, provider_str: str) -> str:
        if 'cuda' in provider_str.lower() or 'gpu' in provider_str.lower():
            return 'CUDAExecutionProvider'
        return 'CPUExecutionProvider'

    def recognize(self, image: np.ndarray | Image.Image) -> str:
        """Run inference on image."""
        if isinstance(image, Image.Image):
            image = np.array(image)
        input_tensor = self._preprocess(image)

        output = self.session.run(None, {self.input_name: input_tensor})[0]

        pred_indices = output.argmax(axis=1)[0].tolist()
        text = self._ctc_decode(pred_indices)

        return text

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        # 转换为 PIL Image
        if self.nc == 1:
            # Grayscale mode
            if len(image.shape) == 3:
                # RGB to grayscale
                img = Image.fromarray(image).convert('L')
            else:
                img = Image.fromarray(image)
            # Resize
            img = img.resize((self.img_w, self.img_h), Image.Resampling.LANCZOS)
            # Convert to numpy array and normalize
            img = np.array(img, dtype=np.float32) / 255.0
            # Add channel dimension (H, W) -> (1, H, W)
            img = np.expand_dims(img, axis=0)
        else:
            # RGB mode
            if len(image.shape) == 3:
                img = Image.fromarray(image)
            else:
                img = Image.fromarray(image).convert('RGB')
            # Resize
            img = img.resize((self.img_w, self.img_h), Image.Resampling.LANCZOS)
            # Convert to numpy array and normalize
            img = np.array(img, dtype=np.float32) / 255.0
            # HWC -> CHW
            img = np.transpose(img, (2, 0, 1))

        # Add batch dimension
        img = np.expand_dims(img, axis=0)
        return img

    def _ctc_decode(self, pred_indices: list) -> str:
        result = []
        prev = -1
        for idx in pred_indices:
            if idx != prev and idx != self.blank:
                if idx < len(self.character):
                    result.append(self.character[idx])
            prev = idx
        return ''.join(result)


@functools.lru_cache(maxsize=1)
def _get_ocr_instance() -> ONNXCaptchaRecognizer:
    """获取 ONNXCaptchaRecognizer 实例（全局单例）"""
    onnx_model_path = Path(__file__).parent.parent / "assets/onnx_model" / "captcha_ocr.onnx"
    if project_config_instance.onnx_model_dir is not None:
        if Path(project_config_instance.onnx_model_dir).exists():
            onnx_model_path = Path(project_config_instance.onnx_model_dir) / "captcha_ocr.onnx"
            onnx_model_data_path = Path(project_config_instance.onnx_model_dir) / "captcha_ocr.onnx.data"
            if (not onnx_model_path.exists()) or (not onnx_model_data_path.exists()):
                logger.warn(f"指定的ONNX模型目录：{project_config_instance.onnx_model_dir}中缺少captcha_ocr.onnx或captcha_ocr.onnx.data文件,将使用项目默认模型权重")
        else:
            logger.warn(f"指定的ONNX模型目录：{project_config_instance.onnx_model_dir}不存在,将使用项目默认模型权重")

    ocr = ONNXCaptchaRecognizer(str(onnx_model_path.absolute()))
    return ocr


class CaptchaOCR:
    def __init__(self):
        self.logger = structlog.get_logger(__name__)

    def recognize(self, captcha_control) -> Tuple[str, Image.Image]:
        """识别验证码
        Args:
            captcha_control : 验证码控件

        Returns:
            str: 识别结果
            Image.Image: 验证码图片
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
            result = ocr.recognize(image)
            self.logger.debug(f"验证码识别结果: {result}")
            return result, image

        except Exception as e:
            self.logger.error(f"验证码识别失败: {e}")
            return "", Image.Image()


@functools.lru_cache(maxsize=1)
def get_captcha_ocr_server() -> CaptchaOCR:
    return CaptchaOCR()
