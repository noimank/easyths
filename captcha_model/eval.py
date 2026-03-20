"""
Evaluation script for captcha recognition model.

Usage:
    # Evaluate with default model (outputs/best_model.pth)
    python -m captcha_model.eval --data_dir data/test

    # Evaluate ONNX model (auto-detected by suffix)
    python -m captcha_model.eval --model outputs/best_model.onnx --data_dir data/test

    # Use beam search decoding
    python -m captcha_model.eval --data_dir data/test --decode beam_search
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from captcha_model.utils import load_config, get_device, calculate_ctc_accuracy
from captcha_model.dataset import create_dataloader
from captcha_model.model import CaptchaRecognizer


def greedy_decode_ctc(probs: np.ndarray, blank: int = 0) -> List[int]:
    """Greedy CTC decoding."""
    best_path = np.argmax(probs, axis=1)
    decoded = []
    prev = blank
    for token in best_path:
        if token != blank and token != prev:
            decoded.append(int(token))
        prev = token
    return decoded


def evaluate_pytorch(
    model: CaptchaRecognizer,
    dataloader: torch.utils.data.DataLoader,
    device: torch.device,
    decode_method: str = "greedy",
) -> Tuple[float, float, Dict]:
    """Evaluate PyTorch model."""
    model.eval()

    all_predictions = []
    all_targets = []

    with torch.no_grad():
        iterator = tqdm(dataloader, desc="Evaluating")

        for images, targets, input_lengths, target_lengths in iterator:
            images = images.to(device)
            predictions = model.decode(images, blank=0, method=decode_method)

            target_list = []
            offset = 0
            for length in target_lengths:
                target_list.append(targets[offset:offset + length].tolist())
                offset += length

            all_predictions.extend(predictions)
            all_targets.extend(target_list)

            char_acc, seq_acc = calculate_ctc_accuracy(
                all_predictions[-len(target_list):], target_list
            )
            iterator.set_postfix({"char_acc": f"{char_acc:.4f}", "seq_acc": f"{seq_acc:.4f}"})

    return calculate_ctc_accuracy(all_predictions, all_targets)


def evaluate_onnx(
    ort_session,
    dataloader: torch.utils.data.DataLoader,
    idx_to_char: Dict[int, str],
    decode_method: str = "greedy",
) -> Tuple[float, float, Dict]:
    """Evaluate ONNX model."""
    all_predictions = []
    all_targets = []

    iterator = tqdm(dataloader, desc="Evaluating")

    for images, targets, input_lengths, target_lengths in iterator:
        images_np = images.numpy()

        # Run ONNX inference: output is (T, B, C)
        probs = ort_session.run(None, {"input": images_np})[0]
        # ONNX may have static or dynamic batch in the T dimension
        # Handle both: (T, B, C) with B>1 OR (T, 1, C) with B=1
        if probs.shape[1] == 1:
            probs = probs.squeeze(1)  # (T, C) for single sample
            probs = probs[None, ...]   # (1, T, C) for uniform loop
        else:
            probs = np.transpose(probs, (1, 0, 2))  # (B, T, C)

        # Decode each sample in batch
        predictions = []
        for i in range(probs.shape[0]):
            if decode_method == "beam_search":
                from captcha_model.ctc_decoder import beam_search_decode
                indices = beam_search_decode(probs[i], blank=0, beam_width=10)
            else:
                indices = greedy_decode_ctc(probs[i], blank=0)
            predictions.append(indices)

        target_list = []
        offset = 0
        for length in target_lengths:
            target_list.append(targets[offset:offset + length].tolist())
            offset += length

        all_predictions.extend(predictions)
        all_targets.extend(target_list)

        char_acc, seq_acc = calculate_ctc_accuracy(
            all_predictions[-len(target_list):], target_list
        )
        iterator.set_postfix({"char_acc": f"{char_acc:.4f}", "seq_acc": f"{seq_acc:.4f}"})

    return calculate_ctc_accuracy(all_predictions, all_targets)


def run_evaluation(
    model_path: str,
    config: Dict,
    data_dir: str,
    batch_size: int = None,
    decode_method: str = "greedy",
    verbose: bool = True,
) -> Tuple[float, float]:
    """Run evaluation on a dataset."""
    device = get_device()
    use_onnx = model_path.endswith(".onnx")

    if verbose:
        print(f"Using device: {device}")
        print(f"Model type: {'ONNX' if use_onnx else 'PyTorch'}")
        print(f"Loading model: {model_path}")

    if batch_size is not None:
        config["evaluation"]["batch_size"] = batch_size

    charset_size = len(config["charset"])
    idx_to_char = {idx + 1: char for idx, char in enumerate(config["charset"])}

    # Load model
    if use_onnx:
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError("ONNX runtime requires: pip install onnxruntime")
        ort_session = ort.InferenceSession(model_path)
        model = None
    else:
        checkpoint = torch.load(model_path, map_location=device, weights_only=False)

        if isinstance(checkpoint, dict):
            model_config = checkpoint.get("config", {}).get("model", config.get("model", {}))
        else:
            model_config = config.get("model", {})

        model = CaptchaRecognizer(
            charset_size=charset_size,
            dropout=model_config.get("dropout", 0.2),
            hidden_size=model_config.get("hidden_size", 384),
            num_tcn_layers=model_config.get("num_tcn_layers", 4),
        )

        model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))

        model.to(device)
        model.eval()
        ort_session = None

    # Create dataloader
    eval_loader = create_dataloader(data_dir, config, is_training=False)

    if verbose:
        print(f"Evaluating on: {data_dir}")
        print(f"Decode method: {decode_method}")

    # Run evaluation
    if use_onnx:
        char_acc, seq_acc = evaluate_onnx(ort_session, eval_loader, idx_to_char, decode_method)
    else:
        char_acc, seq_acc = evaluate_pytorch(model, eval_loader, device, decode_method)

    if verbose:
        print("\n" + "=" * 60)
        print("Evaluation Results")
        print("=" * 60)
        print(f"Total samples: {len(eval_loader.dataset)}")
        print(f"Decode method: {decode_method}")
        print("-" * 60)
        print(f"Character-level accuracy: {char_acc:.4f} ({char_acc * 100:.2f}%)")
        print(f"Sequence-level accuracy:  {seq_acc:.4f} ({seq_acc * 100:.2f}%)")
        print("=" * 60)

    return char_acc, seq_acc


def main():
    parser = argparse.ArgumentParser(description="Evaluate captcha recognition model")
    parser.add_argument(
        "--model",
        type=str,
        default="outputs/best_model.pth",
        help="Path to model file (.pth or .onnx), auto-detected by suffix",
    )
    parser.add_argument(
        "--data_dir",
        type=str,
        required=True,
        help="Path to evaluation data directory",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=None,
        help="Batch size for evaluation",
    )
    parser.add_argument(
        "--decode",
        type=str,
        default="greedy",
        choices=["greedy", "beam_search"],
        help="CTC decoding method",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    run_evaluation(
        args.model,
        config,
        data_dir=args.data_dir,
        batch_size=args.batch_size,
        decode_method=args.decode,
    )


if __name__ == "__main__":
    main()
