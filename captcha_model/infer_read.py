"""
Captcha Recognition Inference Script.

Usage:
    python infer_read.py                           # Run on test directory
    python infer_read.py --image captcha.png       # Test single image
    python infer_read.py --dir data/test           # Test directory

Author: noimank (康康)
Email: noimank@163.com
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml
from tqdm import tqdm

from models.resnet_ocr import ResNetOCR


def parse_args():
    parser = argparse.ArgumentParser(description="Captcha Recognition Inference")

    parser.add_argument("--config", type=str, default="config.yaml",
                        help="Config file path")
    parser.add_argument("--model", type=str, default="outputs/best_model.pt",
                        help="Model path (.pt)")
    parser.add_argument("--image", type=str, default=None,
                        help="Single image path")
    parser.add_argument("--dir", type=str, default=None,
                        help="Directory containing images")
    parser.add_argument("--output", type=str, default="outputs/infer",
                        help="Output directory")
    parser.add_argument("--device", type=str, default="cuda",
                        help="Device (cuda, cpu)")

    return parser.parse_args()


def load_config(config_path: str) -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def preprocess_image(img_path: str, img_h: int, img_w: int) -> torch.Tensor:
    """Load and preprocess image."""
    img = cv2.imread(img_path, cv2.IMREAD_COLOR)
    if img is None:
        return None

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (img_w, img_h))
    img = img.astype(np.float32) / 255.0
    img = np.transpose(img, (2, 0, 1))
    img = torch.from_numpy(img).float()
    img = img.unsqueeze(0)

    return img


def ctc_decode(pred_indices: list, character: str, blank: int) -> str:
    """CTC greedy decoding."""
    result = []
    prev = -1
    for idx in pred_indices:
        idx_int = int(idx)
        if idx_int != prev and idx_int != blank:
            if idx_int < len(character):
                result.append(character[idx_int])
        prev = idx_int
    return ''.join(result)


def main():
    args = parse_args()

    # Load config
    config = load_config(args.config)
    global_cfg = config.get('Global', {})

    character = global_cfg.get('character', "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    img_h = global_cfg.get('img_h', 64)
    img_w = global_cfg.get('img_w', 256)
    num_classes = len(character) + 1
    blank_idx = num_classes - 1

    # Set device
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load model
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        sys.exit(1)

    print(f"Loading model: {model_path}")

    model = ResNetOCR(
        img_h=img_h,
        img_w=img_w,
        num_classes=num_classes,
        character=character
    ).to(device)

    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    # Prepare input sources
    sources = []

    if args.image:
        img_path = Path(args.image)
        if img_path.exists():
            sources = [img_path]
        else:
            print(f"Image not found: {args.image}")
            sys.exit(1)
    elif args.dir:
        input_dir = Path(args.dir)
        if input_dir.exists():
            exts = ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']
            sources = []
            for ext in exts:
                sources.extend(input_dir.glob(ext))
        else:
            print(f"Directory not found: {args.dir}")
            sys.exit(1)
    else:
        # Default test directory
        test_dir = Path("data/test")
        if test_dir.exists():
            exts = ['*.png', '*.jpg', '*.jpeg']
            for ext in exts:
                sources.extend(test_dir.glob(ext))
            print(f"Using default test directory: {test_dir}")
        else:
            print("No test directory found. Please specify --image or --dir")
            sys.exit(1)

    if not sources:
        print("No images found")
        sys.exit(1)

    print(f"Found {len(sources)} images")

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process images
    results = []

    for img_path in tqdm(sources, desc="Recognizing"):
        img_tensor = preprocess_image(str(img_path), img_h, img_w)
        if img_tensor is None:
            print(f"Failed to load: {img_path}")
            continue

        img_tensor = img_tensor.to(device)

        start = time.perf_counter()
        with torch.no_grad():
            logits = model(img_tensor)
        latency = (time.perf_counter() - start) * 1000

        # Decode
        pred_indices = logits.argmax(dim=1)[0].cpu().tolist()
        text = ctc_decode(pred_indices, character, blank_idx)

        result = {
            'image': str(img_path),
            'prediction': text,
            'latency_ms': latency
        }
        results.append(result)

        print(f"  {img_path.name}: {text} ({latency:.2f}ms)")

    # Calculate statistics
    total_latency = sum(r['latency_ms'] for r in results)
    avg_latency = total_latency / len(results) if results else 0

    print(f"\nInference completed!")
    print(f"  Total images: {len(results)}")
    print(f"  Average latency: {avg_latency:.2f} ms")

    # Save results
    json_path = output_dir / "recognition_results.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'model': str(model_path),
            'total_images': len(results),
            'avg_latency_ms': avg_latency,
            'results': results
        }, f, indent=2, ensure_ascii=False)

    print(f"  Results saved to: {json_path}")

    return results


if __name__ == "__main__":
    main()
