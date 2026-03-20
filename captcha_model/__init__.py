"""
Captcha Recognition Model Module
================================

High-performance captcha recognition using ResNet + TCN + Attention.

Features:
- ResNet-style backbone with residual connections
- TCN (Temporal Convolutional Network) for sequence modeling
- Lightweight self-attention for global context
- CTC Loss for variable-length captcha support
- ROCm compatible (AMD GPU), ONNX export ready

Quick Start:
-----------

1. Train the model:
   ```bash
   python -m captcha_model.train
   ```

2. Evaluate:
   ```bash
   python -m captcha_model.eval --model outputs/best_model.pth
   ```

3. Export to ONNX:
   ```bash
   python -m captcha_model.export_onnx --model outputs/best_model.pth --validate
   ```

4. Run inference:
   ```bash
   python -m captcha_model.infer --model model.pth --image captcha.png
   ```

Configuration:
-------------
Edit `config.yaml` to customize:
- `charset`: Character set for captchas
- `model`: Architecture parameters (hidden_size, num_tcn_layers, dropout)
- `training`: Training hyperparameters
- `dataset`: Paths to train/val/test data

Filename Format:
---------------
Images should be named: `{captcha_text}_{uuid}.png`
Example: `a1b2c_3f8a9e84.png`
"""

__version__ = "2.0.0"

from captcha_model.utils import load_config, get_device
from captcha_model.model import CaptchaRecognizer, CTCLoss
from captcha_model.dataset import CaptchaDataset, TorchCaptchaDataset, create_dataloader

__all__ = [
    "load_config",
    "get_device",
    "CaptchaRecognizer",
    "CTCLoss",
    "CaptchaDataset",
    "TorchCaptchaDataset",
    "create_dataloader",
]
