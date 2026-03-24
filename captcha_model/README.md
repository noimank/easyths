# 验证码识别模型

基于 CRNN（现代 ResNet-style CNN + BiLSTM + CTC）的验证码识别模型，专门用于识别同花顺交易软件的验证码。

## 模型特性

- **现代 CNN 架构**：ResNet-style 残差块 + SE 通道注意力 + GELU 激活
- **轻量级**：约 1M 参数，支持 CPU 实时推理
- **大小写敏感**：专门优化大小写字母区分（如 `c/C`、`s/S`）
- **OneCycleLR 调度**：超收敛训练，150 epochs 即可收敛
- **ONNX 自包含**：推理参数嵌入模型元数据，无需额外配置文件

## 目录结构

```
captcha_model/
├── config.yaml              # 训练配置文件
├── requirements.txt         # Python 依赖
├── data_generate.py         # 数据集生成脚本（仿同花顺风格）
├── data_generate2.py        # 数据集生成脚本（备选方案）
├── data_generate3.py        # 数据集生成脚本（备选方案）
├── train.py                 # 模型训练脚本
├── eval.py                  # 模型评估脚本
├── export_onnx.py           # 导出 ONNX 模型
├── infer_onnx.py            # ONNX 推理脚本
├── eval_ddddocr.py          # ddddocr 对比评估脚本
├── fonts/                   # 字体文件目录
│   └── *.ttf
├── models/                  # 模型定义
│   ├── __init__.py
│   ├── crnn.py              # CRNN 模型（CaptchaCNN + BiLSTM + CTC）
│   └── loss.py              # 数据集类 + 数据增强
├── data/                    # 数据集目录
│   ├── train/               # 训练集
│   ├── val/                 # 验证集
│   └── test/                # 测试集
├── outputs/                 # 训练输出
│   ├── best_model.pt        # 最佳模型
│   ├── last_model.pt        # 最终模型
│   └── train_log.csv        # 训练日志
└── onnx_model/              # ONNX 模型输出
    └── captcha_ocr.onnx     # 导出的 ONNX 模型
```

## 环境准备

### 安装依赖

```bash
# 使用 uv 安装依赖
cd captcha_model
uv pip install -r requirements.txt
```

### 依赖列表

- PyTorch >= 2.0.0
- onnx >= 1.14.0
- onnxruntime >= 1.15.0
- Pillow >= 10.0.0
- PyYAML >= 6.0
- numpy >= 1.24.0

## 数据集准备

### 1. 准备字体文件

将字体文件放入 `fonts/` 目录：

```bash
ls fonts/
# arial.ttf
# Roboto-VariableFont_wdth,wght.ttf
# ...
```

### 2. 生成数据集

```bash
# 生成训练集
python data_generate.py --num_samples 10000 --output_dir data/train

# 生成验证集
python data_generate.py --num_samples 2000 --output_dir data/val

# 生成测试集
python data_generate.py --num_samples 1000 --output_dir data/test
```

### 3. 数据集格式

图片命名格式：`{label}_{uuid}.png`

```
data/train/
├── aB3x_abc123.png
├── Xy9k_def456.png
└── ...
```

### 4. 同花顺验证码特征

数据生成器精确模拟同花顺验证码：

- 尺寸：84×38 像素
- 背景：纯白 RGB(255, 255, 255)
- 顶部边线：淡蓝色 RGB(219, 233, 242)
- 文字颜色：天蓝色 RGB(0, 160, 233)
- 字符数：4 位
- 字符集：`0-9A-Za-z`（62 字符）
- 无旋转、无干扰线、无噪点

## 模型训练

### 配置文件

`config.yaml` 关键配置：

```yaml
Global:
  use_gpu: true
  character: "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
  img_h: 64
  img_w: 256
  output_dir: "outputs"

Architecture:
  backbone:
    nc: 1  # 1=灰度图, 3=RGB
  head:
    hidden_dim: 128

Scheduler:
  type: onecycle
  epochs: 150
  max_lr: 0.003
  div_factor: 25
  pct_start: 0.3

Training:
  batch_size: 64
  early_stopping:
    patience: 20
```

### 开始训练

```bash
# 使用默认配置
python train.py

# 使用自定义配置
python train.py --config custom_config.yaml
```

### 训练输出

```
outputs/
├── best_model.pt      # 最佳模型（验证集序列准确率最高）
├── last_model.pt      # 最终模型
├── epoch_20.pt        # 周期性检查点
└── train_log.csv      # 训练日志
```

### 学习率调度

使用 **OneCycleLR** 策略：

```
LR
  1.2e-4 ──╱╲
           ╱  ╲  3e-3 (peak)
          ╱    ╲
         ╱      ╲____________
         0    45          150
              30%
```

- 起始 LR：`1.2e-4` (= max_lr / div_factor)
- 峰值 LR：`3e-3`（30% 位置）
- 终止 LR：`~1e-7`

## 模型微调

当需要适配特定验证码样式时，可以对预训练模型进行微调。

### 微调配置

项目提供了专门的微调配置文件 `config_finetune.yaml`，与从头训练的主要区别：

| 参数 | 从头训练 (`config.yaml`) | 微调 (`config_finetune.yaml`) |
|------|-------------------------|------------------------------|
| 学习率调度 | `onecycle` | `constant` |
| 学习率 | 0.0001 | 0.00001 (更低) |
| 数据增强噪声 | 0.02 | 0.04 (更强) |

### 微调步骤

#### 1. 准备数据集

使用数据生成工具或真实验证码样本：

```bash
# 生成训练集（推荐 1000+ 张）
python data_generate.py --num_samples 2000 --output_dir data/train

# 生成验证集
python data_generate.py --num_samples 500 --output_dir data/val

# 生成测试集
python data_generate.py --num_samples 500 --output_dir data/test
```

#### 2. 准备预训练模型

将预训练模型 `best_model.pt` 放到 `outputs/` 目录：

```bash
# 确保模型文件存在
ls outputs/best_model.pt
```

#### 3. 开始微调

```bash
# 使用微调配置
python train.py --config config_finetune.yaml
```

配置文件中 `resume: true` 会自动加载 `outputs/best_model.pt` 作为初始权重。

#### 4. 评估微调效果

```bash
python eval.py --model outputs/best_model.pt --test_dir data/test
```

### 微调配置说明

```yaml
# config_finetune.yaml 关键配置
Optimizer:
  lr: 0.00001  # 更低的学习率，避免破坏预训练权重

Scheduler:
  type: constant  # 固定学习率，适合微调稳定阶段
  # 或使用 reduce_on_plateau 基于验证指标动态调整

Training:
  early_stopping:
    patience: 20  # 防止过拟合
```

### 学习率调度器选择

| 调度器 | 适用场景 |
|--------|----------|
| `constant` | 微调稳定阶段（推荐） |
| `reduce_on_plateau` | 基于验证指标动态调整 |
| `cosine` | 平滑衰减 |
| `onecycle` | 从头训练 |

## 模型评估

```bash
# 使用默认配置
python eval.py

# 指定模型和测试目录
python eval.py --model outputs/best_model.pt --test_dir data/test

# 指定设备
python eval.py --device cuda --batch_size 64
```

### 评估指标

| 指标 | 说明 |
|------|------|
| Char Acc | 单字符识别准确率 |
| Seq Acc | 完整验证码正确率 |
| Latency | 单张图片推理延迟 |

## 导出 ONNX 模型

```bash
# 使用默认配置
python export_onnx.py

# 指定参数
python export_onnx.py --model outputs/best_model.pt --output onnx_model --opset 18
```

### 模型元数据

导出的 ONNX 模型自动嵌入：

- `character`：字符集
- `img_h`：图片高度
- `img_w`：图片宽度
- `nc`：输入通道数

推理时无需额外配置文件。

## ONNX 推理

### 单张图片

```bash
python infer_onnx.py --model onnx_model/captcha_ocr.onnx --image captcha.png
```

### 批量推理

```bash
python infer_onnx.py --model onnx_model/captcha_ocr.onnx --dir data/test
```

### 性能基准

```bash
python infer_onnx.py --model onnx_model/captcha_ocr.onnx --benchmark
```

### GPU 推理

```bash
python infer_onnx.py --model onnx_model/captcha_ocr.onnx --providers CUDAExecutionProvider
```

### Python API

```python
from infer_onnx import ONNXCaptchaRecognizer

ocr = ONNXCaptchaRecognizer("onnx_model/captcha_ocr.onnx")
text, latency_ms = ocr.recognize(image_array)
print(f"结果: {text}, 耗时: {latency_ms:.2f}ms")
```

## 模型架构

### CRNN

```
Input (B, 1, 64, 256)
    │
    ▼
┌─────────────────────────────────┐
│  CaptchaCNN (ResNet-style)      │
│  ┌─────────────────────────────┐│
│  │ Stage 1: Conv(1→32) + Pool  ││  H/2, W/2
│  │ Stage 2: Conv(32→64) + Pool ││  H/4, W/4
│  │ Stage 3: ResBlock(64) + SE  ││  H/8, W~
│  │         + Pool              ││
│  │ Stage 4: Conv(64→128)       ││  H/16, W~
│  │         + ResBlock(128) + SE││
│  │         + Pool              ││
│  │ Stage 5: Conv(128→128, 2×1) ││  H=1
│  └─────────────────────────────┘│
└─────────────────────────────────┘
    │
    ▼
(B, 128, 1, W_seq) → reshape → (W_seq, B, 128)
    │
    ▼
┌─────────────────────────────────┐
│  BiLSTM (hidden=128)            │
│  双向 LSTM 序列编码              │
└─────────────────────────────────┘
    │
    ▼
(W_seq, B, 256)
    │
    ▼
┌─────────────────────────────────┐
│  Linear(256 → 63)               │
│  62 字符 + 1 CTC blank          │
└─────────────────────────────────┘
    │
    ▼
Output (B, 63, W_seq)
    │
    ▼
CTC Greedy Decoding → Predicted Text
```

### 关键组件

| 组件 | 说明 |
|------|------|
| SEBlock | Squeeze-and-Excitation 通道注意力 |
| ResBlock | 残差块：2×Conv + SE + Skip Connection |
| ConvBlock | Conv-BN-GELU，支持 depthwise separable |
| BiLSTM | 双向 LSTM 序列编码 |
| CTC Loss | 无需字符级对齐，支持变长输出 |

### 参数统计

| 模块 | 参数量 |
|------|--------|
| CNN Backbone | ~506K |
| BiLSTM | ~526K |
| Classifier | ~16K |
| **Total** | **~1.05M** |

## 部署到 EasyTHS

### 复制模型

```bash
cp onnx_model/captcha_ocr.onnx ../easyths/assets/onnx_model/
```

### 使用方式

```python
from easyths.utils import get_captcha_ocr_server

ocr = get_captcha_ocr_server()
result = ocr.recognize(captcha_control)
print(f"验证码: {result}")
```

## 常见问题

### Q: 训练时 loss 不下降？

1. 检查数据集是否正确生成
2. 检查字符集配置是否正确
3. 增加训练数据量（建议 >= 5000 张）

### Q: 大小写字母识别混淆？

1. 增加字体多样性
2. 调整数据增强参数（rotation、blur）
3. 使用真实样本微调

### Q: ONNX 导出失败？

1. 确保 PyTorch >= 2.0
2. 尝试不同 opset 版本（14、15、18）
3. 检查模型是否有不支持的操作

### Q: 推理速度慢？

1. 使用 GPU 推理（CUDAExecutionProvider）
2. 确保输入图片尺寸正确（64×256）
3. 批量推理时使用较大 batch_size

## 参考资料

- [CRNN 论文](https://arxiv.org/abs/1507.05717)
- [CTC Loss 解释](https://distill.pub/2017/ctc/)
- [Squeeze-and-Excitation Networks](https://arxiv.org/abs/1709.01507)
- [Super-Convergence (OneCycleLR)](https://arxiv.org/abs/1708.07120)
- [ONNX Runtime](https://onnxruntime.ai/)

## 作者

- 作者：noimank
- 邮箱：noimank@163.com
