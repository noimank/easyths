"""
Utility functions and configuration management for captcha recognition model.

Configuration is managed centrally through config.yaml file.
All default values are defined in config.yaml, not in code.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yaml


# Required configuration keys for validation
REQUIRED_CONFIG_KEYS = {
    "charset",
    "captcha_length",
    "image",
    "model",
    "dataset",
    "training",
    "evaluation",
}


def find_config_file() -> Optional[Path]:
    """Find the configuration file in standard locations."""
    possible_paths = [
        Path("config.yaml"),
        Path("captcha_model/config.yaml"),
        Path(__file__).parent / "config.yaml",
    ]
    for path in possible_paths:
        if path.exists():
            return path
    return None


def validate_config(config: Dict) -> None:
    """
    Validate configuration dictionary.

    Args:
        config: Configuration dictionary to validate.

    Raises:
        ValueError: If required keys are missing or values are invalid.
    """
    # Check required keys
    missing_keys = REQUIRED_CONFIG_KEYS - set(config.keys())
    if missing_keys:
        raise ValueError(f"Missing required config keys: {missing_keys}")

    # Validate charset
    if not config["charset"]:
        raise ValueError("charset cannot be empty")

    # Validate captcha length
    captcha_length = config["captcha_length"]
    if isinstance(captcha_length, dict):
        min_len = captcha_length.get("min", 4)
        max_len = captcha_length.get("max", 6)
    else:
        min_len = max_len = captcha_length

    if min_len < 1 or max_len < min_len:
        raise ValueError(f"Invalid captcha_length: min={min_len}, max={max_len}")

    # Validate model input size
    model = config["model"]
    input_width = model.get("input_width", 160)
    input_height = model.get("input_height", 64)

    if input_width < 32 or input_height < 16:
        raise ValueError(f"Input size too small: {input_width}x{input_height}")

    # Validate sequence length is sufficient for CTC
    # EnhancedBackbone downsamples by 8x, so seq_len = input_width / 8
    seq_len = input_width // 8
    if seq_len < max_len + 2:
        raise ValueError(
            f"Sequence length ({seq_len}) too short for max captcha length ({max_len}). "
            f"Increase input_width to at least {(max_len + 2) * 8}"
        )


def load_config(config_path: Optional[str] = None) -> Dict:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, searches standard locations.

    Returns:
        Configuration dictionary.

    Raises:
        FileNotFoundError: If no config file is found.
        ValueError: If configuration is invalid.
    """
    if config_path is not None:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
    else:
        path = find_config_file()
        if path is None:
            raise FileNotFoundError(
                "No config.yaml found. Please create one or specify --config"
            )

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Validate configuration
    validate_config(config)

    return config


def ensure_output_dir(output_dir: str) -> Path:
    """Ensure output directory exists."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_device() -> "torch.device":
    """Get the best available device for computation."""
    try:
        import torch
        if torch.cuda.is_available():
            return torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
    except ImportError:
        pass
    return "cpu"


def calculate_ctc_accuracy(
    predictions: List[List[int]],
    targets: List[List[int]],
) -> Tuple[float, float]:
    """
    Calculate character-level and sequence-level accuracy for CTC outputs.

    Args:
        predictions: List of predicted sequences (variable length).
        targets: List of target sequences (variable length).

    Returns:
        Tuple of (char_accuracy, sequence_accuracy).
    """
    if not predictions or not targets:
        return 0.0, 0.0

    total_char_correct = 0
    total_char = 0
    seq_correct = 0

    for pred, target in zip(predictions, targets):
        if pred == target:
            seq_correct += 1

        min_len = min(len(pred), len(target))
        for i in range(min_len):
            if pred[i] == target[i]:
                total_char_correct += 1

        total_char += len(target)

    char_accuracy = total_char_correct / total_char if total_char > 0 else 0.0
    seq_accuracy = seq_correct / len(targets) if len(targets) > 0 else 0.0

    return char_accuracy, seq_accuracy


def decode_predictions(
    predictions: List[List[int]],
    idx_to_char: Dict[int, str],
) -> List[str]:
    """Decode predicted indices to strings."""
    return [
        "".join(idx_to_char[idx] for idx in pred if idx in idx_to_char)
        for pred in predictions
    ]


def encode_labels(
    labels: List[str],
    char_to_idx: Dict[str, int],
) -> List[List[int]]:
    """Encode string labels to index sequences."""
    return [
        [char_to_idx[char] for char in label]
        for label in labels
    ]
