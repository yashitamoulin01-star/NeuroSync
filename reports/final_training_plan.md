# MBA Phase 5 — Final Training Plan
*Generated: 2026-06-16 14:49 UTC*

---

## Executive Summary

All data prerequisites are satisfied for DeBERTa training.
The fusion model requires a preparatory export step before training.
Training must not begin until the CUDA driver is installed and PyTorch is rebuilt with `cu118`.

| Item | Status |
|------|--------|
| DeBERTa training data | READY (74,288 records) |
| sklearn / statistical features | READY (44-dim, 74,288 rows) |
| Session embeddings (428-dim) | READY (74,288 sessions) |
| Fusion training export | NOT BUILT — prerequisite step required |
| CUDA / GPU | NOT READY — driver install required |
| Phase 4 classifiers | TRAINED (serving as baseline) |

---

## Training Sequence

### Step 0 — CUDA Setup (prerequisite, ~30 min)

```powershell
# 1. Install NVIDIA driver from nvidia.com → GeForce → MX130 → Win11
#    Required driver version: ≥ 452.39

# 2. Verify driver
nvidia-smi

# 3. Uninstall CPU-only torch
D:\MBD\.venv\Scripts\pip uninstall torch torchaudio torchvision -y

# 4. Install CUDA 11.8 torch (installs to D: drive via venv — no C: space issue)
D:\MBD\.venv\Scripts\pip install torch==2.3.0+cu118 torchaudio==2.3.0+cu118 torchvision==0.18.0+cu118 --index-url https://download.pytorch.org/whl/cu118

# 5. Verify GPU
D:\MBD\.venv\Scripts\python -c "import torch; print(torch.cuda.get_device_name(0))"
# Expected: NVIDIA GeForce MX130
```

---

### Step 1 — Phase 5A: DeBERTa Multi-Task Fine-Tuning (~5–10 hours on MX130)

**Model:** `microsoft/deberta-v3-base`
**Method:** LoRA (PEFT) — only 442,368 trainable parameters (0.24% of 184M)
**Targets:** `confidence_cls`, `stress_cls`, `hesitation_cls`, `comm_cls`
**Excluded:** `eye_cls` (degenerate — 19,807:1 imbalance, 100% class 0)

#### Architecture
```
Input text (max 128 tokens)
    ↓
DeBERTa-v3-base backbone (184M params, FROZEN)
  + LoRA adapters: query_proj, key_proj, value_proj
    r=16, alpha=32, dropout=0.1
    Trainable ΔW only (~442K params)
    ↓
[CLS] token → Dropout(0.1)
    ↓
4 × Linear classification heads:
  confidence_cls  → 3 classes (low / medium / high)
  stress_cls      → 3 classes (calm / moderate / high)
  hesitation_cls  → 3 classes (low / medium / high)
  comm_cls        → 4 classes (strong / clear / hesitant / weak)
```

#### Training Configuration
```python
TrainingConfig(
    base_model        = "microsoft/deberta-v3-base",
    max_seq_length    = 128,          # avg text = 14.5 words, max = 66
    lora_r            = 16,
    lora_alpha        = 32,
    lora_dropout      = 0.1,
    lora_target_modules = ["query_proj", "key_proj", "value_proj"],
    num_epochs        = 3,
    batch_size        = 8,            # fp16 on MX130; use 4 on CPU
    learning_rate     = 2e-4,
    warmup_ratio      = 0.06,
    weight_decay      = 0.01,
    eval_steps        = 500,
    logging_steps     = 100,
)
```

#### Class Weights (Inverse Frequency)
| Target | Class 0 | Class 1 | Class 2 | Class 3 |
|--------|---------|---------|---------|---------|
| confidence_cls | 0.90 (low) | 0.77 (medium) | 1.70 (high) | — |
| stress_cls | 1.17 (calm) | 0.65 (moderate) | 1.63 (high) | — |
| hesitation_cls | 0.85 (low) | 0.96 (medium) | 1.25 (high) | — |
| comm_cls | 1.21 (strong) | 0.83 (clear) | 1.89 (hesitant) | 2.32 (weak) |

#### Run Command
```powershell
cd D:\MBD
D:\.venv\Scripts\python ml/training/deberta_trainer.py
# or with custom params:
D:\.venv\Scripts\python ml/training/deberta_trainer.py --epochs 3 --batch-size 8 --lora-r 16
# CPU fallback (slow):
D:\.venv\Scripts\python ml/training/deberta_trainer.py --cpu-only --batch-size 4
```

#### Expected Outputs
```
models/deberta/best/model.pt          — best checkpoint (merged LoRA)
models/deberta/best/tokenizer_config.json
models/deberta/final/model.pt         — end-of-training checkpoint
models/deberta/metrics.json           — full training + eval report
```

#### Expected Metrics (based on similar tasks)
| Target | Expected val macro-F1 |
|--------|-----------------------|
| confidence_cls | 0.55 – 0.72 |
| stress_cls | 0.55 – 0.72 |
| hesitation_cls | 0.50 – 0.68 |
| comm_cls | 0.48 – 0.65 |
| **Average** | **0.52 – 0.69** |

*Note: These are text-only models on synthetic GoEmotions-derived data.
Real-session fine-tuning post-deployment will significantly improve performance.*

---

### Step 2 — Phase 5B: Build Fusion Training Arrays (prerequisite for Step 3, ~5 min)

The `data/exports/fusion/` directory is currently empty.
Before training the fusion model, export 428-dim `[text || audio || face]` arrays
from the 74,288 labeled session embeddings.

```python
# Script to build: scripts/build_fusion_arrays.py  (create before running)
# Input:   data/embeddings/sessions/<id>/text.npy + audio.npy + face.npy
#          data/labeled/sessions/<id>/labels.json
# Output:  data/exports/fusion/X_train.npy  (N, 428)
#                               Y_train.npy  (N, 4)   ← 4 targets, not 5
#                               X_val.npy / Y_val.npy
#                               X_test.npy / Y_test.npy
```

Embedding dimensions: text=384, audio=28, face=16 → **combined=428**
Label columns: `confidence_cls`, `stress_cls`, `hesitation_cls`, `comm_cls` (eye_cls excluded)

---

### Step 3 — Phase 5C: Multimodal Fusion Model (~5–30 min on MX130)

**Model:** MLP on 428-dim concatenated embeddings
**Targets:** same 4 as DeBERTa (eye_cls excluded)

#### Architecture
```
Input: [text_emb(384) || audio_emb(28) || face_emb(16)] → 428-dim
    ↓
LayerNorm(428)
    ↓
Linear(428 → 256) → ReLU → Dropout(0.3)
    ↓
Linear(256 → 128)  → ReLU → Dropout(0.2)
    ↓
4 × Linear(128 → n_classes) heads
```

#### Configuration
```python
FusionConfig(
    input_dim     = 428,
    hidden_dims   = [256, 128],
    dropout       = 0.3,
    num_epochs    = 30,
    batch_size    = 64,
    learning_rate = 1e-3,
)
```

#### Estimated Training Time
| Hardware | Estimated Time |
|----------|---------------|
| MX130 GPU | 3–8 minutes |
| CPU | 10–30 minutes |

---

## Hardware Requirements Summary

| Requirement | Value | Available | Status |
|-------------|-------|-----------|--------|
| RAM | ≥ 4 GB free | 1.0 GB free | WARNING — close all apps |
| VRAM | ≥ 1.0 GB (LoRA fp16) | 2.0 GB (MX130) | READY after driver install |
| CUDA Driver | ≥ 452.39 | Not installed | BLOCKER |
| torch CUDA | cu118 | +cpu build | BLOCKER |
| Disk (D:) | ~2 GB (model + cache) | Check available | Verify |
| HF cache | ~700 MB (DeBERTa-v3-base) | Already cached | READY |

---

## Checkpoint Strategy

| Event | Action | Location |
|-------|--------|----------|
| Every 500 steps (best val F1) | Save merged model | `models/deberta/best/` |
| End of training | Save final state | `models/deberta/final/` |
| After fusion training | Save best MLP | `models/fusion/best_fusion.pt` |
| Training complete | Emit metrics.json | `models/deberta/metrics.json` |

---

## Evaluation Metrics

### DeBERTa
| Metric | Description |
|--------|-------------|
| `macro_F1` | Primary — equal weight across all classes (handles imbalance) |
| `weighted_F1` | Secondary — class-frequency weighted |
| `accuracy` | Reported but not used for model selection |
| `confusion_matrix` | Per-target, for error analysis |
| `avg_macro_F1` | Checkpoint trigger — mean of 4 target macro-F1 scores |

### Fusion MLP
| Metric | Description |
|--------|-------------|
| `macro_F1` | Per-target |
| `val_loss` | For early stopping |

---

## Expected Final Output Structure

```
models/
  deberta/
    best/
      model.pt                ← merged DeBERTa + LoRA weights (~700 MB)
      tokenizer_config.json
      metrics.json
    final/
      model.pt
    metrics.json              ← full training report
  fusion/
    best_fusion.pt            ← MLP weights (~1 MB)
    fusion_metrics.json
  classifiers/                ← Phase 4 (already trained)
    *.pkl
    metrics.json
```

---

## Data Quality Notes

1. **Synthetic labels**: All 74,288 sessions are labeled `"labeled_by": "synthetic_generator"`.
   Phase 4 classifier F1 scores near 1.0 confirm features directly encode labels.
   DeBERTa provides an **independent text-based signal** immune to this leakage.

2. **eye_cls degenerate**: 99.987% class 0 across all splits. Excluded from all deep learning.

3. **Session text avg length**: 14.5 words (max 66 words). Well within DeBERTa's 128 token limit.
   `max_seq_length=128` is optimal — using 512 would waste 4× compute.

4. **Pre-training model cached**: `microsoft/deberta-v3-base` is already in HuggingFace cache
   from the Phase 5 smoke test. No re-download required.

---

## Go/No-Go Checklist

- [ ] NVIDIA driver installed and `nvidia-smi` shows MX130
- [ ] `torch.cuda.is_available()` returns `True`
- [ ] At least 3 GB RAM free (close browser, IDE, other apps)
- [ ] At least 1.5 GB free disk space on D:
- [ ] `data/exports/deberta/train.jsonl` exists (74,288 rows total) ← **DONE**
- [ ] `models/deberta/` directory writable ← **DONE**
- [ ] `D:/MBD/.venv/Scripts/python ml/training/deberta_trainer.py --help` runs cleanly ← **DONE**
- [ ] (Optional) Build fusion arrays before Step 3

**When all boxes are checked → run Step 1.**
