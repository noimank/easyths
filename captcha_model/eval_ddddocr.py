"""
ddddocr Captcha Recognition Evaluation Script.

Evaluate ddddocr library performance on captcha datasets.

Usage:
    python eval_ddddocr.py                          # Use default test directory
    python eval_ddddocr.py --test_dir data/test     # Use specific test directory
    python eval_ddddocr.py --show_adsl --test_dir data/test  # Enable advertising

Author: noimank (康康)
Email: noimank@163.com
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import ddddocr
from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(description="ddddocr Captcha Recognition Evaluation")

    parser.add_argument("--test_dir", type=str, default="data/test",
                        help="Test directory containing captcha images")
    parser.add_argument("--output", type=str, default="outputs/eval_ddddocr",
                        help="Output directory for results")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of samples to evaluate")

    return parser.parse_args()


def extract_label_from_filename(filename: str) -> str:
    """Extract ground truth label from filename.

    Expected format: <label>_<uuid>.png
    Example: 24Nh_69c29135-e572-4f91-942d-b43d41777366.png -> 24Nh
    """
    name = Path(filename).stem
    # Split on first underscore, label is before it
    parts = name.split('_', 1)
    return parts[0]


def evaluate_dataset(ocr, test_dir: str, limit: int = None):
    """Evaluate ddddocr on dataset."""
    total_chars = 0
    correct_chars = 0
    correct_seqs = 0
    total_samples = 0
    total_latency = 0.0
    errors = []

    # Get all image files
    image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}
    image_files = []
    for f in os.listdir(test_dir):
        if Path(f).suffix.lower() in image_extensions:
            image_files.append(f)

    if limit:
        image_files = image_files[:limit]

    if not image_files:
        print(f"No image files found in {test_dir}")
        return None

    print(f"Found {len(image_files)} images to evaluate")

    for i, filename in enumerate(image_files):
        filepath = os.path.join(test_dir, filename)
        ground_truth = extract_label_from_filename(filename)

        # Read image
        with open(filepath, 'rb') as f:
            image_bytes = f.read()

        # Measure inference time
        start = time.perf_counter()
        prediction = ocr.classification(image_bytes)
        latency = (time.perf_counter() - start) * 1000
        total_latency += latency

        # Calculate metrics
        total_samples += 1
        total_chars += len(ground_truth)

        # Character-level accuracy
        min_len = min(len(prediction), len(ground_truth))
        for j in range(min_len):
            if prediction[j] == ground_truth[j]:
                correct_chars += 1

        # Sequence-level accuracy
        if prediction == ground_truth:
            correct_seqs += 1
        else:
            errors.append({
                'prediction': prediction,
                'ground_truth': ground_truth
            })

        # Progress indicator
        if (i + 1) % 100 == 0 or (i + 1) == len(image_files):
            print(f"  Processed: {i + 1}/{len(image_files)}")

    char_acc = correct_chars / max(total_chars, 1)
    seq_acc = correct_seqs / max(total_samples, 1)
    avg_latency = total_latency / max(total_samples, 1)

    return {
        'char_acc': char_acc,
        'seq_acc': seq_acc,
        'avg_latency_ms': avg_latency,
        'total_samples': total_samples,
        'correct_samples': correct_seqs,
        'total_chars': total_chars,
        'correct_chars': correct_chars,
        'errors': errors
    }


def main():
    args = parse_args()

    # Check test directory
    if not os.path.exists(args.test_dir):
        print(f"Test directory not found: {args.test_dir}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("ddddocr Captcha Recognition Evaluation")
    print("=" * 60)
    print(f"Test directory: {args.test_dir}")
    print(f"Output directory: {args.output}")
    if args.limit:
        print(f"Sample limit: {args.limit}")
    print("=" * 60 + "\n")

    # Initialize ddddocr
    print("Initializing ddddocr...")
    init_start = time.perf_counter()

    ocr = ddddocr.DdddOcr(
        show_ad=False,
        # beta=True
    )

    init_time = time.perf_counter() - init_start
    print(f"ddddocr initialized in {init_time:.2f}s")

    # Evaluate
    print("\nEvaluating...")
    start_time = datetime.now()
    results = evaluate_dataset(ocr, args.test_dir, args.limit)
    eval_time = (datetime.now() - start_time).total_seconds()

    if results is None:
        print("Evaluation failed: no valid samples")
        sys.exit(1)

    # Print results
    print("\n" + "=" * 60)
    print("Evaluation Results")
    print("=" * 60)
    print(f"Total samples: {results['total_samples']}")
    print(f"Correct samples: {results['correct_samples']}")
    print(f"Total characters: {results['total_chars']}")
    print(f"Correct characters: {results['correct_chars']}")
    print(f"Character accuracy: {results['char_acc']:.4f} ({results['char_acc'] * 100:.2f}%)")
    print(f"Sequence accuracy: {results['seq_acc']:.4f} ({results['seq_acc'] * 100:.2f}%)")
    print(f"Average latency: {results['avg_latency_ms']:.2f} ms")
    print(f"Throughput: {results['total_samples'] / max(eval_time, 0.001):.2f} samples/s")
    print(f"Evaluation time: {eval_time:.2f} s")
    print(f"Init time: {init_time:.2f} s")
    print("=" * 60)

    # Print errors
    if results['errors']:
        print(f"\nErrors ({len(results['errors'])} samples):")
        print("-" * 60)
        for err in results['errors'][:20]:
            print(f"  GT: '{err['ground_truth']}' -> Pred: '{err['prediction']}'")
        if len(results['errors']) > 20:
            print(f"  ... and {len(results['errors']) - 20} more errors")

    # Save results
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "eval_ddddocr_results.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'library': 'ddddocr',
            'test_dir': str(args.test_dir),
            'total_samples': results['total_samples'],
            'correct_samples': results['correct_samples'],
            'total_chars': results['total_chars'],
            'correct_chars': results['correct_chars'],
            'char_acc': results['char_acc'],
            'seq_acc': results['seq_acc'],
            'avg_latency_ms': results['avg_latency_ms'],
            'throughput': results['total_samples'] / max(eval_time, 0.001),
            'init_time_s': init_time,
            'eval_time_s': eval_time,
            'timestamp': datetime.now().isoformat(),
            'errors': results['errors']
        }, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {results_path}")

    return results


if __name__ == "__main__":
    main()
