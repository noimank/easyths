"""
Standalone captcha recognition inference using only ONNX model.

All configuration (charset, input size, normalization) is embedded
directly in the ONNX model's metadata — no config file needed.

Usage:
    python -m captcha_model.onnx_infer model.onnx captcha.png

    # Or import directly:
    from captcha_model.onnx_infer import CaptchaRecognizer
    model = CaptchaRecognizer("model.onnx")
    text = model.predict("captcha.png")
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image


class CaptchaRecognizer:
    """
    Self-contained captcha recognizer — loads everything from ONNX metadata.

    Requires only:
        - onnxruntime
        - numpy
        - Pillow
    """

    def __init__(self, model_path: str, decode_method: str = "greedy", beam_width: int = 10):
        """
        Args:
            model_path: Path to ONNX model file (with embedded metadata).
            decode_method: CTC decoding method, "greedy" or "beam_search".
            beam_width: Beam width for beam search decoding.
        """
        self.model_path = model_path
        self.decode_method = decode_method
        self.beam_width = beam_width

        self._load_metadata()
        self._init_session()

    def _load_metadata(self) -> None:
        """Extract all configuration from ONNX model metadata."""
        import onnxruntime as ort
        from onnx import load as load_onnx

        onnx_model = load_onnx(self.model_path)
        meta = onnx_model.metadata_props
        m = {entry.key: entry.value for entry in meta}

        self.charset: str = m["charset"]
        self.input_height: int = int(m["input_height"])
        self.input_width: int = int(m["input_width"])
        self.channels: int = int(m["channels"])
        self.downsampling: int = int(m.get("downsampling", "8"))
        self.seq_len: int = self.input_width // self.downsampling

        # Normalization params
        self.mean: List[float] = json.loads(m.get("mean", "[0.485, 0.456, 0.406]"))
        self.std: List[float] = json.loads(m.get("std", "[0.229, 0.224, 0.225]"))

        # Character mapping
        self.charset_size = len(self.charset)
        self.idx_to_char = {idx + 1: char for idx, char in enumerate(self.charset)}
        self.idx_to_char[0] = ""  # CTC blank token

        self.num_classes = self.charset_size + 1  # +1 for CTC blank

    def _init_session(self) -> None:
        """Initialize ONNX Runtime session."""
        import onnxruntime as ort

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(self.model_path, sess_options)

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        """Preprocess image for model input."""
        if self.channels == 1:
            image = image.convert("L")
        else:
            image = image.convert("RGB")

        image = image.resize((self.input_width, self.input_height), Image.Resampling.BILINEAR)
        image_array = np.array(image, dtype=np.float32) / 255.0

        if self.channels == 3:
            mean = np.array(self.mean, dtype=np.float32)
            std = np.array(self.std, dtype=np.float32)
            image_array = (image_array - mean) / std
            image_array = np.transpose(image_array, (2, 0, 1))
        else:
            image_array = np.expand_dims(image_array, 0)

        return image_array

    def _greedy_decode(self, probs: np.ndarray) -> List[int]:
        """Greedy CTC decoding."""
        best_path = np.argmax(probs, axis=1)
        decoded = []
        prev = 0
        for token in best_path:
            if token != 0 and token != prev:
                decoded.append(token)
            prev = token
        return decoded

    def _beam_search_decode(self, probs: np.ndarray) -> List[int]:
        """Beam search CTC decoding with log-space computation."""
        import math

        seq_len, num_classes = probs.shape
        log_probs = np.log(probs + 1e-10)
        NEG_INF = float("-inf")

        def logsumexp(a: float, b: float) -> float:
            if a == NEG_INF:
                return b
            if b == NEG_INF:
                return a
            max_val = max(a, b)
            return max_val + math.log(1.0 + math.exp(min(a, b) - max_val))

        beam: Dict[Tuple, Tuple[float, float]] = {(): (0.0, NEG_INF)}

        for t in range(seq_len):
            new_beam: Dict[Tuple, Tuple[float, float]] = {}

            for prefix, (lp_blank, lp_non_blank) in beam.items():
                lp_b = log_probs[t, 0]
                new_lp_blank = logsumexp(lp_blank, lp_non_blank) + lp_b
                if prefix in new_beam:
                    old_lp_blank, old_lp_non_blank = new_beam[prefix]
                    new_beam[prefix] = (logsumexp(old_lp_blank, new_lp_blank), old_lp_non_blank)
                else:
                    new_beam[prefix] = (new_lp_blank, NEG_INF)

                for c in range(1, num_classes):
                    lp_c = log_probs[t, c]
                    if len(prefix) > 0 and prefix[-1] == c:
                        new_lp_non_blank = lp_blank + lp_c
                    else:
                        new_lp_non_blank = logsumexp(lp_blank, lp_non_blank) + lp_c

                    new_prefix = prefix + (c,)
                    if new_prefix in new_beam:
                        old_lp_blank, old_lp_non_blank = new_beam[new_prefix]
                        new_beam[new_prefix] = (
                            old_lp_blank,
                            logsumexp(old_lp_non_blank, new_lp_non_blank),
                        )
                    else:
                        new_beam[new_prefix] = (NEG_INF, new_lp_non_blank)

            sorted_beam = sorted(
                new_beam.items(),
                key=lambda x: logsumexp(x[1][0], x[1][1]),
                reverse=True,
            )[: self.beam_width]
            beam = {k: v for k, v in sorted_beam}

        best_prefix = max(beam.keys(), key=lambda x: logsumexp(beam[x][0], beam[x][1]))
        return list(best_prefix)

    def _decode(self, probs: np.ndarray) -> str:
        """Decode probability matrix to text."""
        if self.decode_method == "beam_search":
            indices = self._beam_search_decode(probs)
        else:
            indices = self._greedy_decode(probs)
        return "".join(self.idx_to_char[idx] for idx in indices if idx in self.idx_to_char)

    def predict(
        self,
        image_path: Union[str, "Image.Image"],
        return_confidence: bool = False,
    ) -> Union[str, Tuple[str, List[float]]]:
        """
        Recognize captcha text from an image.

        Args:
            image_path: Path to image file or PIL Image object.
            return_confidence: If True, return (text, per_char_confidences).

        Returns:
            Predicted text, or (text, confidences) if return_confidence=True.
        """
        if isinstance(image_path, Image.Image):
            image = image_path
        else:
            image = Image.open(image_path)

        img_array = self._preprocess(image)
        img_array = np.expand_dims(img_array, 0)  # Add batch dim

        probs: np.ndarray = self.session.run(None, {"input": img_array})[0]
        probs = probs.squeeze(1)  # (seq_len, num_classes)

        text = self._decode(probs)

        if return_confidence:
            confidences = self._get_confidences(probs, text)
            return text, confidences

        return text

    def _get_confidences(self, probs: np.ndarray, text: str) -> List[float]:
        """Calculate per-character confidence scores."""
        best_path = np.argmax(probs, axis=1)
        confidences = []
        prev = 0
        char_idx = 0

        for t, token in enumerate(best_path):
            if token != 0 and token != prev:
                if char_idx < len(text):
                    char = text[char_idx]
                    expected_idx = self.charset.index(char) + 1 if char in self.charset else 0
                    if token == expected_idx:
                        confidences.append(float(probs[t, token]))
                    else:
                        confidences.append(float(probs[t, token]))
                    char_idx += 1
            prev = token

        return confidences

    def predict_batch(
        self,
        image_paths: List[Union[str, "Image.Image"]],
        return_confidence: bool = False,
    ) -> List[Union[str, Tuple[str, List[float]]]]:
        """Recognize captcha text from multiple images."""
        return [self.predict(p, return_confidence) for p in image_paths]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Standalone ONNX captcha recognition")
    parser.add_argument("model", type=str, help="Path to ONNX model file")
    parser.add_argument("images", type=str, nargs="+", help="Path(s) to captcha image(s)")
    parser.add_argument(
        "--decode",
        type=str,
        default="greedy",
        choices=["greedy", "beam_search"],
        help="CTC decoding method",
    )
    parser.add_argument(
        "--show_confidence",
        action="store_true",
        help="Show per-character confidence scores",
    )
    args = parser.parse_args()

    print(f"Loading model: {args.model}")
    recognizer = CaptchaRecognizer(args.model, decode_method=args.decode)
    print(f"  charset:    {recognizer.charset}")
    print(f"  input size: {recognizer.input_width}x{recognizer.input_height}")
    print(f"  classes:    {recognizer.num_classes} (including blank)")
    print()

    for image_path in args.images:
        if not Path(image_path).exists():
            print(f"[ERROR] Image not found: {image_path}")
            continue

        if args.show_confidence:
            text, confidences = recognizer.predict(image_path, return_confidence=True)
            print(f"Image: {image_path}")
            print(f"  Prediction: {text}")
            if confidences:
                print("  Confidence per character:")
                for i, (char, conf) in enumerate(zip(text, confidences)):
                    print(f"    [{i}] '{char}' = {conf:.4f}")
            print()
        else:
            text = recognizer.predict(image_path)
            print(f"{Path(image_path).name}: {text}")


if __name__ == "__main__":
    main()
