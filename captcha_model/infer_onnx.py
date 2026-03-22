"""
ONNX Inference Script for Captcha Recognition.

Usage:
    python infer_onnx.py                           # Run on test images
    python infer_onnx.py --image captcha.png       # Test single image
    python infer_onnx.py --dir data/test           # Test directory
    python infer_onnx.py --benchmark               # Run benchmark

Author: noimank (康康)
Email: noimank@163.com
"""
import argparse
import json
import time
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
import onnxruntime as ort
import yaml


def parse_args():
    parser = argparse.ArgumentParser(description="ONNX Captcha Recognition")

    parser.add_argument("--config", type=str, default="config.yaml",
                        help="Config file path")
    parser.add_argument("--model", type=str, default="onnx_model/captcha_ocr.onnx",
                        help="ONNX model path")
    parser.add_argument("--image", type=str, default=None,
                        help="Single image path")
    parser.add_argument("--dir", type=str, default=None,
                        help="Directory containing images")
    parser.add_argument("--output", type=str, default="outputs/onnx_infer",
                        help="Output directory")
    parser.add_argument("--providers", type=str, default="CPUExecutionProvider",
                        help="ONNX providers")
    parser.add_argument("--benchmark", action="store_true",
                        help="Run benchmark")
    parser.add_argument("--warmup", type=int, default=10,
                        help="Warmup iterations")
    parser.add_argument("--iterations", type=int, default=100,
                        help="Benchmark iterations")

    return parser.parse_args()


class ONNXCaptchaRecognizer:
    """ONNX-based captcha recognizer."""

    def __init__(self, model_path: str, config: dict):
        global_cfg = config.get('Global', {})

        self.character = global_cfg.get('character', "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
        self.img_h = global_cfg.get('img_h', 64)
        self.img_w = global_cfg.get('img_w', 256)
        self.blank = len(self.character)

        providers = [self._get_provider(config.get('providers', 'CPUExecutionProvider'))]
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name

        print(f"Loaded ONNX model: {model_path}")
        print(f"  Image size: {self.img_h}x{self.img_w}")
        print(f"  Character set: {self.character[:20]}... ({len(self.character)} chars)")

    def _get_provider(self, provider_str: str) -> str:
        if 'cuda' in provider_str.lower() or 'gpu' in provider_str.lower():
            return 'CUDAExecutionProvider'
        return 'CPUExecutionProvider'

    def recognize(self, image: np.ndarray) -> Tuple[str, float]:
        """Run inference on image."""
        input_tensor = self._preprocess(image)

        start = time.perf_counter()
        output = self.session.run(None, {self.input_name: input_tensor})[0]
        latency = (time.perf_counter() - start) * 1000

        pred_indices = output.argmax(axis=1)[0].tolist()
        text = self._ctc_decode(pred_indices)

        return text, latency

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            img = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

        img = cv2.resize(img, (self.img_w, self.img_h))
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
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


def run_benchmark(recognizer: ONNXCaptchaRecognizer, warmup: int, iterations: int):
    """Run benchmark."""
    print("\n" + "=" * 60)
    print("Benchmark Results")
    print("=" * 60)

    times = []
    for i in range(warmup + iterations):
        img = np.random.randint(0, 255, (recognizer.img_h, recognizer.img_w, 3), dtype=np.uint8)
        start = time.perf_counter()
        _, _ = recognizer.recognize(img)
        times.append((time.perf_counter() - start) * 1000)

    times = times[warmup:]
    avg_time = np.mean(times)
    std_time = np.std(times)

    print(f"Latency: {avg_time:.2f} ms (+/-{std_time:.2f})")
    print(f"FPS: {1000 / avg_time:.1f}")

    return {'avg_ms': avg_time, 'std_ms': std_time, 'fps': 1000 / avg_time}


def main():
    args = parse_args()

    # Load config
    with open(args.config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Update provider from args
    config['providers'] = args.providers

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("ONNX Captcha Recognition")
    print("=" * 60)

    # Load model
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        return

    recognizer = ONNXCaptchaRecognizer(str(model_path), config)

    # Benchmark mode
    if args.benchmark:
        results = run_benchmark(recognizer, args.warmup, args.iterations)
        json_path = output_dir / "benchmark_results.json"
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {json_path}")
        return

    # Prepare test images
    sources = []

    if args.image:
        img_path = Path(args.image)
        if img_path.exists():
            sources = [img_path]
    elif args.dir:
        input_dir = Path(args.dir)
        if input_dir.exists():
            exts = ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG']
            for ext in exts:
                sources.extend(input_dir.glob(ext))
    else:
        # Default test directory
        test_dir = Path("data/test")
        if test_dir.exists():
            exts = ['*.png', '*.jpg', '*.jpeg']
            for ext in exts:
                sources.extend(test_dir.glob(ext))

    if not sources:
        print("No test images found, running benchmark")
        run_benchmark(recognizer, args.warmup, args.iterations)
        return

    print(f"\nProcessing {len(sources)} images...")

    # Run inference
    results = []
    total_latency = 0.0

    for img_path in sources:
        img = cv2.imread(str(img_path))
        if img is None:
            continue

        text, latency = recognizer.recognize(img)
        total_latency += latency

        result = {
            'image': str(img_path),
            'prediction': text,
            'latency_ms': latency
        }
        results.append(result)

        print(f"  {img_path.name}: {text} ({latency:.2f}ms)")

    # Summary
    avg_latency = total_latency / len(results) if results else 0

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Processed: {len(results)} images")
    print(f"Average latency: {avg_latency:.2f} ms")
    print(f"FPS: {1000 / avg_latency:.1f}" if avg_latency > 0 else "")

    # Save results
    json_path = output_dir / "inference_results.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'model': str(model_path),
            'total_images': len(results),
            'avg_latency_ms': avg_latency,
            'results': results
        }, f, indent=2, ensure_ascii=False)

    print(f"Results saved to: {json_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
