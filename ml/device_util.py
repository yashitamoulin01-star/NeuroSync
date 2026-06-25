"""
Inference device resolution.

Defaults to CPU so low-VRAM GPUs (e.g. a 2 GB MX130) never hit CUDA OOM during a
live interview. Override with the INFERENCE_DEVICE setting/env var:
    cpu   — always CPU (safe default)
    cuda  — use the GPU (falls back to CPU if CUDA is unavailable)
    auto  — GPU when available, else CPU
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("ml.device")


def resolve_device(default: str = "cpu") -> str:
    pref = None
    try:
        from backend.core.config import settings
        pref = getattr(settings, "INFERENCE_DEVICE", None)
    except Exception:
        pass
    pref = (pref or os.environ.get("INFERENCE_DEVICE") or default).lower()

    try:
        import torch
        cuda = torch.cuda.is_available()
    except Exception:
        cuda = False

    if pref == "auto":
        return "cuda" if cuda else "cpu"
    if pref == "cuda" and not cuda:
        logger.warning("INFERENCE_DEVICE=cuda but no CUDA available — using CPU")
        return "cpu"
    return "cuda" if (pref == "cuda" and cuda) else "cpu"
