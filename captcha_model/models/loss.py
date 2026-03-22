"""
CTC Loss and Dataset for Captcha Recognition.

Dataset format: {captcha_text}_{uuid}.png
Labels are extracted from filenames automatically.
"""

import os
import random
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class EnhancedAugmentation:
    """
    Enhanced data augmentation for captcha images.

    Author: noimank (康康)
    Email: noimank@163.com
    """

    def __init__(
            self,
            brightness_prob: float = 0.5,
            brightness_range: tuple = (0.8, 1.2),
            contrast_prob: float = 0.5,
            contrast_range: tuple = (0.8, 1.2),
            rotation_prob: float = 0.3,
            rotation_range: tuple = (-5, 5),
            noise_prob: float = 0.3,
            noise_std: float = 0.02,
            blur_prob: float = 0.2,
            blur_kernel_range: tuple = (3, 5),
            cutout_prob: float = 0.1,
            cutout_size: int = 10
    ):
        self.brightness_prob = brightness_prob
        self.brightness_range = brightness_range
        self.contrast_prob = contrast_prob
        self.contrast_range = contrast_range
        self.rotation_prob = rotation_prob
        self.rotation_range = rotation_range
        self.noise_prob = noise_prob
        self.noise_std = noise_std
        self.blur_prob = blur_prob
        self.blur_kernel_range = blur_kernel_range
        self.cutout_prob = cutout_prob
        self.cutout_size = cutout_size

    def __call__(self, img: 'np.ndarray') -> 'np.ndarray':
        """Apply data augmentation."""
        import cv2

        # 1. Brightness adjustment
        if random.random() < self.brightness_prob:
            brightness = random.uniform(*self.brightness_range)
            img = np.clip(img.astype(np.float32) * brightness, 0, 255).astype(np.uint8)

        # 2. Contrast adjustment
        if random.random() < self.contrast_prob:
            contrast = random.uniform(*self.contrast_range)
            mean = img.mean()
            img = np.clip((img.astype(np.float32) - mean) * contrast + mean, 0, 255).astype(np.uint8)

        # 3. Random rotation
        if random.random() < self.rotation_prob:
            angle = random.uniform(*self.rotation_range)
            h, w = img.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

        # 4. Gaussian noise
        if random.random() < self.noise_prob:
            noise = np.random.normal(0, self.noise_std * 255, img.shape).astype(np.float32)
            img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        # 5. Gaussian blur
        if random.random() < self.blur_prob:
            kernel_size = random.choice(range(self.blur_kernel_range[0], self.blur_kernel_range[1] + 1, 2))
            img = cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)

        # 6. Random cutout
        if random.random() < self.cutout_prob:
            h, w = img.shape[:2]
            y = random.randint(0, max(0, h - self.cutout_size))
            x = random.randint(0, max(0, w - self.cutout_size))
            img[y:y + self.cutout_size, x:x + self.cutout_size] = 0

        return img


class CTCLoss(nn.Module):
    """Connectionist Temporal Classification Loss."""

    def __init__(
            self,
            num_classes: int,
            blank: int = None,
            reduction: str = 'mean',
            zero_infinity: bool = True
    ):
        super().__init__()

        self.num_classes = num_classes
        self.blank = num_classes - 1 if blank is None else blank
        self.reduction = reduction
        self.zero_infinity = zero_infinity

    def forward(
            self,
            log_probs: torch.Tensor,
            targets: torch.Tensor,
            input_lengths: Optional[torch.Tensor] = None,
            target_lengths: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        if input_lengths is None:
            input_lengths = torch.full(
                size=(log_probs.size(0),),
                fill_value=log_probs.size(1),
                dtype=torch.long
            )

        if target_lengths is None:
            target_lengths = torch.full(
                size=(targets.size(0),),
                fill_value=targets.size(1),
                dtype=torch.long
            )

        log_probs = F.log_softmax(log_probs, dim=1)

        loss = F.ctc_loss(
            log_probs.transpose(0, 1),
            targets,
            input_lengths,
            target_lengths,
            blank=self.blank,
            reduction=self.reduction,
            zero_infinity=self.zero_infinity
        )

        return loss


class CaptchaDataset(torch.utils.data.Dataset):
    """
    Dataset for captcha recognition training.

    Filename format: {captcha_text}_{uuid}.png
    Labels are extracted from filenames automatically.

    Args:
        data_dir: Directory containing captcha images
        img_h: Image height
        img_w: Image width
        character: Character set for recognition
        augment: Whether to apply data augmentation
        augmentation_config: Data augmentation configuration
    """

    def __init__(
            self,
            data_dir: str,
            img_h: int = 64,
            img_w: int = 256,
            character: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
            augment: bool = True,
            augmentation_config: dict = None
    ):
        self.data_dir = data_dir
        self.img_h = img_h
        self.img_w = img_w
        self.character = character
        self.augment = augment
        self.training = True

        # Initialize augmentation
        if augmentation_config and augmentation_config.get('enabled', False):
            self.augmentor = EnhancedAugmentation(**{
                k: v for k, v in augmentation_config.items() if k != 'enabled'
            })
        else:
            self.augmentor = None

        # Character to index mapping (blank is last index)
        self.char_to_idx = {char: idx for idx, char in enumerate(character)}
        self.blank_idx = len(character)

        # Load samples from filenames
        self.samples = self._load_samples()

    def _load_samples(self) -> list:
        """Load samples from directory, extracting labels from filenames."""
        samples = []
        data_path = self.data_dir

        if not os.path.exists(data_path):
            print(f"Warning: Data directory not found: {data_path}")
            return samples

        for filename in os.listdir(data_path):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                # Extract label from filename: {captcha_text}_{uuid}.png
                # Find the last underscore before the extension
                name_without_ext = os.path.splitext(filename)[0]

                # Find the last underscore (separates captcha from uuid)
                last_underscore = name_without_ext.rfind('_')
                if last_underscore > 0:
                    label = name_without_ext[:last_underscore]
                else:
                    # No underscore found, use entire name as label
                    label = name_without_ext

                # Validate label characters
                if all(c in self.char_to_idx for c in label):
                    samples.append((os.path.join(data_path, filename), label))
                else:
                    print(f"Warning: Skipping file with invalid characters: {filename}")

        return samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx: int):
        import cv2

        img_path, label = self.samples[idx]

        # Load image in RGB format
        img = cv2.imread(img_path, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError(f"Failed to load image: {img_path}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Resize
        img = cv2.resize(img, (self.img_w, self.img_h))

        # Data augmentation
        if self.augmentor and self.training:
            img = self.augmentor(img)
        elif self.augment and self.training:
            if random.random() > 0.5:
                brightness = random.uniform(0.8, 1.2)
                img = np.clip(img.astype(np.float32) * brightness, 0, 255).astype(np.uint8)

            if random.random() > 0.5:
                contrast = random.uniform(0.8, 1.2)
                mean = img.mean()
                img = np.clip((img.astype(np.float32) - mean) * contrast + mean, 0, 255).astype(np.uint8)

        # Normalize (H, W, C) -> (C, H, W)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))

        # Convert to tensor
        img = torch.from_numpy(img).float()

        # Convert label to tensor
        label_tensor = self.encode_label(label)

        return img, label_tensor, len(label_tensor)

    def encode_label(self, label: str) -> torch.Tensor:
        """Encode label string to tensor of indices."""
        indices = [self.char_to_idx[c] for c in label]
        return torch.tensor(indices, dtype=torch.long)

    def decode_label(self, indices: torch.Tensor) -> str:
        """Decode indices to label string using CTC decoding."""
        result = []
        prev = -1
        for idx in indices:
            if idx != prev and idx != self.blank_idx:
                char = None
                if idx < len(self.character):
                    char = self.character[idx]
                if char:
                    result.append(char)
            prev = idx
        return ''.join(result)
