"""
Backend event type definitions.

The event bus uses these types to route events to subscribers.
Events flow through the system without components needing to know about each other.

Flow:
  FRAME_RECEIVED → {VISION, AUDIO, NLP}_FEATURES_READY → EVIDENCE_CREATED
  → REASONING_COMPLETED → INSIGHT_GENERATED → REPORT_UPDATED
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class EventType(str, Enum):
    # Frame ingestion
    FRAME_RECEIVED           = "frame.received"
    AUDIO_CHUNK_RECEIVED     = "audio.chunk.received"

    # Feature extraction
    VISION_FEATURES_READY    = "vision.features.ready"
    AUDIO_FEATURES_READY     = "audio.features.ready"
    NLP_FEATURES_READY       = "nlp.features.ready"

    # Reasoning pipeline
    EVIDENCE_CREATED         = "evidence.created"
    REASONING_COMPLETED      = "reasoning.completed"
    INSIGHT_GENERATED        = "insight.generated"

    # Session lifecycle
    SESSION_CREATED          = "session.created"
    SESSION_STREAMING        = "session.streaming"
    SESSION_PAUSED           = "session.paused"
    SESSION_ENDED            = "session.ended"
    SESSION_FAILED           = "session.failed"

    # State machine
    BEHAVIORAL_STATE_CHANGED = "session.behavioral_state.changed"

    # System
    MODEL_LOADED             = "system.model.loaded"
    MODEL_UNAVAILABLE        = "system.model.unavailable"
    BENCHMARK_COMPLETED      = "system.benchmark.completed"


@dataclass
class BackendEvent:
    type:       EventType
    session_id: str
    payload:    Dict[str, Any] = field(default_factory=dict)
    event_id:   str            = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp:  float          = field(default_factory=time.time)
    source:     str            = "backend"
