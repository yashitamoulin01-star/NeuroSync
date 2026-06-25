"""
Pydantic models for the Adaptive Behavioral Memory Engine.

Every learned metric is stored as a MetricTrace — an EMA value paired
with observation metadata (count, confidence, variance).  The profile
JSON stored in SQLite is the serialized form of CandidateProfile.
"""

from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import time


class MetricTrace(BaseModel):
    """A single learned behavioral metric with EMA state."""
    value: float = 0.0
    observation_count: int = 0
    confidence: float = 0.0          # 0 → 1, grows with more observations
    variance: float = 0.0
    last_updated: float = Field(default_factory=time.time)

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.8:   return "high"
        if self.confidence >= 0.4:   return "medium"
        if self.confidence >= 0.1:   return "low"
        return "insufficient"


class VoiceMemory(BaseModel):
    speech_rate:      MetricTrace = Field(default_factory=MetricTrace)
    pause_ratio:      MetricTrace = Field(default_factory=MetricTrace)
    filler_ratio:     MetricTrace = Field(default_factory=MetricTrace)
    vocal_stability:  MetricTrace = Field(default_factory=MetricTrace)
    energy_level:     MetricTrace = Field(default_factory=MetricTrace)
    voice_stress:     MetricTrace = Field(default_factory=MetricTrace)


class FaceMemory(BaseModel):
    eye_contact:     MetricTrace = Field(default_factory=MetricTrace)
    head_stability:  MetricTrace = Field(default_factory=MetricTrace)
    facial_tension:  MetricTrace = Field(default_factory=MetricTrace)
    blink_rate:      MetricTrace = Field(default_factory=MetricTrace)


class LanguageMemory(BaseModel):
    clarity_score:    MetricTrace = Field(default_factory=MetricTrace)
    hesitation_score: MetricTrace = Field(default_factory=MetricTrace)
    sentiment:        MetricTrace = Field(default_factory=MetricTrace)


class BehavioralMemory(BaseModel):
    avg_confidence:    MetricTrace = Field(default_factory=MetricTrace)
    avg_engagement:    MetricTrace = Field(default_factory=MetricTrace)
    avg_communication: MetricTrace = Field(default_factory=MetricTrace)
    avg_stress:        MetricTrace = Field(default_factory=MetricTrace)
    avg_consistency:   MetricTrace = Field(default_factory=MetricTrace)


class InterviewHistoryEntry(BaseModel):
    session_id:      str
    conducted_at:    float
    duration:        float = 0.0
    overall_score:   float = 0.0
    avg_confidence:  float = 0.0
    avg_stress:      float = 0.0
    avg_engagement:  float = 0.0
    avg_communication: float = 0.0
    avg_consistency:   float = 0.0
    recommendation:  str = ""


class CandidateProfile(BaseModel):
    candidate_id:      str
    voice:             VoiceMemory     = Field(default_factory=VoiceMemory)
    face:              FaceMemory      = Field(default_factory=FaceMemory)
    language:          LanguageMemory  = Field(default_factory=LanguageMemory)
    behavioral:        BehavioralMemory = Field(default_factory=BehavioralMemory)
    total_interviews:  int = 0
    first_seen_at:     float = Field(default_factory=time.time)
    updated_at:        float = Field(default_factory=time.time)
    learning_paused:   bool = False

    def overall_growth_score(self) -> float:
        """Simple aggregate growth proxy — mean confidence across all behavioral traces."""
        traces = [
            self.behavioral.avg_confidence,
            self.behavioral.avg_engagement,
            self.behavioral.avg_communication,
            self.behavioral.avg_consistency,
        ]
        if not any(t.observation_count > 0 for t in traces):
            return 0.0
        active = [t for t in traces if t.observation_count > 0]
        return round(sum(t.value for t in active) / len(active), 4)


# ── Response shapes ───────────────────────────────────────────────────────────

class GrowthResponse(BaseModel):
    candidate_id: str
    total_interviews: int
    baseline: Dict[str, float]        # dim → current EMA value
    confidence_levels: Dict[str, str] # dim → "high/medium/low/insufficient"
    trend_direction: Dict[str, str]   # dim → "improving/declining/stable"
    coaching_focus: List[str]         # suggested focus areas
    overall_growth_score: float
    history_summary: List[Dict]       # lightweight per-interview summary


class ProfileUpdateRequest(BaseModel):
    candidate_id: str
    session_id: str
