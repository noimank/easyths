"""
Captcha Recognition Training Script.

Usage:
    python train.py                          # Use default config
    python train.py --config custom.yaml     # Use custom config

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
import torch.nn.functional as F
from torch.utils.data import DataLoader
import numpy as np
import yaml

from models.crnn import CRNN, DEFAULT_CHARSET
from models.loss import CaptchaDataset


def parse_args():
    parser = argparse.ArgumentParser(description="Captcha Recognition Training")
    parser.add_argument("--config", type=str, default="config.yaml", help="Config YAML file path")
    return parser.parse_args()


class TrainConfig:
    """Training configuration from YAML."""

    def __init__(self, config: dict):
        g = config.get('Global', {})
        a = config.get('Architecture', {})
        o = config.get('Optimizer', {})
        s = config.get('Scheduler', {})
        t = config.get('Training', {})
        d = config.get('Dataset', {})
        es = t.get('early_stopping', {})

        self.use_gpu = g.get('use_gpu', True)
        self.character = g.get('character', DEFAULT_CHARSET)
        self.img_h = g.get('img_h', 64)
        self.img_w = g.get('img_w', 256)
        self.seed = g.get('seed', 42)
        self.output_dir = g.get('output_dir', 'outputs')
        self.resume = g.get('resume', True)

        self.nc = a.get('backbone', {}).get('nc', 1)
        self.hidden_size = a.get('head', {}).get('hidden_dim', 128)

        self.lr = o.get('lr', 1e-4)
        self.weight_decay = o.get('weight_decay', 1e-5)
        self.epochs = s.get('epochs', 150)
        self.scheduler_type = s.get('type', 'onecycle')
        # OneCycle params
        self.max_lr = s.get('max_lr', 3e-3)
        self.div_factor = s.get('div_factor', 25)
        self.final_div_factor = s.get('final_div_factor', 1000)
        self.pct_start = s.get('pct_start', 0.3)
        # CosineAnnealing params
        self.t0 = s.get('T_0', 10)          # restart period
        self.t_mult = s.get('T_mult', 2)    # period multiplier
        self.eta_min = s.get('eta_min', 1e-6)
        # ReduceLROnPlateau params
        self.factor = s.get('factor', 0.5)
        self.patience = s.get('patience', 5)
        self.min_lr = s.get('min_lr', 1e-7)

        self.batch_size = t.get('batch_size', 32)
        self.num_workers = t.get('num_workers', 0)
        self.save_interval = t.get('save_interval', 20)
        self.es_patience = es.get('patience', 20)
        self.es_min_delta = es.get('min_delta', 0.001)

        self.train_dir = d.get('train_dir', 'data/train')
        self.val_dir = d.get('val_dir', 'data/val')

        self.device = 'cuda' if self.use_gpu and torch.cuda.is_available() else 'cpu'

    def print_summary(self, model: CRNN):
        lines = [
            "=" * 60,
            "Captcha Recognition Training (CRNN)",
            "=" * 60,
            f"Image: {self.img_h}x{self.img_w} (nc={self.nc})",
            f"Charset: {model.character[:20]}... ({len(model.character)} chars, sorted)",
            f"Classes: {model.num_classes} (auto: charset + blank)",
            f"Hidden: {self.hidden_size}  SeqLen: {model.get_seq_len()}",
            f"Epochs: {self.epochs}  BS: {self.batch_size}  MaxLR: {self.max_lr}",
            f"Train: {self.train_dir}  Val: {self.val_dir}",
            f"Device: {self.device}  Resume: {self.resume}",
            "=" * 60,
        ]
        print("\n".join(lines))


# ── Helpers ──────────────────────────────────────────────────

def collate_fn(batch):
    images = torch.stack([b[0] for b in batch])
    max_len = max(b[1].shape[0] for b in batch)
    labels = torch.zeros(len(batch), max_len, dtype=torch.long)
    lengths = torch.zeros(len(batch), dtype=torch.long)
    for i, (_, lbl, ln) in enumerate(batch):
        labels[i, :ln] = lbl
        lengths[i] = ln
    return images, labels, lengths


def compute_ctc_loss(logits, labels, label_lengths, device, num_classes):
    B, C, T = logits.shape
    input_lengths = torch.full((B,), T, dtype=torch.long, device=device)
    log_probs = F.log_softmax(logits.permute(2, 0, 1), dim=2)   # (T, B, C)
    return F.ctc_loss(
        log_probs, labels,
        input_lengths.cpu().tolist(), label_lengths.cpu().tolist(),
        blank=num_classes - 1, reduction='mean', zero_infinity=True
    )


def ctc_greedy_decode(logits, blank):
    preds = logits.argmax(dim=1).cpu().numpy()
    results = []
    for pred in preds:
        out, prev = [], -1
        for idx in pred:
            idx = int(idx)
            if idx != prev and idx != blank:
                out.append(idx)
            prev = idx
        results.append(out)
    return results


def compute_accuracy(pred_seqs, label_seqs):
    total_chars = correct_chars = correct_seqs = 0
    for pred, label in zip(pred_seqs, label_seqs):
        total_chars += len(label)
        correct_chars += sum(p == l for p, l in zip(pred, label))
        if pred == label:
            correct_seqs += 1
    char_acc = correct_chars / max(total_chars, 1)
    seq_acc = correct_seqs / max(len(pred_seqs), 1)
    return char_acc, seq_acc


# ── Scheduler Factory ─────────────────────────────────────────

def build_scheduler(cfg: TrainConfig, optimizer, steps_per_epoch: int):
    """Build learning rate scheduler based on config.

    Scheduler types:
    - onecycle: OneCycleLR - good for training from scratch
    - constant: ConstantLR - fixed LR, best for fine-tuning
    - cosine: CosineAnnealingWarmRestarts - smooth decay with restarts
    - reduce_on_plateau: ReduceLROnPlateau - dynamic based on val metrics
    - linear: LinearLR with warmup - linear decay
    """
    scheduler_type = cfg.scheduler_type.lower()

    if scheduler_type == 'onecycle':
        return torch.optim.lr_scheduler.OneCycleLR(
            optimizer,
            max_lr=cfg.max_lr,
            epochs=cfg.epochs,
            steps_per_epoch=steps_per_epoch,
            div_factor=cfg.div_factor,
            final_div_factor=cfg.final_div_factor,
            pct_start=cfg.pct_start,
            anneal_strategy='cos',
        ), 'step'  # step mode: call scheduler.step() per batch

    elif scheduler_type == 'constant':
        return torch.optim.lr_scheduler.ConstantLR(
            optimizer,
            factor=1.0,
            total_iters=cfg.epochs,
        ), 'epoch'  # epoch mode: call scheduler.step() per epoch

    elif scheduler_type == 'cosine':
        return torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            optimizer,
            T_0=cfg.t0,
            T_mult=cfg.t_mult,
            eta_min=cfg.eta_min,
        ), 'epoch'

    elif scheduler_type == 'reduce_on_plateau':
        return torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode='max',          # maximize seq_acc
            factor=cfg.factor,
            patience=cfg.patience,
            min_lr=cfg.min_lr,
        ), 'plateau'  # plateau mode: call scheduler.step(metric)

    elif scheduler_type == 'linear':
        return torch.optim.lr_scheduler.LinearLR(
            optimizer,
            start_factor=1.0,
            end_factor=0.01,
            total_iters=cfg.epochs,
        ), 'epoch'

    else:
        raise ValueError(f"Unknown scheduler type: {scheduler_type}. "
                        f"Options: onecycle, constant, cosine, reduce_on_plateau, linear")


# ── Train / Eval ─────────────────────────────────────────────

def train_epoch(model, loader, optimizer, scheduler, device, num_classes, scheduler_mode: str):
    model.train()
    total_loss, n = 0.0, len(loader)
    t0 = datetime.now()
    for imgs, labels, lengths in loader:
        imgs = imgs.to(device)
        logits = model(imgs)
        loss = compute_ctc_loss(logits, labels, lengths, device, num_classes)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        if scheduler_mode == 'step':
            scheduler.step()
        total_loss += loss.item()
    return {'loss': total_loss / n, 'time': (datetime.now() - t0).total_seconds()}


def evaluate(model, loader, device, num_classes):
    model.eval()
    total_loss, all_preds, all_labels = 0.0, [], []
    blank = num_classes - 1
    with torch.no_grad():
        for imgs, labels, lengths in loader:
            imgs = imgs.to(device)
            logits = model(imgs)
            total_loss += compute_ctc_loss(logits, labels, lengths, device, num_classes).item()
            all_preds.extend(ctc_greedy_decode(logits, blank))
            for i, ln in enumerate(lengths):
                all_labels.append(labels[i, :ln].cpu().tolist())
    char_acc, seq_acc = compute_accuracy(all_preds, all_labels)
    return {'loss': total_loss / len(loader), 'char_acc': char_acc, 'seq_acc': seq_acc}


# ── Logger / EarlyStopping ───────────────────────────────────

class TrainingLogger:
    HEADERS = ['epoch', 'train_loss', 'val_loss', 'char_acc', 'seq_acc', 'lr', 'time']

    def __init__(self, path):
        self.path = path
        with open(path, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(self.HEADERS)

    def log(self, **kw):
        with open(self.path, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([kw.get(h, '') for h in self.HEADERS])

    def get_best_epoch(self):
        best_acc, best_ep = 0.0, 0
        with open(self.path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                acc = float(row['seq_acc'] or 0)
                if acc > best_acc:
                    best_acc, best_ep = acc, int(row['epoch'])
        return best_ep, best_acc


class EarlyStopping:
    def __init__(self, patience=20, min_delta=0.001):
        self.patience, self.min_delta = patience, min_delta
        self.counter, self.best = 0, None

    def __call__(self, score):
        if self.best is None or score > self.best + self.min_delta:
            self.best, self.counter = score, 0
            return False
        self.counter += 1
        return self.counter >= self.patience


# ── Main ─────────────────────────────────────────────────────

def main():
    args = parse_args()
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)
    cfg = TrainConfig(raw_config)

    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(cfg.seed)
    device = torch.device(cfg.device)

    # Build model (num_classes derived from character automatically)
    model = CRNN(
        character=cfg.character,
        img_h=cfg.img_h, img_w=cfg.img_w,
        nc=cfg.nc, hidden_size=cfg.hidden_size,
    ).to(device)

    cfg.print_summary(model)

    total_p = sum(p.numel() for p in model.parameters())
    train_p = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Parameters: {total_p:,} (trainable: {train_p:,})")

    # Datasets (character sorted inside Dataset, same as model)
    aug_cfg = raw_config.get('DataAugmentation', {})
    train_ds = CaptchaDataset(cfg.train_dir, character=cfg.character,
                              img_h=cfg.img_h, img_w=cfg.img_w, nc=cfg.nc,
                              augment=True, augmentation_config=aug_cfg)
    val_ds = None
    if cfg.val_dir and os.path.exists(cfg.val_dir):
        val_ds = CaptchaDataset(cfg.val_dir, character=cfg.character,
                                img_h=cfg.img_h, img_w=cfg.img_w, nc=cfg.nc, augment=False)
        val_ds.training = False

    print(f"Train: {len(train_ds)}  Val: {len(val_ds) if val_ds else 0}")

    if len(train_ds) == 0:
        print(f"Error: No training data in {cfg.train_dir}")
        sys.exit(1)

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True,
                              num_workers=cfg.num_workers, pin_memory=torch.cuda.is_available(),
                              drop_last=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False,
                            num_workers=cfg.num_workers, pin_memory=torch.cuda.is_available(),
                            collate_fn=collate_fn) if val_ds else None

    # Optimizer / Scheduler
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    steps_per_epoch = len(train_loader)
    scheduler, scheduler_mode = build_scheduler(cfg, optimizer, steps_per_epoch)

    # Resume
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_path = out_dir / "best_model.pt"
    if cfg.resume and best_path.exists():
        model_data = torch.load(best_path, map_location=device, weights_only=True)
        if model_data.get("model_state_dict"):
            model.load_state_dict(model_data["model_state_dict"])
        else:
            model.load_state_dict(model_data)
        # model.load_state_dict(torch.load(best_path, map_location=device, weights_only=True))
        print(f"Resumed from {best_path}")

    logger = TrainingLogger(str(out_dir / "train_log.csv"))
    es = EarlyStopping(cfg.es_patience, cfg.es_min_delta)

    # Training
    best_acc = 0.0
    t_start = datetime.now()
    nc = model.num_classes

    hdr = f"{'Ep':>4} | {'TrLoss':>10} | {'VaLoss':>10} | {'ChAcc':>8} | {'SqAcc':>8} | {'LR':>10} | {'Time':>6}"
    print("\n" + "-" * len(hdr))
    print(hdr)
    print("-" * len(hdr))

    for epoch in range(cfg.epochs):
        tr = train_epoch(model, train_loader, optimizer, scheduler, device, nc, scheduler_mode)
        va = evaluate(model, val_loader, device, nc) if val_loader else {'loss': 0, 'char_acc': 0, 'seq_acc': 0}

        # Step scheduler based on mode
        if scheduler_mode == 'epoch':
            scheduler.step()
        elif scheduler_mode == 'plateau' and val_loader:
            scheduler.step(va['seq_acc'])

        lr = scheduler.get_last_lr()[0]

        print(f"{epoch+1:>4} | {tr['loss']:>10.4f} | {va['loss']:>10.4f} | "
              f"{va['char_acc']:>8.4f} | {va['seq_acc']:>8.4f} | {lr:>10.6f} | {tr['time']:>5.1f}s")

        logger.log(epoch=epoch+1, train_loss=tr['loss'], val_loss=va['loss'],
                   char_acc=va['char_acc'], seq_acc=va['seq_acc'], lr=lr, time=tr['time'])

        if val_loader and va['seq_acc'] > best_acc:
            best_acc = va['seq_acc']
            torch.save(model.state_dict(), best_path)
            print(f"  -> best (SeqAcc={best_acc:.4f})")

        if (epoch + 1) % cfg.save_interval == 0:
            torch.save({'epoch': epoch+1, 'model_state_dict': model.state_dict(),
                        'optimizer_state_dict': optimizer.state_dict(),
                        'scheduler_state_dict': scheduler.state_dict()}, out_dir / f"epoch_{epoch+1}.pt")

        if val_loader and es(va['seq_acc']):
            print(f"\nEarly stopping at epoch {epoch+1}, best={es.best:.4f}")
            break

    torch.save(model.state_dict(), out_dir / "last_model.pt")
    total_time = (datetime.now() - t_start).total_seconds()
    best_ep, best_val = logger.get_best_epoch()
    print(f"\nDone in {total_time/60:.1f}min | Best ep={best_ep} SeqAcc={best_val:.4f}")


if __name__ == "__main__":
    main()
