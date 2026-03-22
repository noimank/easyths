"""
Captcha Recognition Training Script.

Usage:
    python train.py                          # Use default config
    python train.py --config custom.yaml    # Use custom config

Author: noimank (康康)
Email: noimank@163.com
"""
import os
import sys
import argparse
import csv
from pathlib import Path
from datetime import datetime

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
import numpy as np
import yaml

from models.resnet_ocr import ResNetOCR, CosineWarmupScheduler
from models.loss import CaptchaDataset


def parse_args():
    parser = argparse.ArgumentParser(description="Captcha Recognition Training")
    parser.add_argument(
        "--config", type=str, default="config.yaml",
        help="Config YAML file path"
    )
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


class TrainConfig:
    """Training configuration from YAML file."""

    def __init__(self, config: dict):
        self._config = config
        self._parse_config()

    def _parse_config(self):
        global_cfg = self._config.get('Global', {})
        arch_cfg = self._config.get('Architecture', {})
        backbone_cfg = arch_cfg.get('backbone', {})
        head_cfg = arch_cfg.get('head', {})
        opt_cfg = self._config.get('Optimizer', {})
        scheduler_cfg = self._config.get('Scheduler', {})
        train_cfg = self._config.get('Training', {})
        dataset_cfg = self._config.get('Dataset', {})

        # Global settings
        self.use_gpu = global_cfg.get('use_gpu', True)
        self.character = global_cfg.get('character', "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
        self.img_h = global_cfg.get('img_h', 64)
        self.img_w = global_cfg.get('img_w', 256)
        self.seed = global_cfg.get('seed', 42)
        self.output_dir = global_cfg.get('output_dir', "data/outputs/captcha_ocr")
        self.resume = global_cfg.get('resume', True)

        # Architecture settings
        self.pretrained = backbone_cfg.get('pretrained', True)
        self.freeze_backbone = backbone_cfg.get('freeze_backbone', True)
        self.hidden_dim = head_cfg.get('hidden_dim', 128)
        self.dropout = head_cfg.get('dropout', 0.3)

        # Optimizer settings
        self.lr = opt_cfg.get('lr', 1e-4)
        self.weight_decay = opt_cfg.get('weight_decay', 1e-5)

        # Scheduler settings
        self.warmup_epochs = scheduler_cfg.get('warmup_epoch', 5)
        self.epochs = scheduler_cfg.get('epochs', 200)

        # Training settings
        self.batch_size = train_cfg.get('batch_size', 32)
        self.num_workers = train_cfg.get('num_workers', 0)
        self.amp = train_cfg.get('amp', False)
        self.save_interval = train_cfg.get('save_interval', 20)

        # Dataset settings
        self.train_dir = dataset_cfg.get('train_dir', 'data/train')
        self.val_dir = dataset_cfg.get('val_dir', 'data/val')

        # Derived values
        self.num_classes = len(self.character) + 1  # +1 for blank
        self.device = "cuda" if self.use_gpu and torch.cuda.is_available() else "cpu"

    def __repr__(self) -> str:
        lines = [
            "=" * 60,
            "Captcha Recognition Training",
            "=" * 60,
            f"Image size: {self.img_h}x{self.img_w}",
            f"Character set: {self.character[:20]}... ({len(self.character)} chars)",
            f"Num classes: {self.num_classes}",
            f"Epochs: {self.epochs}",
            f"Batch size: {self.batch_size}",
            f"Learning rate: {self.lr}",
            f"Warmup epochs: {self.warmup_epochs}",
            f"Output: {self.output_dir}",
            "-" * 60,
            f"Train dir: {self.train_dir}",
            f"Val dir: {self.val_dir}",
            "-" * 60,
            f"AMP: {self.amp}",
            f"Resume: {self.resume}",
            f"Device: {self.device}",
            "=" * 60,
        ]
        return "\n".join(lines)


def collate_fn(batch):
    """Custom collate function for variable length labels."""
    images = torch.stack([item[0] for item in batch], dim=0)
    max_label_len = max(item[1].shape[0] for item in batch)
    labels = torch.zeros(len(batch), max_label_len, dtype=torch.long)
    label_lengths = torch.zeros(len(batch), dtype=torch.long)

    for i, (img, label, length) in enumerate(batch):
        labels[i, :length] = label
        label_lengths[i] = length

    return images, labels, label_lengths


def compute_ctc_loss(
    logits: torch.Tensor,
    labels: torch.Tensor,
    label_lengths: torch.Tensor,
    device: str,
    num_classes: int
) -> torch.Tensor:
    """Compute CTC loss."""
    B, C, T = logits.shape
    input_lengths = torch.full((B,), T, dtype=torch.long, device=device)

    log_probs = logits.permute(2, 0, 1)  # (T, B, C)
    log_probs = F.log_softmax(log_probs, dim=2)

    blank_idx = num_classes - 1

    loss = F.ctc_loss(
        log_probs,
        labels,
        input_lengths.cpu().tolist(),
        label_lengths.cpu().tolist(),
        blank=blank_idx,
        reduction='mean',
        zero_infinity=True
    )

    return loss


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


def compute_accuracy(pred_seqs: list, label_seqs: list) -> tuple:
    """Compute character and sequence accuracy."""
    total_chars = 0
    correct_chars = 0
    correct_seqs = 0

    for pred, label in zip(pred_seqs, label_seqs):
        total_chars += len(label)
        for p, l in zip(pred, label):
            if p == l:
                correct_chars += 1
        if pred == label:
            correct_seqs += 1

    char_acc = correct_chars / max(total_chars, 1)
    seq_acc = correct_seqs / len(pred_seqs) if pred_seqs else 0

    return char_acc, seq_acc


def train_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scheduler: CosineWarmupScheduler,
    device: str,
    num_classes: int,
    amp_enabled: bool = False
) -> dict:
    """Train for one epoch."""
    model.train()
    total_loss = 0.0
    num_batches = len(dataloader)

    scaler = torch.cuda.amp.GradScaler() if amp_enabled else None
    epoch_start = datetime.now()

    for batch in dataloader:
        images = batch[0].to(device)
        labels = batch[1].to(device)
        label_lengths = batch[2].to(device)

        if amp_enabled:
            with torch.cuda.amp.autocast():
                logits = model(images)
                loss = compute_ctc_loss(logits, labels, label_lengths, device, num_classes)
            optimizer.zero_grad()
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            logits = model(images)
            loss = compute_ctc_loss(logits, labels, label_lengths, device, num_classes)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        total_loss += loss.item()

    scheduler.step()
    epoch_time = (datetime.now() - epoch_start).total_seconds()

    return {'loss': total_loss / num_batches, 'time': epoch_time}


def evaluate(
    model: nn.Module,
    dataloader: DataLoader,
    device: str,
    num_classes: int
) -> dict:
    """Evaluate model."""
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_labels = []
    num_batches = len(dataloader)
    blank_idx = num_classes - 1

    with torch.no_grad():
        for batch in dataloader:
            images = batch[0].to(device)
            labels = batch[1].to(device)
            label_lengths = batch[2].to(device)

            logits = model(images)
            loss = compute_ctc_loss(logits, labels, label_lengths, device, num_classes)
            total_loss += loss.item()

            preds = ctc_greedy_decode(logits, blank_idx)
            all_preds.extend(preds)

            for i, length in enumerate(label_lengths):
                label_list = labels[i, :length].cpu().tolist()
                all_labels.append(label_list)

    char_acc, seq_acc = compute_accuracy(all_preds, all_labels)

    return {
        'loss': total_loss / num_batches,
        'char_acc': char_acc,
        'seq_acc': seq_acc
    }


class TrainingLogger:
    """CSV-based training logger."""

    def __init__(self, log_file: str):
        self.log_file = log_file
        self.headers = ['epoch', 'train_loss', 'val_loss', 'char_acc', 'seq_acc', 'lr', 'time']
        with open(log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)

    def log(self, epoch: int, train_loss: float, val_loss: float,
            char_acc: float, seq_acc: float, lr: float, time: float):
        with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([epoch, train_loss, val_loss, char_acc, seq_acc, lr, time])

    def get_best_epoch(self) -> tuple:
        best_seq_acc = 0.0
        best_epoch = 0
        with open(self.log_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                seq_acc = float(row['seq_acc']) if row['seq_acc'] else 0.0
                if seq_acc > best_seq_acc:
                    best_seq_acc = seq_acc
                    best_epoch = int(row['epoch'])
        return best_epoch, best_seq_acc


def main():
    args = parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config = load_config(str(config_path))
    cfg = TrainConfig(config)

    device = torch.device(cfg.device)
    print(f"\nUsing device: {device}")
    print(cfg)

    # Set seeds
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(cfg.seed)

    # Build model
    model = ResNetOCR(
        img_h=cfg.img_h,
        img_w=cfg.img_w,
        num_classes=cfg.num_classes,
        character=cfg.character,
        pretrained=cfg.pretrained,
        freeze_backbone=cfg.freeze_backbone,
        hidden_dim=cfg.hidden_dim,
        dropout=cfg.dropout
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Model parameters: {total_params:,} (trainable: {trainable_params:,})")

    # Build optimizer
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=cfg.lr,
        weight_decay=cfg.weight_decay
    )

    # Build scheduler
    scheduler = CosineWarmupScheduler(
        optimizer,
        warmup_epochs=cfg.warmup_epochs,
        total_epochs=cfg.epochs,
        min_lr=1e-6
    )

    # Build datasets
    augmentation_config = config.get('DataAugmentation', {})

    train_dataset = CaptchaDataset(
        data_dir=cfg.train_dir,
        img_h=cfg.img_h,
        img_w=cfg.img_w,
        character=cfg.character,
        augment=True,
        augmentation_config=augmentation_config
    )

    val_dataset = None
    if cfg.val_dir and os.path.exists(cfg.val_dir):
        val_dataset = CaptchaDataset(
            data_dir=cfg.val_dir,
            img_h=cfg.img_h,
            img_w=cfg.img_w,
            character=cfg.character,
            augment=False
        )
        val_dataset.training = False

    print(f"Train samples: {len(train_dataset)}")
    if val_dataset:
        print(f"Val samples: {len(val_dataset)}")

    # Build dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=cfg.batch_size,
        shuffle=True,
        num_workers=cfg.num_workers,
        pin_memory=False,
        drop_last=True,
        collate_fn=collate_fn
    )

    val_loader = None
    if val_dataset:
        val_loader = DataLoader(
            val_dataset,
            batch_size=cfg.batch_size,
            shuffle=False,
            num_workers=cfg.num_workers,
            pin_memory=False,
            collate_fn=collate_fn
        )

    # Create output directory
    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resume from best model
    best_model_path = output_dir / "best_model.pt"
    if cfg.resume and best_model_path.exists():
        print(f"Resuming from: {best_model_path}")
        state_dict = torch.load(best_model_path, map_location=device)
        model.load_state_dict(state_dict)
        print("Model weights loaded")

    # Initialize logger
    logger = TrainingLogger(str(output_dir / "train_log.csv"))

    # Training loop
    best_seq_acc = 0.0
    start_time = datetime.now()

    print("\n" + "-" * 80)
    print(f"{'Epoch':>5} | {'Train Loss':>12} | {'Val Loss':>12} | {'Char Acc':>10} | {'Seq Acc':>10} | {'LR':>10} | {'Time':>8}")
    print("-" * 80)

    for epoch in range(cfg.epochs):
        train_metrics = train_epoch(
            model, train_loader, optimizer, scheduler,
            device, cfg.num_classes, cfg.amp
        )

        val_metrics = {'loss': 0.0, 'char_acc': 0.0, 'seq_acc': 0.0}
        if val_loader:
            val_metrics = evaluate(model, val_loader, device, cfg.num_classes)

        current_lr = scheduler.get_last_lr()[0]
        epoch_time = train_metrics['time']

        print(f"{epoch + 1:>5} | {train_metrics['loss']:>12.4f} | "
              f"{val_metrics['loss']:>12.4f} | {val_metrics['char_acc']:>10.4f} | "
              f"{val_metrics['seq_acc']:>10.4f} | {current_lr:>10.6f} | {epoch_time:>7.1f}s")

        logger.log(
            epoch + 1,
            train_metrics['loss'],
            val_metrics['loss'],
            val_metrics['char_acc'],
            val_metrics['seq_acc'],
            current_lr,
            epoch_time
        )

        # Save best model
        if val_loader and val_metrics['seq_acc'] > best_seq_acc:
            best_seq_acc = val_metrics['seq_acc']
            torch.save(model.state_dict(), best_model_path)
            print(f"  [*] New best model (Seq Acc: {best_seq_acc:.4f})")

        # Save checkpoint
        if (epoch + 1) % cfg.save_interval == 0:
            ckpt_path = output_dir / f"epoch_{epoch + 1}.pt"
            torch.save({
                'epoch': epoch + 1,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scheduler_state_dict': scheduler.state_dict(),
            }, ckpt_path)

    # Save final model
    final_path = output_dir / "last_model.pt"
    torch.save(model.state_dict(), final_path)

    total_time = (datetime.now() - start_time).total_seconds()
    best_epoch, best_seq_acc_value = logger.get_best_epoch()

    print("-" * 80)
    print(f"\nTraining completed!")
    print(f"  Total time: {total_time / 60:.1f} minutes")
    print(f"  Best epoch: {best_epoch} (Seq Acc: {best_seq_acc_value:.4f})")
    print(f"  Final model: {final_path}")
    print(f"  Best model: {best_model_path}")


if __name__ == "__main__":
    main()
