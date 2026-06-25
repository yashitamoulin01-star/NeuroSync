"""
Model Registry — centralized metadata catalog for every AI model in the system.

Every inference is traceable to a specific model version with performance metrics.
The backend never hardcodes model names in business logic — it queries the registry.

Exposed via GET /system/models so interviewers can see model provenance.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ModelMetadata:
    name:               str
    version:            str
    purpose:            str
    framework:          str
    checkpoint:         str
    status:             str = "active"        # active | loading | unavailable | deprecated
    training_dataset:   Optional[str]  = None
    training_date:      Optional[str]  = None
    macro_f1:           Optional[float]= None  # primary evaluation metric
    inference_latency_ms: Optional[float] = None
    memory_mb:          Optional[float]= None
    supported_tasks:    List[str]      = field(default_factory=list)
    loaded_at:          Optional[float]= None

    def to_dict(self) -> Dict:
        return {
            "name":               self.name,
            "version":            self.version,
            "purpose":            self.purpose,
            "framework":          self.framework,
            "checkpoint":         self.checkpoint,
            "status":             self.status,
            "training_dataset":   self.training_dataset,
            "training_date":      self.training_date,
            "macro_f1":           self.macro_f1,
            "inference_latency_ms": round(self.inference_latency_ms, 2)
                                    if self.inference_latency_ms else None,
            "memory_mb":          self.memory_mb,
            "supported_tasks":    self.supported_tasks,
            "loaded_at":          self.loaded_at,
        }


class ModelRegistry:
    def __init__(self) -> None:
        self._models: Dict[str, ModelMetadata] = {}

    def register(self, meta: ModelMetadata) -> None:
        self._models[meta.name] = meta

    def get(self, name: str) -> Optional[ModelMetadata]:
        return self._models.get(name)

    def all(self) -> List[ModelMetadata]:
        return list(self._models.values())

    def active(self) -> List[ModelMetadata]:
        return [m for m in self._models.values() if m.status == "active"]

    def mark_loaded(self, name: str) -> None:
        if meta := self._models.get(name):
            meta.status    = "active"
            meta.loaded_at = time.time()

    def mark_unavailable(self, name: str, reason: str = "") -> None:
        if meta := self._models.get(name):
            meta.status = "unavailable"

    def update_latency(self, name: str, latency_ms: float) -> None:
        if meta := self._models.get(name):
            # Exponential moving average so one slow inference doesn't spike the metric
            if meta.inference_latency_ms is None:
                meta.inference_latency_ms = latency_ms
            else:
                meta.inference_latency_ms = 0.8 * meta.inference_latency_ms + 0.2 * latency_ms

    def summary(self) -> Dict:
        return {
            "total": len(self._models),
            "active": len(self.active()),
            "models": [m.to_dict() for m in self._models.values()],
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
model_registry = ModelRegistry()

# ── Pre-registered models ────────────────────────────────────────────────────

model_registry.register(ModelMetadata(
    name             = "mediapipe_face_mesh",
    version          = "0.10.x",
    purpose          = "Facial landmark detection and gaze estimation",
    framework        = "MediaPipe",
    checkpoint       = "built-in (468-landmark model)",
    status           = "active",
    inference_latency_ms = 12.0,
    memory_mb        = 40.0,
    supported_tasks  = ["eye_contact", "gaze_direction", "head_stability",
                        "facial_tension", "blink_rate", "expression_label"],
))

model_registry.register(ModelMetadata(
    name             = "faster_whisper",
    version          = "large-v3",
    purpose          = "Speech-to-text transcription for NLP pipeline",
    framework        = "faster-whisper (CTranslate2)",
    checkpoint       = "openai/whisper-large-v3",
    status           = "active",
    inference_latency_ms = None,   # depends on audio length
    memory_mb        = 2900.0,     # large-v3 approximate
    supported_tasks  = ["transcription", "word_timing", "language_detection"],
))

model_registry.register(ModelMetadata(
    name             = "deberta_v3_behavioral",
    version          = "1.0.0",
    purpose          = "Behavioral NLP: confidence language, hesitation, clarity",
    framework        = "HuggingFace Transformers + LoRA",
    checkpoint       = "microsoft/deberta-v3-base",
    status           = "active",
    training_dataset = "behavioral_interview_annotations",
    training_date    = "2025-Q4",
    macro_f1         = None,   # populated after evaluation run
    inference_latency_ms = None,
    memory_mb        = 740.0,  # deberta-v3-base + LoRA adapter
    supported_tasks  = ["confidence_language_score", "hesitation_score",
                        "clarity_score", "filler_word_detection"],
))

model_registry.register(ModelMetadata(
    name             = "behavioral_reasoner",
    version          = "3.0.0",
    purpose          = "Evidence graph → calibrated behavioral scores",
    framework        = "Custom Python (asymptotic pull model)",
    checkpoint       = "built-in",
    status           = "active",
    inference_latency_ms = 1.2,
    memory_mb        = 0.5,
    supported_tasks  = ["confidence", "stress", "communication", "engagement", "consistency"],
))
