"""
Phase 5 — DeBERTa Multi-Task Trainer

Fine-tunes microsoft/deberta-v3-base with LoRA (PEFT) for four behavioral
classification targets: confidence_cls, stress_cls, hesitation_cls, comm_cls.

Run directly:
    D:/MBD/.venv/Scripts/python ml/training/deberta_trainer.py
    D:/MBD/.venv/Scripts/python ml/training/deberta_trainer.py --epochs 5 --batch-size 4
    D:/MBD/.venv/Scripts/python ml/training/deberta_trainer.py --cpu-only

Outputs (all under models/deberta/):
    checkpoint.pt               — latest resumable checkpoint (auto-saved every save_steps)
    best/model.pt               — best val avg-macro-F1 checkpoint (merged)
    best/tokenizer files        — tokenizer for inference
    final/model.pt              — end-of-training checkpoint (merged)
    metrics.json                — full training + eval report
    training.log                — full console mirror
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoTokenizer,
    DebertaV2Model,
    get_linear_schedule_with_warmup,
)
from peft import LoraConfig, get_peft_model

logger = logging.getLogger(__name__)

ROOT      = Path(__file__).parent.parent.parent
DATA_DIR  = ROOT / "data" / "exports" / "deberta"
MODEL_DIR = ROOT / "models" / "deberta"
CKPT_PATH = MODEL_DIR / "checkpoint.pt"

# ── Targets ───────────────────────────────────────────────────────────────────

TARGETS = ["confidence_cls", "stress_cls", "hesitation_cls", "comm_cls"]

NUM_CLASSES: dict[str, int] = {
    "confidence_cls": 3,
    "stress_cls":     3,
    "hesitation_cls": 3,
    "comm_cls":       4,
}

CLASS_NAMES: dict[str, dict[int, str]] = {
    "confidence_cls": {0: "low",    1: "medium",   2: "high"},
    "stress_cls":     {0: "calm",   1: "moderate", 2: "high"},
    "hesitation_cls": {0: "low",    1: "medium",   2: "high"},
    "comm_cls":       {0: "strong", 1: "clear",    2: "hesitant", 3: "weak"},
}

# Inverse-frequency weights from training data distributions:
#   confidence: [37.0%, 43.4%, 19.6%]
#   stress:     [28.5%, 51.1%, 20.4%]
#   hesitation: [39.0%, 34.5%, 26.5%]
#   comm:       [27.6%, 40.3%, 17.7%, 14.4%]
CLASS_WEIGHTS: dict[str, list[float]] = {
    "confidence_cls": [0.90, 0.77, 1.70],
    "stress_cls":     [1.17, 0.65, 1.63],
    "hesitation_cls": [0.85, 0.96, 1.25],
    "comm_cls":       [1.21, 0.83, 1.89, 2.32],
}


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class TrainingConfig:
    base_model:    str = "microsoft/deberta-v3-base"
    max_seq_length: int = 64

    # LoRA — tuned for MX130 (2 GB VRAM)
    lora_r:              int       = 16
    lora_alpha:          int       = 32
    lora_dropout:        float     = 0.1
    lora_target_modules: list[str] = field(
        default_factory=lambda: ["query_proj", "key_proj", "value_proj"]
    )

    # Optimisation
    num_epochs:                int   = 3
    batch_size:                int   = 1      # 1 for MX130 2 GB VRAM; use grad accumulation
    gradient_accumulation_steps: int = 8      # effective batch = batch_size × grad_accum
    gradient_checkpointing:    bool  = True   # required for 2 GB VRAM
    learning_rate:             float = 2e-4
    warmup_ratio:              float = 0.06
    weight_decay:              float = 0.01
    max_grad_norm:             float = 1.0

    # Evaluation / checkpointing
    eval_steps:    int = 2000
    save_steps:    int = 500   # save resumable checkpoint every N optimizer steps
    logging_steps: int = 100

    # Per-task loss weights (equal by default)
    task_weights: dict[str, float] = field(
        default_factory=lambda: {t: 1.0 for t in TARGETS}
    )


# ── Dataset ───────────────────────────────────────────────────────────────────

class BehavioralDataset(Dataset):
    def __init__(self, jsonl_path: str | Path, tokenizer, max_length: int = 128) -> None:
        self.records: list[dict] = []
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                self.records.append(json.loads(line))
        self.tokenizer  = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> dict:
        rec = self.records[idx]
        enc = self.tokenizer(
            rec["text"],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        item: dict[str, torch.Tensor] = {
            "input_ids":      enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
        }
        if "token_type_ids" in enc:
            item["token_type_ids"] = enc["token_type_ids"].squeeze(0)
        for t in TARGETS:
            item[t] = torch.tensor(rec[t], dtype=torch.long)
        return item


# ── Model ─────────────────────────────────────────────────────────────────────

class MultiTaskDeBERTa(nn.Module):
    """
    DeBERTa-v3-base backbone with one linear classification head per target.
    Designed to be wrapped by PEFT LoRA during training and loaded directly
    (from a merged state dict) during inference.
    """

    def __init__(self, base_model_name: str = "microsoft/deberta-v3-base") -> None:
        super().__init__()
        self.deberta = DebertaV2Model.from_pretrained(base_model_name)
        hidden = self.deberta.config.hidden_size
        self.classifiers = nn.ModuleDict({
            t: nn.Linear(hidden, NUM_CLASSES[t])
            for t in TARGETS
        })
        self.dropout = nn.Dropout(0.1)

    def forward(
        self,
        input_ids:      torch.Tensor,
        attention_mask: torch.Tensor,
        token_type_ids: Optional[torch.Tensor] = None,
        **_,
    ) -> dict[str, torch.Tensor]:
        kw: dict = {"input_ids": input_ids, "attention_mask": attention_mask}
        if token_type_ids is not None:
            kw["token_type_ids"] = token_type_ids
        out    = self.deberta(**kw)
        pooled = self.dropout(out.last_hidden_state[:, 0, :])   # [CLS] token
        return {t: self.classifiers[t](pooled) for t in TARGETS}

    # ── persistence ───────────────────────────────────────────────────────────

    def save_pretrained(self, save_dir: str | Path, base_model_name: str) -> None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        torch.save(
            {"base_model_name": base_model_name, "model_state_dict": self.state_dict()},
            save_dir / "model.pt",
        )

    @classmethod
    def from_pretrained(cls, model_dir: str | Path) -> "MultiTaskDeBERTa":
        data  = torch.load(Path(model_dir) / "model.pt", map_location="cpu")
        model = cls(data["base_model_name"])
        model.load_state_dict(data["model_state_dict"])
        return model


# ── Loss ──────────────────────────────────────────────────────────────────────

def _build_loss_fns(device: torch.device) -> dict[str, nn.CrossEntropyLoss]:
    return {
        t: nn.CrossEntropyLoss(
            weight=torch.tensor(CLASS_WEIGHTS[t], dtype=torch.float32).to(device)
        )
        for t in TARGETS
    }


# ── Metrics ───────────────────────────────────────────────────────────────────

def _compute_metrics(all_preds: dict[str, list], all_labels: dict[str, list]) -> dict:
    from sklearn.metrics import accuracy_score, f1_score, confusion_matrix

    result: dict = {}
    f1s: list[float] = []
    for t in TARGETS:
        y_pred = np.array(all_preds[t])
        y_true = np.array(all_labels[t])
        acc  = float(accuracy_score(y_true, y_pred))
        mf1  = float(f1_score(y_true, y_pred, average="macro",    zero_division=0))
        wf1  = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))
        cm   = confusion_matrix(y_true, y_pred, labels=list(range(NUM_CLASSES[t]))).tolist()
        f1s.append(mf1)
        result[t] = {
            "accuracy":    round(acc, 4),
            "macro_f1":    round(mf1, 4),
            "weighted_f1": round(wf1, 4),
            "confusion_matrix": cm,
        }
    result["avg_macro_f1"] = round(float(np.mean(f1s)), 4)
    return result


@torch.no_grad()
def _evaluate(
    model: nn.Module,
    loader: DataLoader,
    loss_fns: dict[str, nn.CrossEntropyLoss],
    device: torch.device,
) -> tuple[float, dict]:
    model.eval()
    total_loss = 0.0
    all_preds:  dict[str, list] = {t: [] for t in TARGETS}
    all_labels: dict[str, list] = {t: [] for t in TARGETS}

    for batch in loader:
        input_ids      = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        token_type_ids = batch.get("token_type_ids")
        if token_type_ids is not None:
            token_type_ids = token_type_ids.to(device)

        logits = model(input_ids, attention_mask, token_type_ids)

        step_loss = 0.0
        for t in TARGETS:
            labels = batch[t].to(device)
            step_loss += loss_fns[t](logits[t], labels).item()
            preds = logits[t].argmax(dim=-1).cpu().numpy().tolist()
            all_preds[t].extend(preds)
            all_labels[t].extend(labels.cpu().numpy().tolist())
        total_loss += step_loss / len(TARGETS)

    avg_loss = total_loss / max(len(loader), 1)
    metrics  = _compute_metrics(all_preds, all_labels)
    return avg_loss, metrics


# ── GPU Monitor ───────────────────────────────────────────────────────────────

def _gpu_stats() -> str:
    if not torch.cuda.is_available():
        return ""
    alloc  = torch.cuda.memory_allocated()  / 1e6
    reserv = torch.cuda.memory_reserved()   / 1e6
    return f"  VRAM={alloc:.0f}/{reserv:.0f}MB"


# ── Trainer ───────────────────────────────────────────────────────────────────

class DeBERTaTrainer:
    def __init__(self, config: Optional[TrainingConfig] = None) -> None:
        self.config     = config or TrainingConfig()
        self._device    = torch.device("cpu")
        self._tokenizer = None

    # ── setup ─────────────────────────────────────────────────────────────────

    def _setup(self) -> nn.Module:
        if torch.cuda.is_available():
            self._device = torch.device("cuda")
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info("GPU: %s  VRAM: %.1f GB  fp16: enabled",
                        torch.cuda.get_device_name(0), vram_gb)
            if vram_gb < 3.0:
                self.config.batch_size = min(self.config.batch_size, 1)
                self.config.gradient_accumulation_steps = max(
                    self.config.gradient_accumulation_steps, 8
                )
                self.config.gradient_checkpointing = True
                logger.warning(
                    "Low VRAM (%.1f GB) - batch=1, grad_accum=%d, grad_ckpt=True",
                    vram_gb, self.config.gradient_accumulation_steps,
                )
        else:
            self._device = torch.device("cpu")
            self.config.batch_size = min(self.config.batch_size, 4)
            self.config.gradient_checkpointing = False
            logger.warning("No GPU found - training on CPU (slow)")

        logger.info("Loading tokenizer: %s", self.config.base_model)
        self._tokenizer = AutoTokenizer.from_pretrained(self.config.base_model)

        logger.info("Building MultiTaskDeBERTa with LoRA r=%d alpha=%d",
                    self.config.lora_r, self.config.lora_alpha)
        base = MultiTaskDeBERTa(self.config.base_model)

        if self.config.gradient_checkpointing:
            base.deberta.gradient_checkpointing_enable()
            base.deberta.enable_input_require_grads()

        lora_cfg = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=self.config.lora_target_modules,
            bias="none",
        )
        model = get_peft_model(base, lora_cfg)
        model.print_trainable_parameters()
        return model.to(self._device)

    # ── checkpoint helpers ────────────────────────────────────────────────────

    def _save_checkpoint(
        self,
        model:        nn.Module,
        optimizer:    torch.optim.Optimizer,
        scheduler,
        scaler,
        global_step:  int,
        epoch:        int,
        next_micro:   int,   # first micro-batch NOT yet processed in `epoch`
        best_val_f1:  float,
        best_step:    int,
        best_weights: Optional[dict],
        history:      list,
    ) -> None:
        CKPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "global_step":  global_step,
            "epoch":        epoch,
            "next_micro":   next_micro,
            "best_val_f1":  best_val_f1,
            "best_step":    best_step,
            "best_weights": best_weights,
            "history":      history,
            "model_state":  self._snapshot_trainable(model),
            "optimizer":    optimizer.state_dict(),
            "scheduler":    scheduler.state_dict(),
            "scaler":       scaler.state_dict() if scaler else None,
        }
        # Write to a temp file then rename (atomic on most filesystems)
        tmp = CKPT_PATH.with_suffix(".tmp")
        torch.save(payload, tmp)
        tmp.replace(CKPT_PATH)
        logger.info("  [ckpt]  saved to %s  (step %d)", CKPT_PATH, global_step)

    def _load_checkpoint(self, model: nn.Module, optimizer, scheduler, scaler) -> dict:
        ckpt = torch.load(CKPT_PATH, map_location=self._device)
        state = model.state_dict()
        state.update({k: v.to(self._device) for k, v in ckpt["model_state"].items()})
        model.load_state_dict(state)
        optimizer.load_state_dict(ckpt["optimizer"])
        scheduler.load_state_dict(ckpt["scheduler"])
        if scaler and ckpt.get("scaler"):
            scaler.load_state_dict(ckpt["scaler"])
        logger.info(
            "Resumed checkpoint - epoch=%d  global_step=%d  best_f1=%.4f",
            ckpt["epoch"], ckpt["global_step"], ckpt["best_val_f1"],
        )
        return ckpt

    # ── train ─────────────────────────────────────────────────────────────────

    def train(self) -> dict:
        model    = self._setup()
        device   = self._device
        use_fp16 = (device.type == "cuda")

        logger.info("Loading data from %s", DATA_DIR)
        train_ds = BehavioralDataset(DATA_DIR / "train.jsonl", self._tokenizer, self.config.max_seq_length)
        val_ds   = BehavioralDataset(DATA_DIR / "val.jsonl",   self._tokenizer, self.config.max_seq_length)
        test_ds  = BehavioralDataset(DATA_DIR / "test.jsonl",  self._tokenizer, self.config.max_seq_length)

        pin = (device.type == "cuda")
        val_loader  = DataLoader(val_ds,  batch_size=32, shuffle=False, num_workers=0, pin_memory=pin)
        test_loader = DataLoader(test_ds, batch_size=32, shuffle=False, num_workers=0, pin_memory=pin)

        loss_fns  = _build_loss_fns(device)
        optimizer = torch.optim.AdamW(
            [p for p in model.parameters() if p.requires_grad],
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )
        grad_accum   = self.config.gradient_accumulation_steps
        # Compute total_steps from dataset size (consistent across resume)
        steps_per_epoch = len(train_ds) // self.config.batch_size // grad_accum
        total_steps     = steps_per_epoch * self.config.num_epochs
        warmup_steps    = max(1, int(total_steps * self.config.warmup_ratio))
        scheduler       = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)
        scaler          = torch.amp.GradScaler("cuda") if use_fp16 else None

        MODEL_DIR.mkdir(parents=True, exist_ok=True)

        # ── Resume from checkpoint if available ───────────────────────────────
        global_step  = 0
        resume_epoch = 0
        resume_micro = 0   # next micro-batch index to process in resume_epoch
        best_val_f1  = -1.0
        best_step    = 0
        best_weights: Optional[dict[str, torch.Tensor]] = None
        history: list[dict] = []

        if CKPT_PATH.exists():
            ckpt = self._load_checkpoint(model, optimizer, scheduler, scaler)
            global_step  = ckpt["global_step"]
            resume_epoch = ckpt["epoch"]
            resume_micro = ckpt["next_micro"]
            best_val_f1  = ckpt["best_val_f1"]
            best_step    = ckpt["best_step"]
            best_weights = ckpt["best_weights"]
            history      = ckpt["history"]
        else:
            logger.info("No checkpoint found - starting from scratch")

        report = {
            "trained_at":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "base_model":   self.config.base_model,
            "lora_r":       self.config.lora_r,
            "lora_alpha":   self.config.lora_alpha,
            "num_epochs":                self.config.num_epochs,
            "batch_size":                self.config.batch_size,
            "gradient_accumulation_steps": self.config.gradient_accumulation_steps,
            "effective_batch_size":      self.config.batch_size * grad_accum,
            "gradient_checkpointing":    self.config.gradient_checkpointing,
            "max_seq_length":            self.config.max_seq_length,
            "device":       str(device),
            "fp16":         use_fp16,
            "n_train":      len(train_ds),
            "n_val":        len(val_ds),
            "n_test":       len(test_ds),
            "targets":      TARGETS,
        }

        logger.info(
            "Training: %d total optimizer steps (%d/epoch), %d warmup, "
            "batch=%d, grad_accum=%d, effective_batch=%d, lr=%.0e",
            total_steps, steps_per_epoch, warmup_steps,
            self.config.batch_size, grad_accum,
            self.config.batch_size * grad_accum,
            self.config.learning_rate,
        )
        if resume_epoch > 0 or resume_micro > 0:
            logger.info("Resuming from epoch %d, micro-batch %d, global_step %d",
                        resume_epoch, resume_micro, global_step)

        for epoch in range(resume_epoch, self.config.num_epochs):
            model.train()
            epoch_loss  = 0.0
            accum_loss  = 0.0
            epoch_steps = 0

            # Seeded per epoch for reproducible shuffle — enables skip-on-resume
            g = torch.Generator()
            g.manual_seed(42 + epoch)
            skip = resume_micro if epoch == resume_epoch else 0

            if skip > 0:
                # Pre-generate the full shuffled order (same as RandomSampler with this generator),
                # then slice from `skip` — instant resume without iterating discarded batches.
                all_indices = torch.randperm(len(train_ds), generator=g).tolist()
                epoch_subset = torch.utils.data.Subset(train_ds, all_indices[skip:])
                epoch_loader = DataLoader(
                    epoch_subset,
                    batch_size=self.config.batch_size,
                    shuffle=False,
                    num_workers=0,
                    pin_memory=pin,
                )
                logger.info("Fast-skip: resuming from micro-batch %d (instant)", skip)
            else:
                epoch_loader = DataLoader(
                    train_ds,
                    batch_size=self.config.batch_size,
                    shuffle=True,
                    num_workers=0,
                    pin_memory=pin,
                    generator=g,
                )

            for micro_step, batch in enumerate(epoch_loader, start=skip):
                input_ids      = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                token_type_ids = batch.get("token_type_ids")
                if token_type_ids is not None:
                    token_type_ids = token_type_ids.to(device)

                if scaler:
                    with torch.amp.autocast("cuda"):
                        logits = model(input_ids, attention_mask, token_type_ids)
                        loss   = self._total_loss(logits, batch, loss_fns, device)
                    scaler.scale(loss / grad_accum).backward()
                else:
                    logits = model(input_ids, attention_mask, token_type_ids)
                    loss   = self._total_loss(logits, batch, loss_fns, device)
                    (loss / grad_accum).backward()

                accum_loss += loss.item()

                if (micro_step + 1) % grad_accum == 0:
                    if scaler:
                        scaler.unscale_(optimizer)
                        nn.utils.clip_grad_norm_(
                            [p for p in model.parameters() if p.requires_grad],
                            self.config.max_grad_norm,
                        )
                        scaler.step(optimizer)
                        scaler.update()
                    else:
                        nn.utils.clip_grad_norm_(
                            [p for p in model.parameters() if p.requires_grad],
                            self.config.max_grad_norm,
                        )
                        optimizer.step()

                    optimizer.zero_grad()
                    scheduler.step()

                    avg_accum    = accum_loss / grad_accum
                    epoch_loss  += avg_accum
                    accum_loss   = 0.0
                    epoch_steps += 1
                    global_step += 1

                    if global_step % self.config.logging_steps == 0:
                        lr = scheduler.get_last_lr()[0]
                        logger.info(
                            "  step %5d  loss=%.4f  lr=%.2e%s",
                            global_step, epoch_loss / epoch_steps, lr, _gpu_stats(),
                        )

                    if global_step % self.config.eval_steps == 0:
                        val_loss, val_metrics = _evaluate(model, val_loader, loss_fns, device)
                        f1 = val_metrics["avg_macro_f1"]
                        logger.info("  [eval %5d]  val_loss=%.4f  avg_macro_f1=%.4f",
                                    global_step, val_loss, f1)
                        history.append({
                            "step": global_step, "epoch": epoch + 1,
                            "val_loss": round(val_loss, 4),
                            "val_avg_macro_f1": f1,
                            **{f"val_{t}_f1": val_metrics[t]["macro_f1"] for t in TARGETS},
                        })
                        if f1 > best_val_f1:
                            best_val_f1  = f1
                            best_step    = global_step
                            best_weights = self._snapshot_trainable(model)
                            logger.info("  [best]  avg_macro_f1=%.4f  (step %d)", f1, global_step)
                        model.train()

                    # Periodic checkpoint — next_micro = micro_step + 1
                    if global_step % self.config.save_steps == 0:
                        self._save_checkpoint(
                            model, optimizer, scheduler, scaler,
                            global_step, epoch, micro_step + 1,
                            best_val_f1, best_step, best_weights, history,
                        )

            # End-of-epoch eval
            val_loss, val_metrics = _evaluate(model, val_loader, loss_fns, device)
            f1 = val_metrics["avg_macro_f1"]
            logger.info(
                "Epoch %d/%d - val_loss=%.4f  avg_macro_f1=%.4f  per-task: %s",
                epoch + 1, self.config.num_epochs, val_loss, f1,
                {t: val_metrics[t]["macro_f1"] for t in TARGETS},
            )
            history.append({
                "step": global_step, "epoch": epoch + 1,
                "val_loss": round(val_loss, 4),
                "val_avg_macro_f1": f1,
                **{f"val_{t}_f1": val_metrics[t]["macro_f1"] for t in TARGETS},
            })
            if f1 > best_val_f1:
                best_val_f1  = f1
                best_step    = global_step
                best_weights = self._snapshot_trainable(model)

            # Save checkpoint at epoch boundary — next epoch, micro=0
            self._save_checkpoint(
                model, optimizer, scheduler, scaler,
                global_step, epoch + 1, 0,
                best_val_f1, best_step, best_weights, history,
            )

            # Flush metrics to disk after every epoch
            partial_report = {**report,
                              "best_val_macro_f1": round(best_val_f1, 4),
                              "best_step": best_step,
                              "training_history": history}
            (MODEL_DIR / "metrics.json").write_text(
                json.dumps(partial_report, indent=2), encoding="utf-8"
            )

        # ── Save final (current end-of-training state) ────────────────────────
        logger.info("Saving final model...")
        self._save_merged(model, MODEL_DIR / "final")

        # ── Restore best weights and save best ────────────────────────────────
        if best_weights is not None:
            logger.info("Restoring best weights (step %d, avg_macro_f1=%.4f)...",
                        best_step, best_val_f1)
            self._restore_trainable(model, best_weights)
        logger.info("Saving best model...")
        self._save_merged(model, MODEL_DIR / "best")

        # ── Test evaluation on best model ─────────────────────────────────────
        logger.info("Running test evaluation...")
        _, test_metrics = _evaluate(model, test_loader, loss_fns, device)
        logger.info("Test avg_macro_f1=%.4f", test_metrics["avg_macro_f1"])

        # ── Final report ──────────────────────────────────────────────────────
        report.update({
            "best_val_macro_f1": round(best_val_f1, 4),
            "best_step":         best_step,
            "training_history":  history,
            "val_metrics":       val_metrics,
            "test_metrics":      test_metrics,
        })
        metrics_path = MODEL_DIR / "metrics.json"
        metrics_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info("metrics.json -> %s", metrics_path)

        # Remove checkpoint after successful completion
        if CKPT_PATH.exists():
            CKPT_PATH.unlink()
            logger.info("Checkpoint removed (training complete)")

        return report

    # ── helpers ───────────────────────────────────────────────────────────────

    def _total_loss(
        self,
        logits: dict[str, torch.Tensor],
        batch:  dict,
        loss_fns: dict[str, nn.CrossEntropyLoss],
        device: torch.device,
    ) -> torch.Tensor:
        losses = [
            self.config.task_weights[t] * loss_fns[t](logits[t], batch[t].to(device))
            for t in TARGETS
        ]
        return sum(losses) / len(TARGETS)   # type: ignore[return-value]

    def _snapshot_trainable(self, model: nn.Module) -> dict[str, torch.Tensor]:
        return {
            k: v.detach().cpu().clone()
            for k, v in model.state_dict().items()
            if "lora_A" in k or "lora_B" in k or "classifiers" in k
        }

    def _restore_trainable(self, model: nn.Module, snapshot: dict[str, torch.Tensor]) -> None:
        current = model.state_dict()
        current.update({k: v.to(self._device) for k, v in snapshot.items()})
        model.load_state_dict(current)

    def _save_merged(self, peft_model: nn.Module, save_dir: Path) -> None:
        import copy
        save_dir.mkdir(parents=True, exist_ok=True)
        model_copy = copy.deepcopy(peft_model)
        model_copy.eval()
        merged: MultiTaskDeBERTa = model_copy.merge_and_unload()
        merged.save_pretrained(save_dir, self.config.base_model)
        self._tokenizer.save_pretrained(str(save_dir))
        del model_copy, merged
        logger.info("Merged checkpoint → %s", save_dir)


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, os, sys, platform

    # Prevent Windows sleep / display-off during training
    if platform.system() == "Windows":
        try:
            import ctypes
            # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)
            print("[sleep-prevention] Windows sleep disabled for this process")
        except Exception:
            pass

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    log_file = MODEL_DIR / "training.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, mode="a", encoding="utf-8"),
        ],
    )

    parser = argparse.ArgumentParser(description="Phase 5 — DeBERTa multi-task trainer")
    parser.add_argument("--epochs",     type=int,   default=3,    help="training epochs")
    parser.add_argument("--batch-size", type=int,   default=1,    help="per-device micro batch size")
    parser.add_argument("--grad-accum", type=int,   default=8,    help="gradient accumulation steps")
    parser.add_argument("--lr",         type=float, default=2e-4, help="learning rate")
    parser.add_argument("--lora-r",     type=int,   default=16,   help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int,   default=32,   help="LoRA alpha")
    parser.add_argument("--max-len",    type=int,   default=128,  help="max token length")
    parser.add_argument("--save-steps", type=int,   default=500,  help="checkpoint every N optimizer steps")
    parser.add_argument("--cpu-only",   action="store_true",      help="force CPU training")
    parser.add_argument("--max-restarts", type=int, default=5,    help="auto-restart on crash")
    args = parser.parse_args()

    if args.cpu_only:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

    sys.path.insert(0, str(ROOT))

    cfg = TrainingConfig(
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        max_seq_length=args.max_len,
        save_steps=args.save_steps,
    )

    result = None
    for attempt in range(1, args.max_restarts + 1):
        try:
            logger.info("=== Training attempt %d/%d ===", attempt, args.max_restarts)
            trainer = DeBERTaTrainer(cfg)
            result  = trainer.train()
            break
        except KeyboardInterrupt:
            logger.info("Interrupted by user - checkpoint preserved at %s", CKPT_PATH)
            sys.exit(0)
        except Exception as exc:
            logger.exception("Training crashed (attempt %d/%d): %s", attempt, args.max_restarts, exc)
            if attempt < args.max_restarts:
                logger.info("Auto-restarting in 15s from latest checkpoint...")
                time.sleep(15)
            else:
                logger.error("Max restarts reached. Exiting.")
                sys.exit(1)

    if result is None:
        sys.exit(1)

    print("\n" + "=" * 60)
    print("PHASE 5 COMPLETE")
    print("=" * 60)
    print(f"  Best val avg_macro_f1 : {result['best_val_macro_f1']:.4f}  (step {result['best_step']})")
    print(f"  Device                : {result['device']}")
    print(f"  fp16                  : {result['fp16']}")
    print("\n  Test metrics:")
    for t in TARGETS:
        m = result["test_metrics"][t]
        print(f"    {t:20s}  acc={m['accuracy']:.4f}  macro_f1={m['macro_f1']:.4f}")
    print(f"\n  Test avg_macro_f1     : {result['test_metrics']['avg_macro_f1']:.4f}")
    print(f"\n  Artifacts saved to    : {MODEL_DIR}")
