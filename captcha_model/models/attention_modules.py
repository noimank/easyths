"""
Attention Modules for ResNet-OCR

包含：
- ECABlock: Efficient Channel Attention
- SpatialAttentionPooling: 空间注意力池化
- ImprovedCTCHead: 改进的CTC Head

Author: noimank (康康)
Email: noimank@163.com
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import math


class ECABlock(nn.Module):
    """
    Efficient Channel Attention Block
    轻量级通道注意力，使用1D卷积替代FC层，避免降维

    Args:
        channels: 输入通道数
        gamma: 卷积核大小计算参数，默认2
        beta: 卷积核大小计算参数，默认1

    Note:
        卷积核大小自适应计算: k = int(abs((log2(C) + beta) / gamma))
    """

    def __init__(self, channels: int, gamma: int = 2, beta: int = 1):
        super(ECABlock, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)

        # 自适应计算卷积核大小
        kernel_size = int(abs((math.log2(channels) + beta) / gamma))
        kernel_size = kernel_size if kernel_size % 2 else kernel_size + 1  # 确保为奇数

        self.conv = nn.Conv1d(
            in_channels=1,
            out_channels=1,
            kernel_size=kernel_size,
            padding=kernel_size // 2,
            bias=False
        )
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, C, H, W]
        Returns:
            out: [B, C, H, W]
        """
        # Squeeze: 全局平均池化
        y = self.avg_pool(x)  # [B, C, 1, 1]
        y = y.squeeze(-1).transpose(-1, -2)  # [B, 1, C]

        # Excitation: 1D卷积捕获跨通道交互
        y = self.conv(y)  # [B, 1, C]
        y = self.sigmoid(y)  # [B, 1, C]

        # Scale: 重新校准
        y = y.transpose(-1, -2).unsqueeze(-1)  # [B, C, 1, 1]
        out = x * y.expand_as(x)
        return out


class SpatialAttentionPooling(nn.Module):
    """
    空间注意力池化模块，专为OCR设计
    垂直方向使用注意力压缩，水平方向自适应池化

    Args:
        in_channels: 输入通道数，默认256
        seq_len: 序列长度（时间步），默认32
    """

    def __init__(self, in_channels: int = 256, seq_len: int = 32):
        super(SpatialAttentionPooling, self).__init__()
        self.seq_len = seq_len

        # 垂直方向注意力压缩
        self.vertical_attention = nn.Sequential(
            nn.Conv2d(in_channels, in_channels // 4, kernel_size=1),
            nn.BatchNorm2d(in_channels // 4),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels // 4, 1, kernel_size=1),
            nn.Sigmoid()
        )

        # 水平方向自适应池化
        self.horizontal_pool = nn.AdaptiveAvgPool2d((1, seq_len))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, C, H, W]
        Returns:
            out: [B, C, 1, seq_len]
        """
        # 计算垂直方向注意力权重
        attention_weights = self.vertical_attention(x)  # [B, 1, H, W]

        # 应用注意力压缩垂直维度
        attended_features = x * attention_weights  # [B, C, H, W]

        # 水平方向池化
        out = self.horizontal_pool(attended_features)  # [B, C, 1, seq_len]

        return out


class ImprovedCTCHead(nn.Module):
    """
    改进的CTC Head
    使用3x1卷积捕获局部时序上下文，添加残差连接保留原始信息

    Args:
        in_channels: 输入通道数，默认256
        hidden_dim: 隐藏层维度，默认128
        num_classes: 输出类别数（字符数+blank），默认12
        dropout: Dropout比例，默认0.3
        num_conv_layers: 3x1卷积层数，默认2
    """

    def __init__(
        self,
        in_channels: int = 256,
        hidden_dim: int = 128,
        num_classes: int = 12,
        dropout: float = 0.3,
        num_conv_layers: int = 2
    ):
        super(ImprovedCTCHead, self).__init__()
        self.num_conv_layers = num_conv_layers

        # 构建多层3x1卷积
        layers = []
        current_channels = in_channels

        for i in range(num_conv_layers):
            layers.extend([
                nn.Conv1d(current_channels, hidden_dim, kernel_size=3, padding=1),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(inplace=True),
                nn.Dropout(dropout)
            ])
            current_channels = hidden_dim

        self.conv_layers = nn.Sequential(*layers)

        # 残差连接的投影层（如果通道数不匹配）
        self.residual_proj = None
        if in_channels != hidden_dim:
            self.residual_proj = nn.Conv1d(in_channels, hidden_dim, kernel_size=1)

        # 最终分类层
        self.classifier = nn.Conv1d(hidden_dim, num_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, C, T] 来自序列编码器的特征
        Returns:
            logits: [B, num_classes, T] CTC logits
        """
        # 残差连接
        residual = x
        if self.residual_proj is not None:
            residual = self.residual_proj(residual)

        # 3x1卷积层
        out = self.conv_layers(x)

        # 残差连接
        out = out + residual

        # 分类
        logits = self.classifier(out)

        return logits


class BasicBlockWithECA(nn.Module):
    """
    带有 ECA 注意力的 BasicBlock，用于替换 ResNet 的标准 BasicBlock。
    这种标准的 nn.Module 实现方式可以确保 ONNX 导出正确。

    Args:
        original_block: 原始的 BasicBlock 实例
        channels: 输出通道数（用于 ECA）
    """

    expansion = 1

    def __init__(self, original_block: nn.Module, channels: int):
        super(BasicBlockWithECA, self).__init__()

        # 复制原始 block 的所有属性
        self.conv1 = original_block.conv1
        self.bn1 = original_block.bn1
        self.conv2 = original_block.conv2
        self.bn2 = original_block.bn2
        self.downsample = original_block.downsample

        # 添加 ECA 注意力
        self.eca = ECABlock(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = F.relu(out, inplace=True)

        out = self.conv2(out)
        out = self.bn2(out)

        # Apply ECA before residual connection
        out = self.eca(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = F.relu(out, inplace=True)

        return out
