"""
Captcha dataset generation script with automatic train/val/test splitting.

Generates captcha images and automatically splits them into train, validation, and test sets.

Usage:
    # Generate 10000 samples with default settings (auto-split to data/train, data/val, data/test)
    python -m captcha_model.generate_dataset

    # Generate with custom number of samples
    python -m captcha_model.generate_dataset --num_samples 20000

    # Generate with custom output directory
    python -m captcha_model.generate_dataset --output_dir my_data --num_samples 5000

    # Generate with custom split ratios
    python -m captcha_model.generate_dataset --train_ratio 0.7 --val_ratio 0.2 --test_ratio 0.1

    # Generate case-sensitive dataset (uppercase rendered larger for visual distinction)
    python -m captcha_model.generate_dataset --case_sensitive
"""

import argparse
import random
import shutil
import sys
import uuid
from pathlib import Path
from typing import Dict, Optional

import numpy as np
from PIL import Image
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from captcha.image import ImageCaptcha
except ImportError:
    raise ImportError(
        "captcha library is required. Install it with: pip install captcha"
    )


class CaseSensitiveCaptcha(ImageCaptcha):
    """ImageCaptcha subclass that scales lowercase letters smaller to ensure
    visual distinguishability between upper and lower case characters.

    Uppercase letters are rendered at normal size, while lowercase letters
    are randomly scaled down within [lower_scale_min, lower_scale_max].
    """

    def __init__(self, *args, lower_scale_min: float = 0.7, lower_scale_max: float = 0.85, **kwargs):
        super().__init__(*args, **kwargs)
        self.lower_scale_min = lower_scale_min
        self.lower_scale_max = lower_scale_max

    def _draw_character(self, c, draw, color):
        im = super()._draw_character(c, draw, color)
        if c.islower():
            scale = random.uniform(self.lower_scale_min, self.lower_scale_max)
            w, h = im.size
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            im = im.resize((new_w, new_h), Image.Resampling.BILINEAR)
        return im


def generate_and_split_dataset(
    output_dir: str = "data",
    num_samples: int = 10000,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    config_path: Optional[str] = None,
    seed: int = 42,
    case_sensitive: Optional[bool] = None,
) -> Dict[str, int]:
    """
    Generate captcha images and split into train/val/test sets.

    Args:
        output_dir: Base output directory (default: "data").
        num_samples: Total number of samples to generate (default: 10000).
        train_ratio: Training set ratio (default: 0.8).
        val_ratio: Validation set ratio (default: 0.1).
        test_ratio: Test set ratio (default: 0.1).
        config_path: Path to configuration file (default: None, uses default config).
        seed: Random seed for reproducibility (default: 42).
        case_sensitive: Override config case_sensitive setting (default: None, uses config).

    Returns:
        Dictionary with generation and split statistics.
    """
    from captcha_model.utils import load_config

    # Load config
    config = load_config(config_path)

    # Determine case sensitivity: CLI arg > config > default (false)
    if case_sensitive is None:
        case_sensitive = config.get("case_sensitive", False)

    charset = config["charset"]
    captcha_length = config.get("captcha_length", {"min": 4, "max": 6})
    min_length = captcha_length.get("min", 4) if isinstance(captcha_length, dict) else captcha_length
    max_length = captcha_length.get("max", 6) if isinstance(captcha_length, dict) else captcha_length
    image_width = config["image"]["width"]
    image_height = config["image"]["height"]

    # Validate ratios
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 0.001:
        raise ValueError(f"Ratios must sum to 1.0, got {total_ratio}")

    # Set random seed
    random.seed(seed)
    np.random.seed(seed)

    # Create output directories
    output_path = Path(output_dir)
    temp_dir = output_path / "temp_all"
    train_dir = output_path / "train"
    val_dir = output_path / "val"
    test_dir = output_path / "test"

    temp_dir.mkdir(parents=True, exist_ok=True)
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    # Initialize captcha generator
    if case_sensitive:
        lower_scale_cfg = config.get("lower_scale", {})
        generator = CaseSensitiveCaptcha(
            width=image_width,
            height=image_height,
            lower_scale_min=lower_scale_cfg.get("min", 0.7),
            lower_scale_max=lower_scale_cfg.get("max", 0.85),
        )
    else:
        generator = ImageCaptcha(width=image_width, height=image_height, fonts=None)

    # Generate all samples to temp directory
    mode_str = f"case-sensitive (lowercase scaled to {generator.lower_scale_min:.0%}-{generator.lower_scale_max:.0%})" if case_sensitive else "case-insensitive"
    print(f"Generating {num_samples} captcha images ({mode_str})...")
    print(f"  Charset: {charset} ({len(charset)} characters)")
    print(f"  Length range: {min_length}-{max_length}")
    print(f"  Image size: {image_width}x{image_height}")
    print(f"  Output: {output_dir}")
    print(f"  Split ratios: train={train_ratio:.1%}, val={val_ratio:.1%}, test={test_ratio:.1%}")

    length_counts: Dict[int, int] = {}

    for _ in tqdm(range(num_samples), desc="Generating images"):
        # Generate random label with random length
        length = random.randint(min_length, max_length)
        label = "".join(random.choice(charset) for _ in range(length))

        # Track length distribution
        length_counts[length] = length_counts.get(length, 0) + 1

        # Generate image
        image_bytes = generator.generate(label)
        image = Image.open(image_bytes)

        # Save with naming format: {captcha}_{uuid}.png
        image_uuid = str(uuid.uuid4())[:8]
        filename = f"{label}_{image_uuid}.png"
        image.save(temp_dir / filename)

    print(f"\n✓ Generated {num_samples} samples")
    print(f"  Length distribution: {dict(sorted(length_counts.items()))}")

    # Split dataset
    print(f"\nSplitting into train/val/test sets...")

    # Get all generated files
    all_files = list(temp_dir.glob("*.png"))
    random.shuffle(all_files)

    # Calculate split sizes
    train_size = int(num_samples * train_ratio)
    val_size = int(num_samples * val_ratio)

    # Split files
    train_files = all_files[:train_size]
    val_files = all_files[train_size:train_size + val_size]
    test_files = all_files[train_size + val_size:]

    # Copy files to respective directories
    def copy_files(files, dest_dir, desc):
        for f in tqdm(files, desc=f"  Copying to {desc}"):
            shutil.copy2(f, dest_dir / f.name)

    copy_files(train_files, train_dir, "train")
    copy_files(val_files, val_dir, "val")
    copy_files(test_files, test_dir, "test")

    # Clean up temp directory
    shutil.rmtree(temp_dir)

    # Print summary
    print(f"\n✓ Dataset split complete:")
    print(f"  Total: {num_samples}")
    print(f"  Train: {len(train_files)} ({len(train_files)/num_samples*100:.1f}%)")
    print(f"  Val:   {len(val_files)} ({len(val_files)/num_samples*100:.1f}%)")
    print(f"  Test:  {len(test_files)} ({len(test_files)/num_samples*100:.1f}%)")
    print(f"\nDirectories:")
    print(f"  Train: {train_dir.absolute()}")
    print(f"  Val:   {val_dir.absolute()}")
    print(f"  Test:  {test_dir.absolute()}")

    return {
        "total": num_samples,
        "train": len(train_files),
        "val": len(val_files),
        "test": len(test_files),
        "length_distribution": length_counts,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate captcha dataset with automatic train/val/test splitting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate 10000 samples with default settings
    python -m captcha_model.generate_dataset

    # Generate 20000 samples
    python -m captcha_model.generate_dataset --num_samples 20000

    # Generate to custom directory
    python -m captcha_model.generate_dataset --output_dir my_data --num_samples 5000

    # Custom split ratios
    python -m captcha_model.generate_dataset --train_ratio 0.7 --val_ratio 0.2 --test_ratio 0.1

    # Generate case-sensitive dataset (uppercase rendered larger)
    python -m captcha_model.generate_dataset --case_sensitive
        """
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="data",
        help="Output directory for dataset (default: data)",
    )
    parser.add_argument(
        "--num_samples",
        type=int,
        default=10000,
        help="Total number of samples to generate (default: 10000)",
    )
    parser.add_argument(
        "--train_ratio",
        type=float,
        default=0.8,
        help="Training set ratio (default: 0.8)",
    )
    parser.add_argument(
        "--val_ratio",
        type=float,
        default=0.1,
        help="Validation set ratio (default: 0.1)",
    )
    parser.add_argument(
        "--test_ratio",
        type=float,
        default=0.1,
        help="Test set ratio (default: 0.1)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (default: use default config)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    case_group = parser.add_mutually_exclusive_group()
    case_group.add_argument(
        "--case_sensitive",
        action="store_true",
        default=None,
        help="Generate case-sensitive dataset (lowercase scaled down for distinction)",
    )
    case_group.add_argument(
        "--no_case_sensitive",
        action="store_true",
        default=None,
        help="Generate case-insensitive dataset (no size distinction)",
    )
    args = parser.parse_args()

    # Determine case_sensitive override
    case_sensitive = None
    if args.case_sensitive:
        case_sensitive = True
    elif args.no_case_sensitive:
        case_sensitive = False

    generate_and_split_dataset(
        output_dir=args.output_dir,
        num_samples=args.num_samples,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        config_path=args.config,
        seed=args.seed,
        case_sensitive=case_sensitive,
    )


if __name__ == "__main__":
    main()
