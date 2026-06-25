"""
DeBERTa inference stub.

Before Phase 5 training is complete (models/deberta/best/ does not exist),
analyze() returns rule-based defaults and is_deberta_active is False.

Once the Phase 5 trainer saves a checkpoint to models/deberta/best/,
the singleton is hot-reloaded on the next call to analyze().
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT      = Path(__file__).parent.parent.parent
MODEL_DIR = ROOT / "models" / "deberta" / "best"

_TARGETS = ["confidence_cls", "stress_cls", "hesitation_cls", "comm_cls"]


@dataclass
class BehavioralNLPResult:
    confidence_score:      float = 0.5
    hesitation_level:      float = 0.3
    communication_quality: float = 0.5
    stress_score:          float = 0.3
    model_used:            str   = "fallback"
    raw_logits:            dict  = field(default_factory=dict)


class BehavioralNLPInference:
    def __init__(self) -> None:
        self._model     = None
        self._tokenizer = None
        self._device    = None
        self._active    = False
        self._try_load()

    # ── load ─────────────────────────────────────────────────────────────────

    def _try_load(self) -> None:
        if not (MODEL_DIR / "model.pt").exists():
            logger.debug("BehavioralNLPInference: no model at %s — running in fallback mode", MODEL_DIR)
            return
        try:
            import torch
            from transformers import AutoTokenizer
            # Import here to avoid hard dependency before training
            from ml.training.deberta_trainer import MultiTaskDeBERTa

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model  = MultiTaskDeBERTa.from_pretrained(str(MODEL_DIR))
            model  = model.to(device)
            model.eval()

            state = torch.load(MODEL_DIR / "model.pt", map_location="cpu")
            tokenizer = AutoTokenizer.from_pretrained(
                state.get("base_model_name", "microsoft/deberta-v3-base")
            )

            self._model     = model
            self._tokenizer = tokenizer
            self._device    = device
            self._active    = True
            logger.info("BehavioralNLPInference: DeBERTa loaded on %s", device)
        except Exception as exc:
            logger.debug("BehavioralNLPInference: load skipped — %s", exc)

    # ── public ────────────────────────────────────────────────────────────────

    def analyze(self, text: str) -> BehavioralNLPResult:
        if not text or not text.strip():
            return BehavioralNLPResult()

        # Try lazy reload if model appeared since last call
        if not self._active and (MODEL_DIR / "model.pt").exists():
            self._try_load()

        if not self._active:
            return BehavioralNLPResult()

        try:
            import torch
            enc = self._tokenizer(
                text,
                max_length=128,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
            enc = {k: v.to(self._device) for k, v in enc.items()}

            with torch.no_grad():
                logits = self._model(**enc)

            def _weighted_score(lg: "torch.Tensor", weights: list[float]) -> float:
                probs = torch.softmax(lg[0], dim=-1).cpu().tolist()
                return float(sum(p * w for p, w in zip(probs, weights)))

            # Map class probabilities to 0-1 scalar scores
            # confidence: cls0=low(0.0) cls1=medium(0.5) cls2=high(1.0)
            confidence = _weighted_score(logits["confidence_cls"], [0.0, 0.5, 1.0])
            stress     = _weighted_score(logits["stress_cls"],     [0.0, 0.5, 1.0])
            hesitation = _weighted_score(logits["hesitation_cls"], [0.0, 0.5, 1.0])
            # comm: cls0=strong(1.0) cls1=clear(0.67) cls2=hesitant(0.33) cls3=weak(0.0)
            comm       = _weighted_score(logits["comm_cls"],       [1.0, 0.67, 0.33, 0.0])

            return BehavioralNLPResult(
                confidence_score=round(confidence, 4),
                hesitation_level=round(hesitation, 4),
                communication_quality=round(comm, 4),
                stress_score=round(stress, 4),
                model_used="deberta",
            )
        except Exception as exc:
            logger.debug("BehavioralNLPInference.analyze error: %s", exc)
            return BehavioralNLPResult()

    @property
    def is_deberta_active(self) -> bool:
        return self._active
