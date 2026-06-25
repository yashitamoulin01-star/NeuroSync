"""
Behavioral evidence data models.

These are the atomic observations that sit between raw metrics and composite scores.
No imports from other backend modules — this file is a pure data layer.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
import time


class EvidencePolarity(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class EvidenceDimension(str, Enum):
    CONFIDENCE    = "confidence"
    STRESS        = "stress"
    COMMUNICATION = "communication"
    ENGAGEMENT    = "engagement"
    CONSISTENCY   = "consistency"


class BehavioralEvidence(BaseModel):
    """
    An atomic, traceable behavioral observation.

    contribution: pull factor [0–1]. Applied asymptotically:
      positive → score += contribution * (1 - score)
      negative → score -= contribution * score
    This keeps scores naturally bounded without clamping.
    """
    id: str
    dimension: EvidenceDimension
    polarity: EvidencePolarity
    description: str
    measurement: Optional[float] = None
    source_modalities: List[str] = []
    timestamp: float = Field(default_factory=time.time)
    contribution: float = 0.0


class ModalityQuality(BaseModel):
    """Quality assessment for each input modality in the current window."""
    face_available: bool = False
    face_quality: float = 0.0      # derived from eye_contact_score as a proxy for frame quality
    audio_available: bool = False
    audio_quality: float = 0.0     # derived from energy_level
    nlp_available: bool = False
    nlp_quality: float = 0.0       # derived from words_per_chunk / target
    transcript_words: int = 0
    evidence_coverage: float = 0.0  # fraction of dimensions that have at least one evidence item


class PredictionReliability(str, Enum):
    HIGH         = "high"
    MEDIUM       = "medium"
    LOW          = "low"
    INSUFFICIENT = "insufficient"


class ScoreBreakdown(BaseModel):
    """
    Calibrated per-dimension scores with reliability metadata.
    This is the output of the reasoning layer before it maps into FusedAnalytics.
    """
    confidence:        float = 0.0
    stress:            float = 0.0
    communication:     float = 0.0
    engagement:        float = 0.0
    consistency:       float = 0.0
    reliability:       PredictionReliability = PredictionReliability.INSUFFICIENT
    evidence_count:    int = 0
    evidence_coverage: float = 0.0
