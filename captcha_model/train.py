"""
Training script for captcha recognition model v2 with CTC Loss.

Features:
- OneCycleLR scheduler
- Gradient clipping for stability
- Reduced decoding frequency for efficiency
- Full checkpoint saving

Usage:
    python -m captcha_model.train
    python -m captcha_model.train --config path/to/config.yaml
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import OneCycleLR
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from captcha_model.utils import (
    load_config,
    ensure_output_dir,
    get_device,
    calculate_ctc_accuracy,
)
from captcha_model.dataset import create_dataloader
from captcha_model.model import CaptchaRecognizer, CTCLoss, count_parameters


class EarlyStopping:
    """Early stopping handler to stop training when validation metric stops improving."""

    def __init__(self, patience: int = 10, min_delta: float = 0.0001, mode: str = "max"):
        """
        Args:
            patience: Number of epochs to wait for improvement
            min_delta: Minimum change to qualify as an improvement
            mode: 'max' for metrics to maximize (e.g., accuracy), 'min' for minimize (e.g., loss)
        """
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.counter = 0
        self.best_score = None
        self.should_stop = False

    def __call__(self, score: float) -> bool:
        """
        Check if training should stop.

        Args:
            score: Current validation metric value

        Returns:
            True if training should stop, False otherwise
        """
        if self.best_score is None:
            self.best_score = score
            return False

        if self.mode == "max":
            improved = score > self.best_score + self.min_delta
        else:
            improved = score < self.best_score - self.min_delta

        if improved:
            self.best_score = score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True

        return self.should_stop

    def get_info(self) -> str:
        """Get current early stopping status."""
        return f"no improvement for {self.counter}/{self.patience} epochs (best: {self.best_score:.4f})"


def create_optimizer(model: nn.Module, config: Dict) -> optim.Optimizer:
    return optim.AdamW(
        model.parameters(),
        lr=config["training"]["learning_rate"],
        weight_decay=config["training"]["weight_decay"],
    )


def create_scheduler(
    optimizer: optim.Optimizer,
    config: Dict,
    dataloader: torch.utils.data.DataLoader,
) -> Optional[optim.lr_scheduler._LRScheduler]:
    scheduler_config = config["training"].get("scheduler", {})
    scheduler_type = scheduler_config.get("type", "onecycle")

    epochs = config["training"]["epochs"]

    if scheduler_type == "onecycle":
        return OneCycleLR(
            optimizer,
            max_lr=config["training"]["learning_rate"],
            epochs=epochs,
            steps_per_epoch=len(dataloader),
            pct_start=config["training"].get("warmup_epochs", 5) / epochs,
            anneal_strategy='cos',
            div_factor=25.0,
            final_div_factor=10000.0,
        )
    return None


def train_epoch(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: torch.device,
    epoch: int,
    config: Dict,
    scheduler: Optional[optim.lr_scheduler._LRScheduler],
    decode_interval: int = 100,
) -> Tuple[float, float, float]:
    """Train for one epoch."""
    model.train()

    total_loss = 0.0
    all_predictions = []
    all_targets = []
    total_samples = 0

    log_interval = config["training"].get("log_interval", 100)

    pbar = tqdm(dataloader, desc=f"Epoch {epoch}", leave=False)

    for batch_idx, (images, targets, input_lengths, target_lengths) in enumerate(pbar):
        images = images.to(device)
        targets = targets.to(device)
        input_lengths = input_lengths.to(device)
        target_lengths = target_lengths.to(device)

        batch_size = images.size(0)

        optimizer.zero_grad()

        outputs = model(images)
        loss = criterion(outputs, targets, input_lengths, target_lengths)

        # Skip invalid losses
        if not torch.isfinite(loss):
            optimizer.zero_grad()
            pbar.set_postfix({"loss": "invalid", "skipped": "1"})
            continue

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        optimizer.step()

        # Step scheduler per batch
        if scheduler is not None:
            scheduler.step()

        total_loss += loss.item() * batch_size
        total_samples += batch_size

        # Only decode periodically to speed up training
        if (batch_idx + 1) % decode_interval == 0 or (batch_idx + 1) == len(dataloader):
            with torch.no_grad():
                predictions = model.decode(images, blank=0, method="greedy")

            target_list = []
            offset = 0
            for length in target_lengths:
                target_list.append(targets[offset:offset + length].tolist())
                offset += length

            all_predictions.extend(predictions)
            all_targets.extend(target_list)

            if len(all_predictions) > 0:
                char_acc, seq_acc = calculate_ctc_accuracy(
                    predictions, target_list
                )
                current_lr = optimizer.param_groups[0]['lr']
                pbar.set_postfix({
                    "loss": f"{loss.item():.4f}",
                    "char_acc": f"{char_acc:.4f}",
                    "seq_acc": f"{seq_acc:.4f}",
                    "lr": f"{current_lr:.6f}",
                })

        if (batch_idx + 1) % log_interval == 0:
            avg_loss = total_loss / total_samples
            if len(all_predictions) > 0:
                char_acc, seq_acc = calculate_ctc_accuracy(all_predictions, all_targets)
            else:
                char_acc, seq_acc = 0.0, 0.0
            print(
                f"  Batch {batch_idx + 1}: loss={avg_loss:.4f}, "
                f"char_acc={char_acc:.4f}, seq_acc={seq_acc:.4f}"
            )

    avg_loss = total_loss / total_samples
    char_accuracy, seq_accuracy = calculate_ctc_accuracy(all_predictions, all_targets)

    return avg_loss, char_accuracy, seq_accuracy


@torch.no_grad()
def validate_epoch(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Tuple[float, float, float]:
    """Validate model on validation set."""
    model.eval()

    total_loss = 0.0
    all_predictions = []
    all_targets = []
    total_samples = 0

    for images, targets, input_lengths, target_lengths in tqdm(dataloader, desc="Validating", leave=False):
        images = images.to(device)
        targets = targets.to(device)
        input_lengths = input_lengths.to(device)
        target_lengths = target_lengths.to(device)

        batch_size = images.size(0)

        outputs = model(images)
        loss = criterion(outputs, targets, input_lengths, target_lengths)

        predictions = model.decode(images, blank=0, method="greedy")

        target_list = []
        offset = 0
        for length in target_lengths:
            target_list.append(targets[offset:offset + length].tolist())
            offset += length

        all_predictions.extend(predictions)
        all_targets.extend(target_list)
        total_loss += loss.item() * batch_size
        total_samples += batch_size

    avg_loss = total_loss / total_samples if total_samples > 0 else 0.0
    char_accuracy, seq_accuracy = calculate_ctc_accuracy(all_predictions, all_targets)

    return avg_loss, char_accuracy, seq_accuracy


def save_checkpoint(
    model: nn.Module,
    output_path: str,
) -> None:
    """Save model weights only."""
    torch.save(model.state_dict(), output_path)


def save_best_model(
    model: nn.Module,
    epoch: int,
    seq_acc: float,
    output_path: str,
) -> None:
    """Save best model weights."""
    torch.save(model.state_dict(), output_path)
    print(f"  Best model saved (epoch {epoch}, seq_acc={seq_acc:.4f})")


def load_weights(model: nn.Module, weights_path: str, device: torch.device) -> None:
    """Load model weights only."""
    model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=True))


def train(config: Dict) -> CaptchaRecognizer:
    device = get_device()
    print(f"Using device: {device}")

    output_dir = ensure_output_dir(config["training"]["output_dir"])

    charset_size = len(config["charset"])

    # Create model
    model = CaptchaRecognizer(
        charset_size=charset_size,
        dropout=config["model"]["dropout"],
        hidden_size=config["model"]["hidden_size"],
        num_tcn_layers=config["model"]["num_tcn_layers"],
        kernel_size=config["model"].get("kernel_size", 3),
    )
    model.to(device)

    print(f"Model: CNN + TCN + CTC")
    print(f"Parameters: {count_parameters(model):,}")

    optimizer = create_optimizer(model, config)

    # Load training data first to create scheduler
    train_dir = config["dataset"]["train_dir"]
    print(f"Loading training data from: {train_dir}")
    train_loader = create_dataloader(train_dir, config, is_training=True)

    scheduler = create_scheduler(optimizer, config, train_loader)
    criterion = CTCLoss(blank=0, reduction="mean", zero_infinity=True)

    # Load validation data if available
    val_dir = config["dataset"].get("val_dir")
    val_loader = None
    if val_dir:
        val_path = Path(val_dir)
        if val_path.exists():
            print(f"Loading validation data from: {val_dir}")
            val_loader = create_dataloader(val_dir, config, is_training=False)

    epochs = config["training"]["epochs"]

    best_seq_accuracy = 0.0
    best_val_seq_accuracy = 0.0
    best_model_path = output_dir / "best_model.pth"
    checkpoint_path = output_dir / "checkpoint.pth"
    start_epoch = 1

    # Initialize early stopping
    early_stopping_config = config["training"].get("early_stopping", {})
    early_stopping = None
    if early_stopping_config.get("enabled", False) and val_loader is not None:
        early_stopping = EarlyStopping(
            patience=early_stopping_config.get("patience", 10),
            min_delta=early_stopping_config.get("min_delta", 0.0001),
            mode="max",  # Maximize seq_acc
        )
        print(f"Early stopping enabled: patience={early_stopping.patience}, min_delta={early_stopping.min_delta}")

    # Load existing weights if available
    if best_model_path.exists():
        print(f"\nFound existing best model: {best_model_path}")
        load_weights(model, str(best_model_path), device)
        print("  Loaded model weights, starting fresh")

    # Decode interval - decode every N batches for efficiency
    decode_interval = max(1, len(train_loader) // 10)  # ~10 times per epoch

    print(f"\nStarting training from epoch {start_epoch} to {epochs}...")
    print(f"Decode interval: every {decode_interval} batches")
    start_time = time.time()

    for epoch in range(start_epoch, epochs + 1):
        epoch_start = time.time()

        avg_loss, char_acc, seq_acc = train_epoch(
            model, train_loader, criterion, optimizer, device, epoch, config,
            scheduler, decode_interval=decode_interval
        )

        epoch_time = time.time() - epoch_start

        current_lr = optimizer.param_groups[0]["lr"]

        # Training metrics
        log_msg = (
            f"Epoch {epoch}/{epochs}: "
            f"train_loss={avg_loss:.4f}, train_char_acc={char_acc:.4f}, train_seq_acc={seq_acc:.4f}"
        )

        # Validation metrics
        if val_loader is not None:
            val_loss, val_char_acc, val_seq_acc = validate_epoch(
                model, val_loader, criterion, device
            )
            log_msg += f", val_loss={val_loss:.4f}, val_char_acc={val_char_acc:.4f}, val_seq_acc={val_seq_acc:.4f}"

            # Save best model based on validation accuracy
            if val_seq_acc > best_val_seq_accuracy:
                best_val_seq_accuracy = val_seq_acc
                save_best_model(model, epoch, val_seq_acc, str(best_model_path))

            # Check early stopping
            if early_stopping is not None:
                log_msg += f", {early_stopping.get_info()}"
                if early_stopping(val_seq_acc):
                    print(log_msg)
                    print(f"\nEarly stopping triggered at epoch {epoch}")
                    break
        else:
            # Fallback to training accuracy if no validation set
            if epoch == start_epoch or seq_acc > best_seq_accuracy:
                best_seq_accuracy = seq_acc
                save_best_model(model, epoch, seq_acc, str(best_model_path))

        log_msg += f", lr={current_lr:.6f}, time={epoch_time:.1f}s"
        print(log_msg)

        # Save checkpoint every N epochs
        checkpoint_interval = config["training"].get("checkpoint_interval", 5)
        if epoch % checkpoint_interval == 0:
            save_checkpoint(model, str(checkpoint_path))

    # Save final checkpoint
    save_checkpoint(model, str(checkpoint_path))

    total_time = time.time() - start_time
    print(f"\nTraining completed in {total_time / 60:.1f} minutes")

    if val_loader is not None:
        print(f"Best validation sequence accuracy: {best_val_seq_accuracy:.4f}")
    else:
        print(f"Best training sequence accuracy: {best_seq_accuracy:.4f}")

    return model


def main():
    parser = argparse.ArgumentParser(description="Train captcha recognition model")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    train(config)


if __name__ == "__main__":
    main()
