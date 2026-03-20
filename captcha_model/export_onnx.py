"""
ONNX export script v2 for captcha recognition model.

Features:
- Opset version 14 for wider compatibility
- Model simplification with onnx-simplifier
- Improved validation

Usage:
    python -m captcha_model.export_onnx
    python -m captcha_model.export_onnx --model outputs/best_model.pth --validate
    python -m captcha_model.export_onnx --model outputs/best_model.pth --simplify
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))

from captcha_model.utils import load_config, get_device
from captcha_model.model import CaptchaRecognizer


class ONNXExportableModel(torch.nn.Module):
    """Wrapper model for ONNX export with softmax output."""

    def __init__(self, model: CaptchaRecognizer):
        super().__init__()
        self.model = model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass returning softmax probabilities."""
        log_output = self.model(x)
        return torch.exp(log_output)


def export_to_onnx(
    model,
    output_path: str,
    input_size: Tuple[int, int, int],
    device: torch.device,
    downsampling: int = 8,
    opset_version: int = 18,
    verbose: bool = True,
    metadata: Optional[Dict] = None,
) -> str:
    """
    Export PyTorch model to ONNX format.

    Args:
        model: The captcha recognition model.
        output_path: Path to save the ONNX model.
        input_size: Input tensor size (channels, height, width).
        device: Device to run export on.
        downsampling: Model downsampling factor (8 for enhanced).
        opset_version: ONNX opset version (14 for wider compatibility).
        verbose: Whether to print export details.
        metadata: Optional dict of metadata to embed in the ONNX model.

    Returns:
        Path to the exported ONNX model.
    """
    model.eval()

    export_model = ONNXExportableModel(model)
    export_model.eval()

    # Use larger batch_size for ONNX to support dynamic batching
    batch_size = 4
    channels, height, width = input_size
    dummy_input = torch.randn(batch_size, channels, height, width).to(device)

    seq_len = width // downsampling

    if verbose:
        print(f"Exporting model to ONNX...")
        print(f"  Input shape: {dummy_input.shape}")
        print(f"  Output sequence length: {seq_len}")
        print(f"  Opset version: {opset_version}")

    torch.onnx.export(
        export_model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "output": {1: "batch_size"},
        },
    )

    # Embed all necessary metadata into the ONNX model
    if metadata:
        import onnx
        onnx_model = onnx.load(output_path)
        for key, value in metadata.items():
            if isinstance(value, (list, dict)):
                import json
                value = json.dumps(value)
            elif not isinstance(value, str):
                value = str(value)
            meta = onnx_model.metadata_props.add()
            meta.key = key
            meta.value = value
        onnx.save(onnx_model, output_path)
        if verbose:
            print(f"  Metadata embedded: {list(metadata.keys())}")

    if verbose:
        print(f"Model exported to {output_path}")

    return output_path


def simplify_onnx_model(onnx_path: str, verbose: bool = True) -> bool:
    """
    Simplify ONNX model using onnx-simplifier.

    Args:
        onnx_path: Path to ONNX model.
        verbose: Whether to print details.

    Returns:
        True if simplification succeeded.
    """
    try:
        import onnx
        from onnxsim import simplify
    except ImportError:
        if verbose:
            print("onnx-simplifier not installed. Skipping simplification.")
            print("Install with: pip install onnx-simplifier")
        return False

    if verbose:
        print("\nSimplifying ONNX model...")

    try:
        onnx_model = onnx.load(onnx_path)
        model_simp, check = simplify(onnx_model)

        if check:
            # Save simplified model
            onnx.save(model_simp, onnx_path)
            if verbose:
                print("  Simplification: SUCCESS")
            return True
        else:
            if verbose:
                print("  Simplification: FAILED (check failed)")
            return False
    except Exception as e:
        if verbose:
            print(f"  Simplification: FAILED ({e})")
        return False


def validate_onnx_model(
    onnx_path: str,
    pytorch_model: CaptchaRecognizer,
    input_size: Tuple[int, int, int],
    device: torch.device,
    num_test_samples: int = 10,
    tolerance: float = 1e-4,
    verbose: bool = True,
) -> bool:
    """
    Validate ONNX model output matches PyTorch model.

    Args:
        onnx_path: Path to ONNX model.
        pytorch_model: Original PyTorch model.
        input_size: Input tensor size (channels, height, width).
        device: Device to run validation on.
        num_test_samples: Number of test samples.
        tolerance: Maximum allowed difference.
        verbose: Whether to print details.

    Returns:
        True if validation passes.
    """
    try:
        import onnx
        import onnxruntime as ort
    except ImportError:
        print("ONNX validation requires onnx and onnxruntime packages")
        return False

    if verbose:
        print("\nValidating ONNX model...")

    # Check ONNX model validity
    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)

    if verbose:
        print("  ONNX model structure: Valid")

    pytorch_model.eval()
    ort_session = ort.InferenceSession(onnx_path)

    channels, height, width = input_size

    all_passed = True
    max_diff = 0.0

    for i in range(num_test_samples):
        test_input = np.random.randn(1, channels, height, width).astype(np.float32)

        with torch.no_grad():
            torch_input = torch.from_numpy(test_input).to(device)
            torch_output = torch.exp(pytorch_model(torch_input))
            torch_output = torch_output.cpu().numpy()

        ort_output = ort_session.run(None, {"input": test_input})[0]

        diff = np.abs(torch_output - ort_output).max()
        max_diff = max(max_diff, diff)

        if diff > tolerance:
            if verbose:
                print(f"  Sample {i}: FAILED (max diff: {diff:.6f})")
            all_passed = False

    if verbose:
        print(f"  Max difference: {max_diff:.6f}")
        print(f"  Tolerance: {tolerance:.6f}")

        if all_passed:
            print("  Validation: PASSED")
        else:
            print("  Validation: FAILED")

    return all_passed


def run_export(
    model_path: str,
    output_path: Optional[str],
    config: Dict,
    validate: bool = True,
    simplify: bool = True,
    opset_version: int = 18,
    verbose: bool = True,
) -> str:
    """
    Run ONNX export with optional validation and simplification.

    Args:
        model_path: Path to trained PyTorch model.
        output_path: Path for ONNX output.
        config: Configuration dictionary.
        validate: Whether to validate ONNX model.
        simplify: Whether to simplify ONNX model.
        opset_version: ONNX opset version.
        verbose: Whether to print details.

    Returns:
        Path to exported ONNX model.
    """
    device = get_device()
    if verbose:
        print(f"Using device: {device}")

    if output_path is None:
        model_path_obj = Path(model_path)
        output_path = str(model_path_obj.with_suffix(".onnx"))

    charset_size = len(config["charset"])
    model_config = config.get("model", {})

    if verbose:
        print(f"Loading model from {model_path}...")

    model = CaptchaRecognizer(
        charset_size=charset_size,
        dropout=model_config.get("dropout", 0.2),
        hidden_size=model_config.get("hidden_size", 384),
        num_tcn_layers=model_config.get("num_tcn_layers", 4),
        kernel_size=model_config.get("kernel_size", 3),
    )

    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    model.load_state_dict(state_dict)

    model.to(device)

    channels = config["image"]["channels"]
    height = config["model"]["input_height"]
    width = config["model"]["input_width"]
    input_size = (channels, height, width)

    # Build metadata to embed in ONNX model
    normalization = config.get("preprocessing", {}).get("normalization", {})
    metadata = {
        "charset": config["charset"],
        "input_height": height,
        "input_width": width,
        "channels": channels,
        "mean": normalization.get("mean", [0.485, 0.456, 0.406]),
        "std": normalization.get("std", [0.229, 0.224, 0.225]),
        "captcha_min_length": config.get("captcha_length", {}).get("min", 4),
        "captcha_max_length": config.get("captcha_length", {}).get("max", 6),
        "downsampling": 8,
    }

    # Export to ONNX with embedded metadata
    export_to_onnx(
        model, output_path, input_size, device,
        downsampling=8, opset_version=opset_version, verbose=verbose,
        metadata=metadata,
    )

    # Simplify if requested
    if simplify:
        simplify_onnx_model(output_path, verbose=verbose)

    # Validate if requested
    if validate:
        success = validate_onnx_model(
            output_path, model, input_size, device, verbose=verbose
        )
        if not success:
            print("Warning: ONNX validation failed. The exported model may not be correct.")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Export captcha model to ONNX format")
    parser.add_argument(
        "--model",
        type=str,
        default="outputs/best_model.pth",
        help="Path to trained PyTorch model",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs/best_model.onnx",
        help="Path for ONNX output",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate ONNX model against PyTorch model",
    )
    parser.add_argument(
        "--simplify",
        action="store_true",
        help="Simplify ONNX model with onnx-simplifier",
    )
    parser.add_argument(
        "--opset",
        type=int,
        default=18,
        help="ONNX opset version (default: 18)",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    run_export(
        args.model,
        args.output,
        config,
        validate=args.validate,
        simplify=args.simplify,
        opset_version=args.opset,
    )


if __name__ == "__main__":
    main()
