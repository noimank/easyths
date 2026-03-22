"""
ResNet-based OCR Model for Captcha Recognition.

A lightweight OCR model using ResNet34 as backbone with:
- ECA attention in backbone
- Spatial attention pooling for sequence encoding
- Improved CTC head with residual connection

Author: noimank (康康)
Email: noimank@163.com
"""

from math import cos, pi

import torch
import torch.nn as nn
from torch.optim.lr_scheduler import LRScheduler


class ResNetOCR(nn.Module):
    """
    ResNet-based OCR model with CTC loss support.

    Architecture:
        - ResNet34 Backbone with ECA attention (pretrained on ImageNet)
        - Freeze early layers (conv1, bn1, layer1, layer2)
        - Trainable late layers (layer3 with ECA)
        - Sequence Encoder with Spatial Attention Pooling
        - Improved CTC Head with residual connection

    Args:
        img_h: Input image height (default: 64)
        img_w: Input image width (default: 256)
        num_classes: Number of output classes (characters + blank)
        character: Character set for recognition
        pretrained: Whether to use pretrained ResNet34 weights (default: True)
        freeze_backbone: Whether to freeze early backbone layers (default: True)
        hidden_dim: Hidden dimension for CTC head (default: 128)
        dropout: Dropout rate for CTC head (default: 0.3)
        seq_len: Sequence length for output (default: 32)
    """

    def __init__(
            self,
            img_h: int = 64,
            img_w: int = 256,
            num_classes: int = 63,  # 62 chars + 1 blank
            character: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
            pretrained: bool = True,
            freeze_backbone: bool = True,
            hidden_dim: int = 128,
            dropout: float = 0.3,
            seq_len: int = 32,
    ):
        super().__init__()

        self.img_h = img_h
        self.img_w = img_w
        self.num_classes = num_classes
        self.character = character
        self.hidden_dim = hidden_dim
        self.dropout = dropout
        self.seq_len = seq_len

        # Character to index mapping
        self.char_to_idx = {char: idx for idx, char in enumerate(character)}
        self.idx_to_char = {idx: char for idx, char in enumerate(character)}

        # Build backbone with ECA attention
        self._build_backbone(pretrained)

        # Freeze early layers if requested
        if freeze_backbone:
            self.freeze_backbone()

        # Build sequence encoder with spatial attention pooling
        self._build_sequence_encoder()

        # Build improved CTC head
        self._build_ctc_head()

    def _build_backbone(self, pretrained: bool):
        """Build ResNet34 backbone with ECA attention."""
        import torchvision.models as models

        # Load pretrained ResNet34
        if pretrained:
            resnet = models.resnet34(weights=models.ResNet34_Weights.IMAGENET1K_V1)
        else:
            resnet = models.resnet34(weights=None)

        # Extract needed layers
        self.conv1 = resnet.conv1
        self.bn1 = resnet.bn1
        self.relu = resnet.relu
        self.maxpool = resnet.maxpool
        self.layer1 = resnet.layer1
        self.layer2 = resnet.layer2
        self.layer3 = resnet.layer3  # Output: (B, 256, H/16, W/16)

        # Add ECA attention to layer2 and layer3
        self._add_eca_attention()

    def _add_eca_attention(self):
        """Add ECA attention to layer2 and layer3."""
        from .attention_modules import BasicBlockWithECA

        for layer in [self.layer2, self.layer3]:
            blocks = list(layer.children())
            new_blocks = []
            for block in blocks:
                if hasattr(block, 'conv2'):
                    channels = block.conv2.out_channels
                    new_block = BasicBlockWithECA(block, channels)
                    new_blocks.append(new_block)
                else:
                    new_blocks.append(block)
            layer.__init__(*new_blocks)

    def _build_sequence_encoder(self):
        """Build sequence encoder with spatial attention pooling."""
        from .attention_modules import SpatialAttentionPooling

        self.adaptive_pool = SpatialAttentionPooling(
            in_channels=256,
            seq_len=self.seq_len
        )

    def _build_ctc_head(self):
        """Build improved CTC head."""
        from .attention_modules import ImprovedCTCHead

        self.ctc_head = ImprovedCTCHead(
            in_channels=256,
            hidden_dim=self.hidden_dim,
            num_classes=self.num_classes,
            dropout=self.dropout,
            num_conv_layers=2
        )

    def freeze_backbone(self):
        """Freeze early layers to prevent overfitting on small datasets."""
        for param in self.conv1.parameters():
            param.requires_grad = False
        for param in self.bn1.parameters():
            param.requires_grad = False
        for param in self.layer1.parameters():
            param.requires_grad = False
        for param in self.layer2.parameters():
            param.requires_grad = False
        # Layer3 remains trainable

    def unfreeze_backbone(self):
        """Unfreeze all backbone layers."""
        for param in self.conv1.parameters():
            param.requires_grad = True
        for param in self.bn1.parameters():
            param.requires_grad = True
        for param in self.layer1.parameters():
            param.requires_grad = True
        for param in self.layer2.parameters():
            param.requires_grad = True
        for param in self.layer3.parameters():
            param.requires_grad = True

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Input tensor (B, C, H, W)

        Returns:
            logits: (B, num_classes, seq_len)
        """
        # Backbone
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)  # (B, 256, H/16, W/16)

        # Sequence encoder
        x = self.adaptive_pool(x)  # (B, 256, 1, seq_len)
        x = x.squeeze(2)  # (B, 256, seq_len)

        # CTC head
        logits = self.ctc_head(x)  # (B, num_classes, seq_len)

        return logits

    def decode(self, logits: torch.Tensor) -> list:
        """
        Decode model output to strings using CTC greedy decoding.

        Args:
            logits: Model output (B, num_classes, T)

        Returns:
            List of decoded strings
        """
        predictions = logits.argmax(dim=1).cpu().numpy()  # (B, T)

        results = []
        blank_idx = self.num_classes - 1
        for pred in predictions:
            result = []
            prev = -1
            for idx in pred:
                idx_int = int(idx)
                if idx_int != prev and idx_int != blank_idx:
                    char = self.idx_to_char.get(idx_int, '')
                    if char:
                        result.append(char)
                prev = idx_int
            results.append(''.join(result))

        return results


class CosineWarmupScheduler(LRScheduler):
    """Cosine annealing with linear warmup."""

    def __init__(
            self,
            optimizer: torch.optim.Optimizer,
            warmup_epochs: int,
            total_epochs: int,
            min_lr: float = 1e-6
    ):
        self.warmup_epochs = warmup_epochs
        self.total_epochs = total_epochs
        self.min_lr = min_lr
        super().__init__(optimizer)

    def get_lr(self):
        if self.last_epoch < self.warmup_epochs:
            alpha = self.last_epoch / self.warmup_epochs
            return [base_lr * alpha for base_lr in self.base_lrs]
        else:
            progress = (self.last_epoch - self.warmup_epochs) / (self.total_epochs - self.warmup_epochs)
            return [self.min_lr + (base_lr - self.min_lr) * 0.5 * (1 + cos(pi * progress))
                    for base_lr in self.base_lrs]


if __name__ == "__main__":
    # Test model
    print("=" * 60)
    print("ResNetOCR Model Test")
    print("=" * 60)

    character = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    num_classes = len(character) + 1
    model = ResNetOCR(
        img_h=64,
        img_w=256,
        num_classes=num_classes,
        character=character,
        pretrained=True,
        freeze_backbone=True
    )

    # Test forward pass
    x = torch.randn(2, 3, 64, 256)
    logits = model(x)
    print(f"Input shape: {x.shape}")
    print(f"Output shape: {logits.shape}")

    # Test decode
    decoded = model.decode(logits)
    print(f"Decoded outputs: {decoded}")

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\nTotal parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
