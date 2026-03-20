"""
Captcha dataset module v2 with enhanced augmentation.

Features:
- Elastic transformation
- Gaussian blur
- Random line interference
- Custom normalization support
"""

import random
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


def parse_label_from_filename(filename: str, charset: str) -> Tuple[str, bool]:
    """
    Parse captcha label from filename.

    Filename format: {captcha}_{uuid}.png
    Example: "a1b2c_3f8a9.png" -> label="a1b2c"
    """
    name = Path(filename).stem
    match = re.match(r"^(.+)_[a-f0-9]+$", name)
    if match:
        label = match.group(1)
    else:
        label = name
    is_valid = all(c in charset for c in label)
    return label, is_valid


def add_random_lines(
    image: Image.Image,
    num_lines: int = 2,
    max_width: int = 2,
) -> Image.Image:
    """Add random interference lines to the image."""
    if num_lines <= 0:
        return image

    draw = ImageDraw.Draw(image)
    width, height = image.size

    for _ in range(num_lines):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)

        # Random color (gray tones)
        gray = random.randint(50, 200)
        color = (gray, gray, gray) if image.mode == "RGB" else gray

        line_width = random.randint(1, max_width)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=line_width)

    return image


def augment_image(
    image: Image.Image,
    rotation_range: float = 5,
    width_shift_range: float = 0.05,
    height_shift_range: float = 0.05,
    zoom_range: float = 0.05,
    brightness_range: Tuple[float, float] = (0.9, 1.1),
    contrast_range: Tuple[float, float] = (0.9, 1.1),
    noise_std: float = 0.01,
    blur_prob: float = 0.3,
    blur_radius: float = 1.0,
    line_prob: float = 0.3,
    num_lines: int = 2,
    elastic_prob: float = 0.2,
) -> Image.Image:
    """
    Apply enhanced data augmentation to captcha image.

    Args:
        image: PIL Image to augment.
        rotation_range: Random rotation range in degrees (±).
        width_shift_range: Random width shift as fraction.
        height_shift_range: Random height shift as fraction.
        zoom_range: Random zoom range as fraction.
        brightness_range: Random brightness range (min, max).
        contrast_range: Random contrast range (min, max).
        noise_std: Gaussian noise standard deviation.
        blur_prob: Probability of applying Gaussian blur.
        blur_radius: Blur radius.
        line_prob: Probability of adding interference lines.
        num_lines: Number of interference lines.
        elastic_prob: Probability of elastic deformation.

    Returns:
        Augmented PIL Image.
    """
    # Random rotation
    if rotation_range > 0:
        angle = random.uniform(-rotation_range, rotation_range)
        image = image.rotate(angle, resample=Image.Resampling.BILINEAR, expand=False)

    width, height = image.size

    # Random shift
    if width_shift_range > 0 or height_shift_range > 0:
        dx = random.uniform(-width_shift_range, width_shift_range) * width
        dy = random.uniform(-height_shift_range, height_shift_range) * height
        image = image.transform(
            image.size,
            Image.Transform.AFFINE,
            (1, 0, -dx, 0, 1, -dy),
            resample=Image.Resampling.BILINEAR,
        )

    # Random zoom
    if zoom_range > 0:
        zoom_factor = random.uniform(1 - zoom_range, 1 + zoom_range)
        new_width = int(width * zoom_factor)
        new_height = int(height * zoom_factor)
        image = image.resize((new_width, new_height), Image.Resampling.BILINEAR)
        if zoom_factor > 1:
            left = (new_width - width) // 2
            top = (new_height - height) // 2
            image = image.crop((left, top, left + width, top + height))
        else:
            pad_width = (width - new_width) // 2
            pad_height = (height - new_height) // 2
            new_image = Image.new(image.mode, (width, height), (255, 255, 255) if image.mode == "RGB" else 255)
            new_image.paste(image, (pad_width, pad_height))
            image = new_image

    # Random brightness
    if brightness_range[0] < brightness_range[1]:
        brightness = random.uniform(brightness_range[0], brightness_range[1])
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(brightness)

    # Random contrast
    if contrast_range[0] < contrast_range[1]:
        contrast = random.uniform(contrast_range[0], contrast_range[1])
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(contrast)

    # Random Gaussian blur
    if blur_prob > 0 and random.random() < blur_prob:
        image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Random interference lines
    if line_prob > 0 and random.random() < line_prob:
        image = add_random_lines(image, num_lines=num_lines)

    # Simple elastic-like deformation using affine transforms
    if elastic_prob > 0 and random.random() < elastic_prob:
        # Apply small random warps
        for _ in range(random.randint(1, 3)):
            angle = random.uniform(-3, 3)
            image = image.rotate(angle, resample=Image.Resampling.BILINEAR, expand=False)

    # Add Gaussian noise
    if noise_std > 0:
        img_array = np.array(image, dtype=np.float32)
        noise = np.random.normal(0, noise_std * 255, img_array.shape)
        img_array = np.clip(img_array + noise, 0, 255).astype(np.uint8)
        image = Image.fromarray(img_array)

    return image


class CaptchaDataset:
    """
    Dataset for reading captcha images from disk.
    """

    def __init__(
        self,
        data_dir: str,
        charset: str,
        target_width: int = 160,
        target_height: int = 64,
        channels: int = 3,
        transform: Optional[Callable] = None,
        is_training: bool = True,
        augmentation_config: Optional[Dict] = None,
    ):
        self.data_dir = Path(data_dir)
        self.charset = charset
        self.target_width = target_width
        self.target_height = target_height
        self.channels = channels
        self.transform = transform
        self.is_training = is_training
        self.augmentation_config = augmentation_config

        self.char_to_idx = {char: idx + 1 for idx, char in enumerate(charset)}
        self.idx_to_char = {idx + 1: char for idx, char in enumerate(charset)}
        self.idx_to_char[0] = ""

        self.image_files: List[Path] = []
        self.labels: List[str] = []
        self._scan_directory()

        self.indices = list(range(len(self.image_files)))
        if is_training:
            random.shuffle(self.indices)

    def _scan_directory(self) -> None:
        """Scan directory for valid captcha images."""
        if not self.data_dir.exists():
            raise ValueError(f"Data directory does not exist: {self.data_dir}")

        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp'}
        png_files = [f for f in self.data_dir.iterdir()
                     if f.suffix.lower() in image_extensions]

        for filepath in png_files:
            label, is_valid = parse_label_from_filename(filepath.name, self.charset)
            if is_valid and len(label) > 0:
                self.image_files.append(filepath)
                self.labels.append(label)

        if not self.image_files:
            raise ValueError(f"No valid captcha images found in {self.data_dir}")

    def __len__(self) -> int:
        return len(self.image_files)

    def __getitem__(self, idx: int) -> Tuple[np.ndarray, str]:
        real_idx = self.indices[idx]
        image = Image.open(self.image_files[real_idx])

        if self.channels == 3:
            if image.mode != "RGB":
                image = image.convert("RGB")
        else:
            if image.mode != "L":
                image = image.convert("L")

        # Apply augmentation if enabled (only for training)
        if self.is_training and self.augmentation_config and self.augmentation_config.get("enabled", False):
            image = augment_image(
                image,
                rotation_range=self.augmentation_config.get("rotation_range", 5),
                width_shift_range=self.augmentation_config.get("width_shift_range", 0.05),
                height_shift_range=self.augmentation_config.get("height_shift_range", 0.05),
                zoom_range=self.augmentation_config.get("zoom_range", 0.05),
                brightness_range=tuple(self.augmentation_config.get("brightness_range", [0.9, 1.1])),
                contrast_range=tuple(self.augmentation_config.get("contrast_range", [0.9, 1.1])),
                noise_std=self.augmentation_config.get("noise_std", 0.01),
                blur_prob=self.augmentation_config.get("blur_prob", 0.3),
                blur_radius=self.augmentation_config.get("blur_radius", 1.0),
                line_prob=self.augmentation_config.get("line_prob", 0.3),
                num_lines=self.augmentation_config.get("num_lines", 2),
                elastic_prob=self.augmentation_config.get("elastic_prob", 0.2),
            )

        image = image.resize(
            (self.target_width, self.target_height),
            Image.Resampling.BILINEAR
        )

        image_array = np.array(image, dtype=np.float32)

        if self.transform is not None:
            image_array = self.transform(image_array)

        label = self.labels[real_idx]
        return image_array, label


class TorchCaptchaDataset(CaptchaDataset):
    """
    PyTorch-compatible captcha dataset for CTC training.
    """

    # Default ImageNet normalization
    IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __init__(self, *args, mean: Optional[np.ndarray] = None, std: Optional[np.ndarray] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.mean = mean if mean is not None else self.IMAGENET_MEAN
        self.std = std if std is not None else self.IMAGENET_STD

    def __getitem__(self, idx: int) -> Tuple["torch.Tensor", "torch.Tensor", int]:
        import torch

        image, label = super().__getitem__(idx)
        image = image / 255.0

        # Apply normalization
        if self.channels == 3:
            image = (image - self.mean) / self.std
            image = np.transpose(image, (2, 0, 1))
        else:
            image = (image - self.mean[0]) / self.std[0]
            image = np.expand_dims(image, 0)

        image_tensor = torch.from_numpy(image)

        encoded_label = np.array(
            [self.char_to_idx[char] for char in label],
            dtype=np.int64
        )
        label_tensor = torch.from_numpy(encoded_label)
        label_length = len(label)

        return image_tensor, label_tensor, label_length


def ctc_collate_fn(batch: List[Tuple]) -> Tuple:
    """Collate function for CTC training with variable-length sequences."""
    import torch

    images = []
    targets = []
    label_lengths = []

    for image, label, label_length in batch:
        images.append(image)
        targets.append(label)
        label_lengths.append(label_length)

    images = torch.stack(images, dim=0)
    targets = torch.cat(targets, dim=0)
    target_lengths = torch.tensor(label_lengths, dtype=torch.long)

    _, _, H, W = images.shape
    seq_len = W // 8  # CRNN backbone: conv1(pool2,2) + conv2(pool2,2) + conv3(pool2,2) = 8x
    input_lengths = torch.full((images.size(0),), seq_len, dtype=torch.long)

    return images, targets, input_lengths, target_lengths


def create_dataloader(
    data_dir: str,
    config: Dict,
    is_training: bool = True,
    batch_size: Optional[int] = None,
    num_workers: int = 0,
    transform: Optional[Callable] = None,
) -> "torch.utils.data.DataLoader":
    """Create a PyTorch DataLoader for captcha data."""
    import torch
    from torch.utils.data import DataLoader

    augmentation_config = None
    if is_training and config.get("preprocessing", {}).get("augmentation", {}).get("enabled", False):
        augmentation_config = config["preprocessing"]["augmentation"]

    # Get custom normalization if provided
    norm_config = config.get("preprocessing", {}).get("normalization", {})
    mean = np.array(norm_config.get("mean", [0.485, 0.456, 0.406]), dtype=np.float32)
    std = np.array(norm_config.get("std", [0.229, 0.224, 0.225]), dtype=np.float32)

    dataset = TorchCaptchaDataset(
        data_dir=data_dir,
        charset=config["charset"],
        target_width=config["model"]["input_width"],
        target_height=config["model"]["input_height"],
        channels=config["image"]["channels"],
        transform=transform,
        is_training=is_training,
        augmentation_config=augmentation_config,
        mean=mean,
        std=std,
    )

    if batch_size is None:
        batch_size = (
            config["training"]["batch_size"]
            if is_training
            else config["evaluation"]["batch_size"]
        )

    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=is_training,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
        collate_fn=ctc_collate_fn,
    )
