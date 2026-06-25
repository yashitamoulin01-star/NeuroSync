"""
CBIP — Continual Behavioral Intelligence Platform data models.

Architecture (four layers):
  Layer 1 — Inference Intelligence:   immutable production models (Whisper, DeBERTa, MediaPipe)
  Layer 2 — Behavioral Memory:        candidate-scoped EMA profiles (Phase 11, ABME)
  Layer 3 — Behavioral Knowledge:     THIS MODULE — cross-candidate validated knowledge
  Layer 4 — Governed Model Evolution: MLOps pipeline (golden tests → calibration → approval)

Production AI models are never modified by this layer.
Knowledge confidence is always proportional to the validation level that produced it.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import time


class ValidationLevel(str, Enum):
    OBSERVATION        = "observation"         # L1 auto-collected, confidence 0.20
    CANDIDATE_FEEDBACK = "candidate_feedback"  # L2 subjective,     confidence 0.45
    RECRUITER_FEEDBACK = "recruiter_feedback"  # L3 expert,         confidence 0.70
    HIRING_DECISION    = "hiring_decision"     # L4 organisational, confidence 0.90
    LONG_TERM_OUTCOME  = "long_term_outcome"   # L5 performance,    confidence 1.00


VALIDATION_CONFIDENCE: Dict[str, float] = {
    ValidationLevel.OBSERVATION:        0.20,
    ValidationLevel.CANDIDATE_FEEDBACK: 0.45,
    ValidationLevel.RECRUITER_FEEDBACK: 0.70,
    ValidationLevel.HIRING_DECISION:    0.90,
    ValidationLevel.LONG_TERM_OUTCOME:  1.00,
}

# Seed archetypes — confidence builds as observations accumulate and are validated
SEED_PATTERNS = [
    {
        "pattern_id":  "pat_analytical",
        "name":        "Analytical Communicator",
        "description": "High linguistic clarity paired with strong cross-modal consistency — a signal of structured, deliberate communication.",
        "dimensions":  ["avg_confidence", "avg_communication", "avg_consistency"],
        "threshold":   0.65,
    },
    {
        "pattern_id":  "pat_engaged",
        "name":        "Engaged Presence",
        "description": "Sustained active listening evidenced by eye contact alignment and consistent response depth.",
        "dimensions":  ["avg_engagement", "avg_consistency"],
        "threshold":   0.65,
    },
    {
        "pattern_id":  "pat_composed",
        "name":        "Composed Expert",
        "description": "Low physiological stress markers combined with high communication structure — a composure-led performance pattern.",
        "dimensions":  ["avg_communication", "avg_consistency"],
        "threshold":   0.70,
    },
    {
        "pattern_id":  "pat_high_energy",
        "name":        "High-Energy Responder",
        "description": "Elevated vocal energy and engagement with controlled stress — high-drive communicators.",
        "dimensions":  ["avg_confidence", "avg_engagement"],
        "threshold":   0.70,
    },
    {
        "pattern_id":  "pat_structured",
        "name":        "Structured Clarity",
        "description": "Strong communication score alongside consistency — systematic, well-organised responses.",
        "dimensions":  ["avg_communication", "avg_consistency", "avg_confidence"],
        "threshold":   0.72,
    },
    {
        "pattern_id":  "pat_resilient",
        "name":        "Resilient Performer",
        "description": "Above-average engagement even under stress — maintains presence under pressure.",
        "dimensions":  ["avg_engagement"],
        "threshold":   0.72,
    },
]


class ValidationEvent(BaseModel):
    event_id:     str
    session_id:   str
    candidate_id: Optional[str] = None
    org_id:       Optional[str] = None
    level:        ValidationLevel
    signal:       str
    confidence:   float
    metadata:     Dict[str, Any] = {}
    recorded_at:  float = Field(default_factory=time.time)


class PatternObservation(BaseModel):
    obs_id:                str
    session_id:            str
    candidate_id:          Optional[str] = None
    org_id:                Optional[str] = None
    avg_confidence:        float = 0.0
    avg_engagement:        float = 0.0
    avg_communication:     float = 0.0
    avg_stress:            float = 0.0
    avg_consistency:       float = 0.0
    overall_score:         float = 0.0
    validation_confidence: float = 0.20
    recorded_at:           float = Field(default_factory=time.time)


class BehavioralPattern(BaseModel):
    pattern_id:        str
    name:              str
    description:       str
    dimensions:        List[str]
    threshold:         float
    observation_count: int   = 0
    validated_count:   int   = 0
    confidence:        float = 0.0
    first_seen_at:     float = Field(default_factory=time.time)
    updated_at:        float = Field(default_factory=time.time)


class CoachingRecord(BaseModel):
    record_id:            str
    candidate_id:         str
    session_id:           str
    dimension:            str
    coaching_text:        str
    delivered_at:         float = Field(default_factory=time.time)
    follow_up_session_id: Optional[str]   = None
    improvement_delta:    Optional[float] = None
    outcome:              Optional[str]   = None  # "improved", "declined", "stable"


class OrgProfile(BaseModel):
    org_id:         str
    total_sessions: int              = 0
    mean_metrics:   Dict[str, float] = {}
    preferred_dims: List[str]        = []
    insight:        str              = ""
    confidence:     float            = 0.0
    updated_at:     float            = Field(default_factory=time.time)


class DimensionForecast(BaseModel):
    dimension:          str
    current_value:      float
    predicted_value:    float
    confidence_low:     float
    confidence_high:    float
    horizon_interviews: int
    trend:              str


class GrowthForecast(BaseModel):
    candidate_id:       str
    total_interviews:   int
    forecasts:          List[DimensionForecast]
    overall_trajectory: str
    confidence_note:    str
    generated_at:       float = Field(default_factory=time.time)


class PlatformKnowledgeStats(BaseModel):
    total_sessions_observed:    int
    total_validation_events:    int
    recruiter_validated:        int
    hiring_decisions:           int
    long_term_outcomes:         int
    patterns_discovered:        int
    patterns_validated:         int
    orgs_tracked:               int
    coaching_records:           int
    coaching_effectiveness_pct: Optional[float]
    knowledge_confidence:       float


# ── Request bodies ────────────────────────────────────────────────────────────

class CandidateFeedbackRequest(BaseModel):
    session_id:   str
    candidate_id: str
    helpful:      bool
    comment:      Optional[str] = None


class RecruiterFeedbackRequest(BaseModel):
    session_id: str
    org_id:     Optional[str] = None
    rating:     str           # helpful / not_helpful / needs_review / incorrect / missing_context
    comment:    Optional[str] = None


class HiringDecisionRequest(BaseModel):
    session_id:   str
    candidate_id: Optional[str] = None
    org_id:       Optional[str] = None
    decision:     str           # strong_hire / hire / hold / reject
    notes:        Optional[str] = None


class LongTermOutcomeRequest(BaseModel):
    session_id:        str
    candidate_id:      Optional[str] = None
    org_id:            Optional[str] = None
    outcome:           str            # retained / promoted / performance_review / probation / exit
    months_since_hire: Optional[int] = None
