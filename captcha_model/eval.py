"""
Captcha Recognition Evaluation Script.

Usage:
    python eval.py                          # Use default config
    python eval.py --model path/to/model.pt  # Use specific model
    python eval.py --test_dir data/test     # Use specific test directory

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

import torch
import yaml

from models.resnet_ocr import ResNetOCR
from models.loss import CaptchaDataset


def parse_args():
    parser = argparse.ArgumentParser(description="Captcha Recognition Evaluation")

    parser.add_argument("--config", type=str, default="config.yaml",
                        help="Config file path")
    parser.add_argument("--model", type=str, default="outputs/best_model.pt",
                        help="Model path (.pt)")
    parser.add_argument("--test_dir", type=str, default=None,
                        help="Test directory (overrides config)")
    parser.add_argument("--output", type=str, default="outputs/eval",
                        help="Output directory")
    parser.add_argument("--device", type=str, default="cuda",
                        help="Device (cuda, cpu)")
    parser.add_argument("--batch_size", type=int, default=32,
                        help="Batch size for evaluation")

    return parser.parse_args()


def load_config(config_path: str) -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def collate_fn(batch):
    """Custom collate function."""
    images = torch.stack([item[0] for item in batch], dim=0)
    max_label_len = max(item[1].shape[0] for item in batch)
    labels = torch.zeros(len(batch), max_label_len, dtype=torch.long)
    label_lengths = torch.zeros(len(batch), dtype=torch.long)

    for i, (img, label, length) in enumerate(batch):
        labels[i, :length] = label
        label_lengths[i] = length

    return images, labels, label_lengths


def ctc_greedy_decode(logits: torch.Tensor, blank: int) -> list:
    """Greedy decode CTC predictions."""
    predictions = logits.argmax(dim=1).cpu().numpy()
    results = []

    for pred in predictions:
        result = []
        prev = -1
        for idx in pred:
            idx_int = int(idx)
            if idx_int != prev and idx_int != blank:
                result.append(idx_int)
            prev = idx_int
        results.append(result)

    return results


def evaluate_dataset(model, dataloader, device, character, num_classes):
    """Evaluate model on dataset."""
    model.eval()

    total_chars = 0
    correct_chars = 0
    correct_seqs = 0
    total_samples = 0
    total_latency = 0.0
    errors = []
    blank_idx = num_classes - 1

    with torch.no_grad():
        for batch in dataloader:
            images = batch[0].to(device)
            labels = batch[1].to(device)
            label_lengths = batch[2].to(device)

            batch_size = images.shape[0]

            start = time.perf_counter()
            logits = model(images)
            latency = (time.perf_counter() - start) * 1000
            total_latency += latency

            preds = ctc_greedy_decode(logits, blank_idx)

            for i in range(batch_size):
                pred = preds[i]
                label_len = label_lengths[i].item()
                label_indices = labels[i, :label_len].cpu().tolist()
                label_str = ''.join([character[idx] for idx in label_indices])
                pred_str = ''.join([character[idx] for idx in pred if idx < len(character)])

                total_samples += 1
                total_chars += len(label_str)

                for p_char, l_char in zip(pred_str, label_str):
                    if p_char == l_char:
                        correct_chars += 1

                if pred_str == label_str:
                    correct_seqs += 1
                else:
                    errors.append({
                        'prediction': pred_str,
                        'ground_truth': label_str
                    })

    char_acc = correct_chars / max(total_chars, 1)
    seq_acc = correct_seqs / max(total_samples, 1)
    avg_latency = total_latency / max(total_samples, 1)

    return {
        'char_acc': char_acc,
        'seq_acc': seq_acc,
        'avg_latency_ms': avg_latency,
        'total_samples': total_samples,
        'correct_samples': correct_seqs,
        'errors': errors
    }


def main():
    args = parse_args()

    # Load config
    config = load_config(args.config)
    global_cfg = config.get('Global', {})
    eval_cfg = config.get('Eval', {})

    character = global_cfg.get('character', "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    img_h = global_cfg.get('img_h', 64)
    img_w = global_cfg.get('img_w', 256)
    num_classes = len(character) + 1

    test_dir = args.test_dir or eval_cfg.get('test_dir', 'data/test')

    # Set device
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    print("\n" + "=" * 60)
    print("Captcha Recognition Evaluation")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Test dir: {test_dir}")
    print(f"Image size: {img_h}x{img_w}")
    print(f"Character set: {character[:20]}... ({len(character)} chars)")
    print("=" * 60 + "\n")

    # Check paths
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        sys.exit(1)

    if not os.path.exists(test_dir):
        print(f"Test directory not found: {test_dir}")
        sys.exit(1)

    # Build model
    model = ResNetOCR(
        img_h=img_h,
        img_w=img_w,
        num_classes=num_classes,
        character=character
    ).to(device)

    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    print(f"Model loaded: {model_path}")

    # Build dataset
    test_dataset = CaptchaDataset(
        data_dir=test_dir,
        img_h=img_h,
        img_w=img_w,
        character=character,
        augment=False
    )
    test_dataset.training = False

    print(f"Test samples: {len(test_dataset)}")

    # Build dataloader
    from torch.utils.data import DataLoader
    test_loader = DataLoader(
        test_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        collate_fn=collate_fn
    )

    # Evaluate
    print("\nEvaluating...")
    start_time = datetime.now()
    results = evaluate_dataset(model, test_loader, device, character, num_classes)
    eval_time = (datetime.now() - start_time).total_seconds()

    # Print results
    print("\n" + "=" * 60)
    print("Evaluation Results")
    print("=" * 60)
    print(f"Total samples: {results['total_samples']}")
    print(f"Correct samples: {results['correct_samples']}")
    print(f"Character accuracy: {results['char_acc']:.4f} ({results['char_acc'] * 100:.2f}%)")
    print(f"Sequence accuracy: {results['seq_acc']:.4f} ({results['seq_acc'] * 100:.2f}%)")
    print(f"Average latency: {results['avg_latency_ms']:.2f} ms")
    print(f"Evaluation time: {eval_time:.2f} s")
    print("=" * 60)

    # Print errors
    if results['errors']:
        print(f"\nErrors ({len(results['errors'])} samples):")
        print("-" * 60)
        for i, err in enumerate(results['errors'][:20]):
            print(f"  GT: '{err['ground_truth']}' -> Pred: '{err['prediction']}'")
        if len(results['errors']) > 20:
            print(f"  ... and {len(results['errors']) - 20} more errors")

    # Save results
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "eval_results.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'model': str(model_path),
            'test_dir': str(test_dir),
            'img_size': [img_h, img_w],
            'character': character,
            'total_samples': results['total_samples'],
            'correct_samples': results['correct_samples'],
            'char_acc': results['char_acc'],
            'seq_acc': results['seq_acc'],
            'avg_latency_ms': results['avg_latency_ms'],
            'eval_time_s': eval_time,
            'timestamp': datetime.now().isoformat(),
            'errors': results['errors']
        }, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {results_path}")

    return results


if __name__ == "__main__":
    main()
