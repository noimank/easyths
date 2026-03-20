"""
Captcha recognition model: CNN + TCN + CTC (No LSTM).

Architecture: VGG-style CNN backbone + Temporal Convolutional Network + CTC
Fully GPU-optimized, no LSTM, AMD 7900 XTX friendly.

Key design:
- VGG-style CNN: Efficient spatial feature extraction
- TCN: Parallelizable temporal modeling with dilated convolutions
- LayerNorm: Training stability (replaces BatchNorm for 1D)
- WeightNorm: Stabilizes gradient flow
- CTC: Sequence-level loss for variable-length output
"""

from typing import List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class ConvBNReLU(nn.Module):
    """Conv + BatchNorm + ReLU (2D)."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        stride: int = 1,
        padding: int = 1,
    ):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding, bias=False)
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.bn(self.conv(x)))


class TemporalBlock(nn.Module):
    """
    Temporal block with causal dilated convolution.
    Each block: Gated Conv1D (input gate + output gate).
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        stride: int = 1,
        dilation: int = 1,
        dropout: float = 0.1,
    ):
        super().__init__()
        padding = (kernel_size - 1) * dilation  # Causal padding

        # Gated convolution (similar to WaveNet)
        self.conv = nn.Conv1d(
            in_channels, out_channels * 2, kernel_size,
            stride=stride, padding=padding, dilation=dilation, bias=True
        )

        self.bn = nn.BatchNorm1d(out_channels * 2)
        self.dropout = nn.Dropout(dropout)

        # Residual connection
        if in_channels != out_channels:
            self.residual = nn.Conv1d(in_channels, out_channels, 1, bias=False)
        else:
            self.residual = nn.Identity()

        # Initialize gate bias to be slightly positive (encourages gating open at start)
        nn.init.constant_(self.conv.bias[out_channels:], 1.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, C, T)
        Returns:
            (B, C_out, T) - same temporal length
        """
        residual = self.residual(x)

        out = self.conv(x)
        out = self.bn(out)

        # Gated activation
        # conv outputs [B, 2*C, T], split into input and forget gates
        gates = torch.sigmoid(out[:, :out.size(1) // 2, :])
        signals = torch.tanh(out[:, out.size(1) // 2:, :])

        out = gates * signals
        out = self.dropout(out)

        # Trim to original length (remove right-side padding from causal conv)
        if out.size(2) > residual.size(2):
            out = out[:, :, :residual.size(2)]

        return F.relu(out + residual)


class TCNStack(nn.Module):
    """Stack of temporal blocks with increasing dilation."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        num_layers: int = 4,
        kernel_size: int = 3,
        dropout: float = 0.1,
    ):
        super().__init__()
        layers = []
        for i in range(num_layers):
            dilation = 2 ** i
            layers.append(
                TemporalBlock(
                    in_channels if i == 0 else out_channels,
                    out_channels,
                    kernel_size=kernel_size,
                    dilation=dilation,
                    dropout=dropout,
                )
            )
        self.blocks = nn.ModuleList(layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward through all TCN blocks."""
        for block in self.blocks:
            x = block(x)
        return x


class CaptchaRecognizer(nn.Module):
    """
    CNN + TCN captcha recognizer.

    Architecture:
    - CNN backbone (VGG-style, 8x width downsampling)
    - TCN stack (4 dilated conv layers)
    - Linear classifier + log_softmax

    GPU-optimized, no LSTM.
    """

    def __init__(
        self,
        charset_size: int,
        dropout: float = 0.2,
        hidden_size: int = 384,
        num_tcn_layers: int = 4,
        kernel_size: int = 3,
    ):
        super().__init__()

        self.charset_size = charset_size
        self.num_classes = charset_size + 1  # +1 for CTC blank
        self.hidden_size = hidden_size

        # CNN backbone: 8x downsampling
        self.backbone = self._build_backbone()

        # Project CNN features -> TCN hidden
        self.proj = nn.Sequential(
            nn.Conv2d(self.backbone.out_channels, hidden_size, 1, bias=False),
            nn.BatchNorm2d(hidden_size),
            nn.ReLU(inplace=True),
        )

        # TCN for sequence modeling
        self.tcn = TCNStack(
            in_channels=hidden_size,
            out_channels=hidden_size,
            num_layers=num_tcn_layers,
            kernel_size=kernel_size,
            dropout=dropout,
        )

        # Final normalization
        self.final_norm = nn.LayerNorm(hidden_size)

        # Classifier
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Conv1d(hidden_size, hidden_size, 1, bias=True),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Conv1d(hidden_size, self.num_classes, 1, bias=True),
        )

        self._init_weights()

    def _build_backbone(self) -> nn.Module:
        """Build VGG-style backbone with 8x downsampling."""
        class Backbone(nn.Module):
            def __init__(self):
                super().__init__()
                # 3 -> 64, stride 2
                self.conv1 = nn.Sequential(
                    ConvBNReLU(3, 64, 3, 2, 1),   # H/2, W/2
                    ConvBNReLU(64, 64, 3, 1, 1),
                )
                # 64 -> 128, stride 2
                self.conv2 = nn.Sequential(
                    ConvBNReLU(64, 128, 3, 2, 1),  # H/4, W/4
                    ConvBNReLU(128, 128, 3, 1, 1),
                )
                # 128 -> 256, stride 2
                self.conv3 = nn.Sequential(
                    ConvBNReLU(128, 256, 3, 2, 1),  # H/8, W/8
                    ConvBNReLU(256, 256, 3, 1, 1),
                    ConvBNReLU(256, 256, 3, 1, 1),
                )
                # 256 -> 512, spatial pool
                self.conv4 = nn.Sequential(
                    ConvBNReLU(256, 512, 3, 1, 1),
                    ConvBNReLU(512, 512, 3, 1, 1),
                    nn.BatchNorm2d(512),
                    nn.ReLU(inplace=True),
                    nn.AdaptiveAvgPool2d((1, None)),  # H -> 1
                )
                self.out_channels = 512

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                x = self.conv1(x)
                x = self.conv2(x)
                x = self.conv3(x)
                x = self.conv4(x)
                return x

        return Backbone()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, (nn.Conv2d, nn.Conv1d)):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, (nn.BatchNorm2d, nn.BatchNorm1d)):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.LayerNorm):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, 3, H, W) input images
        Returns:
            (T, B, num_classes) log probabilities for CTC
        """
        # CNN: (B, 3, H, W) -> (B, 512, 1, W/8)
        conv = self.backbone(x)
        b, c, h, _ = conv.size()
        assert h == 1, f"Expected H=1, got H={h}"

        # Project: (B, 512, 1, W/8) -> (B, hidden, 1, W/8)
        conv = self.proj(conv)

        # TCN input: (B, hidden, W/8)
        seq = conv.squeeze(2)

        # TCN: (B, hidden, W/8) -> (B, hidden, W/8)
        seq = self.tcn(seq)

        # LayerNorm: (B, hidden, W/8) -> (B, W/8, hidden)
        seq = seq.permute(0, 2, 1)  # (B, T, C)
        seq = self.final_norm(seq)

        # Back to (B, hidden, T) for conv classifier
        seq = seq.permute(0, 2, 1)  # (B, C, T)

        # Classify: (B, hidden, T) -> (B, num_classes, T)
        logits = self.classifier(seq)

        # log_softmax over classes, CTC expects (T, B, C)
        log_probs = F.log_softmax(logits, dim=1).permute(2, 0, 1)

        return log_probs

    def decode(self, x: torch.Tensor, blank: int = 0, method: str = "greedy") -> List[List[int]]:
        """Decode images to character sequences."""
        self.eval()
        with torch.no_grad():
            output = self.forward(x)
            if method == "greedy":
                return self._greedy_decode(output, blank)
            elif method == "beam_search":
                return self._beam_search_decode(output, blank)
            else:
                raise ValueError(f"Unknown decode method: {method}")

    def _greedy_decode(self, output: torch.Tensor, blank: int) -> List[List[int]]:
        """Greedy CTC decoding."""
        best_paths = output.argmax(dim=2).T  # (B, T)
        results = []
        for path in best_paths:
            collapsed = []
            prev = None
            for token in path.tolist():
                if token != prev:
                    if token != blank:
                        collapsed.append(token)
                    prev = token
            results.append(collapsed)
        return results

    def _beam_search_decode(
        self, output: torch.Tensor, blank: int, beam_width: int = 10
    ) -> List[List[int]]:
        """Beam search CTC decoding."""
        from captcha_model.ctc_decoder import beam_search_decode_batch
        probs = torch.exp(output)
        probs = probs.permute(1, 0, 2)  # (B, T, C)
        return beam_search_decode_batch(probs.cpu().numpy(), blank, beam_width)


class CTCLoss(nn.Module):
    """CTC Loss wrapper."""

    def __init__(
        self,
        blank: int = 0,
        reduction: str = "mean",
        zero_infinity: bool = True,
    ):
        super().__init__()
        self.criterion = nn.CTCLoss(
            blank=blank, reduction=reduction, zero_infinity=zero_infinity
        )

    def forward(self, outputs, targets, input_lengths, target_lengths):
        return self.criterion(outputs, targets, input_lengths, target_lengths)


def load_model(
    model_path: str,
    charset_size: int,
    device: Optional[torch.device] = None,
    **kwargs
) -> CaptchaRecognizer:
    """Load trained model from checkpoint."""
    if device is None:
        from captcha_model.utils import get_device
        device = get_device()

    model = CaptchaRecognizer(charset_size=charset_size, **kwargs)
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model


def count_parameters(model: nn.Module) -> int:
    """Count trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    model = CaptchaRecognizer(charset_size=62, hidden_size=384, num_tcn_layers=4)
    print(f"Parameters: {count_parameters(model):,}")

    x = torch.randn(2, 3, 64, 160)
    out = model(x)
    print(f"Input: {x.shape} -> Output: {out.shape}")
    print(f"Sequence length: {out.shape[0]} (expected: 160/8 = 20)")
    print(f"Classes: {out.shape[2]} (expected: 63)")

    # Test CTC loss
    criterion = CTCLoss(blank=0)
    targets = torch.tensor([1, 2, 3, 4, 5, 6])
    input_lengths = torch.tensor([20, 20])
    target_lengths = torch.tensor([3, 3])
    loss = criterion(out, targets, input_lengths, target_lengths)
    print(f"CTC loss: {loss.item():.4f}")

    # Test backward
    loss.backward()
    print("Backward: OK")

    # Timing test
    import time
    model = CaptchaRecognizer(charset_size=62, hidden_size=384)
    x = torch.randn(32, 3, 64, 160)
    model.eval()
    with torch.no_grad():
        for _ in range(5):
            _ = model(x)
    t0 = time.time()
    with torch.no_grad():
        for _ in range(100):
            _ = model(x)
    print(f"Inference: {100 * (time.time() - t0) / 100 * 1000:.1f}ms/image")
