"""
Feature Store schemas — structured representation of every extracted feature.

Every feature that flows through the pipeline should be loggable here.
This creates an audit trail:
  - What features did the model see for this prediction?
  - Which pipeline version extracted them?
  - What was the quality of that feature?

Enables: offline experimentation, model comparison, debugging, retraining.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FeatureSource(str, Enum):
    FACE    = "face"
    AUDIO   = "audio"
    NLP     = "nlp"
    DERIVED = "derived"        # computed from multiple modalities
    META    = "session_meta"   # session-level metadata


class FeatureQuality(str, Enum):
    HIGH    = "high"       # >0.80
    MEDIUM  = "medium"     # 0.50–0.80
    LOW     = "low"        # 0.20–0.50
    MISSING = "missing"    # not available this window


@dataclass
class FeatureRecord:
    """One extracted feature value at a point in time."""
    feature_id:       str   = field(default_factory=lambda: str(uuid.uuid4())[:12])
    session_id:       str   = ""
    window_index:     int   = 0
    timestamp:        float = field(default_factory=time.time)

    # Feature identity
    name:             str   = ""              # e.g. "eye_contact_score"
    value:            Any   = None            # float, bool, str, list
    source:           FeatureSource = FeatureSource.DERIVED
    quality:          FeatureQuality = FeatureQuality.HIGH

    # Provenance
    pipeline_version: str   = "3.0.0"        # reasoning pipeline version
    extractor:        str   = ""              # which extractor produced this

    def to_dict(self) -> Dict:
        return {
            "feature_id":       self.feature_id,
            "session_id":       self.session_id,
            "window_index":     self.window_index,
            "timestamp":        self.timestamp,
            "name":             self.name,
            "value":            self.value,
            "source":           self.source.value,
            "quality":          self.quality.value,
            "pipeline_version": self.pipeline_version,
            "extractor":        self.extractor,
        }


@dataclass
class FeatureBatch:
    """All features extracted during one reasoning window."""
    batch_id:     str   = field(default_factory=lambda: str(uuid.uuid4())[:12])
    session_id:   str   = ""
    window_index: int   = 0
    timestamp:    float = field(default_factory=time.time)
    features:     List[FeatureRecord] = field(default_factory=list)

    # Aggregate quality
    face_available:  bool  = False
    audio_available: bool  = False
    nlp_available:   bool  = False
    evidence_count:  int   = 0

    def to_dict(self) -> Dict:
        return {
            "batch_id":      self.batch_id,
            "session_id":    self.session_id,
            "window_index":  self.window_index,
            "timestamp":     self.timestamp,
            "feature_count": len(self.features),
            "features":      [f.to_dict() for f in self.features],
            "face_available":  self.face_available,
            "audio_available": self.audio_available,
            "nlp_available":   self.nlp_available,
            "evidence_count":  self.evidence_count,
        }
