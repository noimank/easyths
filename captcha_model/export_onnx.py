"""
Export Captcha Recognition Model to ONNX Format.

All necessary parameters (character set, image size) are embedded into the ONNX
model metadata, so inference only requires the ONNX file without external config.

Usage:
    python export_onnx.py                    # Export with default config
    python export_onnx.py --model path/to/model.pt  # Export specific model
    python export_onnx.py --output onnx_model  # Custom output directory

Author: noimank (康康)
Email: noimank@163.com
"""
import os
import sys
import warnings
import logging
from pathlib import Path
import numpy as np

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
logging.getLogger('torch.onnx').setLevel(logging.ERROR)
warnings.filterwarnings('ignore')

import argparse
import yaml
import torch
import onnx
import onnxruntime as ort

from models.resnet_ocr import ResNetOCR


def parse_args():
    parser = argparse.ArgumentParser(description="Export Captcha Model to ONNX")

    parser.add_argument("--config", type=str, default="config.yaml",
                        help="Config file path")
    parser.add_argument("--model", type=str, default="outputs/best_model.pt",
                        help="Model path (.pt)")
    parser.add_argument("--output", type=str, default="onnx_model",
                        help="Output directory")
    parser.add_argument("--name", type=str, default="captcha_ocr.onnx",
                        help="Output ONNX file name")
    parser.add_argument("--opset", type=int, default=18,
                        help="ONNX opset version (18 recommended, use 17+ for best compatibility)")

    return parser.parse_args()


def main():
    args = parse_args()

    # Load config
    with open(args.config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    global_cfg = config.get('Global', {})

    character = global_cfg.get('character', "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    img_h = global_cfg.get('img_h', 64)
    img_w = global_cfg.get('img_w', 256)
    num_classes = len(character) + 1

    print("\n" + "=" * 60)
    print("Exporting Captcha Recognition Model to ONNX")
    print("=" * 60)
    print(f"Config: {args.config}")
    print(f"Model: {args.model}")
    print(f"Image size: {img_h}x{img_w}")
    print(f"Character set: {character[:20]}... ({len(character)} chars)")
    print(f"Num classes: {num_classes}")
    print(f"Opset: {args.opset}")
    print("=" * 60)

    # Check model path
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        sys.exit(1)

    # Build model
    device = torch.device("cpu")
    model = ResNetOCR(
        img_h=img_h,
        img_w=img_w,
        num_classes=num_classes,
        character=character,
        pretrained=False,
        freeze_backbone=True
    ).to(device)

    # Load weights
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
        state_dict = checkpoint['model_state_dict']
    else:
        state_dict = checkpoint
    model.load_state_dict(state_dict)
    model.eval()

    print("Model loaded successfully")

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / args.name

    # Export to ONNX
    try:
        dummy_input = torch.randn(1, 3, img_h, img_w)

        # Export with specified opset version
        # Note: onnxscript may attempt version conversion for lower opsets
        # Use opset 17+ for best compatibility with modern PyTorch operations
        torch.onnx.export(
            model,
            dummy_input,
            str(output_path),
            input_names=["input"],
            output_names=["output"],
            opset_version=args.opset,
            dynamic_axes=None,
            training=torch.onnx.TrainingMode.EVAL
        )

        # Add metadata to ONNX model
        onnx_model = onnx.load(str(output_path))

        # Embed inference parameters into model metadata
        meta = onnx_model.metadata_props.add()
        meta.key = "character"
        meta.value = character

        meta = onnx_model.metadata_props.add()
        meta.key = "img_h"
        meta.value = str(img_h)

        meta = onnx_model.metadata_props.add()
        meta.key = "img_w"
        meta.value = str(img_w)

        onnx.save(onnx_model, str(output_path))
        print(f"  Metadata embedded: character({len(character)} chars), img_h={img_h}, img_w={img_w}")

        # Verify
        session = ort.InferenceSession(str(output_path))
        input_info = session.get_inputs()[0]
        output_info = session.get_outputs()[0]

        print(f"\nONNX model exported: {output_path}")
        print(f"  Input: {input_info.name} {input_info.shape}")
        print(f"  Output: {output_info.name} {output_info.shape}")

        # Test inference
        ort_inputs = {input_info.name: dummy_input.numpy()}
        ort_output = session.run(None, ort_inputs)[0]
        print(f"  Output shape: {ort_output.shape}")

        # Verify output matches
        with torch.no_grad():
            torch_output = model(dummy_input).numpy()

        if np.allclose(torch_output, ort_output, rtol=1e-4, atol=1e-4):
            print("  Verification: PASSED (PyTorch and ONNX outputs match)")
        else:
            print("  Verification: WARNING (outputs differ slightly)")

        print("\n" + "=" * 60)
        print("Export completed successfully!")
        print("=" * 60)

        return str(output_path)

    except Exception as e:
        print(f"Export failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
