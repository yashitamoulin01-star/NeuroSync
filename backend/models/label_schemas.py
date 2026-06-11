from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
import time


class ConfidenceLabel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class StressLabel(str, Enum):
    CALM = "calm"
    MODERATE = "moderate"
    HIGH = "high"


class CommunicationLabel(str, Enum):
    STRONG = "strong"
    CLEAR = "clear"
    HESITANT = "hesitant"
    WEAK = "weak"


class EyeContactLabel(str, Enum):
    STABLE = "stable"
    NERVOUS = "nervous"
    AVOIDANT = "avoidant"


class BehavioralEvent(str, Enum):
    STRESS_SPIKE = "stress_spike"
    HESITATION_BURST = "hesitation_burst"
    GAZE_AVERSION = "gaze_aversion"
    CONFIDENCE_DROP = "confidence_drop"
    STRONG_DELIVERY = "strong_delivery"
    SPEECH_INSTABILITY = "speech_instability"
    EXCESSIVE_PAUSE = "excessive_pause"
    FILLER_BURST = "filler_burst"


class TemporalLabel(BaseModel):
    start_time: float
    end_time: float
    confidence_label: ConfidenceLabel = ConfidenceLabel.MEDIUM
    stress_label: StressLabel = StressLabel.MODERATE
    eye_contact_label: EyeContactLabel = EyeContactLabel.STABLE
    communication_label: CommunicationLabel = CommunicationLabel.CLEAR
    behavioral_events: List[BehavioralEvent] = []
    notes: str = ""


class OverallLabel(BaseModel):
    confidence_score: int = Field(50, ge=0, le=100)
    stress_level: int = Field(50, ge=0, le=100)
    communication_quality: CommunicationLabel = CommunicationLabel.CLEAR
    hesitation_level: str = "medium"           # low | medium | high
    eye_contact_quality: EyeContactLabel = EyeContactLabel.STABLE
    overall_performance: int = Field(50, ge=0, le=100)
    summary_notes: str = ""


class SessionLabel(BaseModel):
    session_id: str
    labeled_at: float = Field(default_factory=time.time)
    labeled_by: str = "human"
    schema_version: str = "1.0"
    overall: OverallLabel = Field(default_factory=OverallLabel)
    temporal_labels: List[TemporalLabel] = []
    is_complete: bool = False


class LabelSubmitRequest(BaseModel):
    session_id: str = ""
    labeled_by: str = "human"
    overall: OverallLabel
    temporal_labels: List[TemporalLabel] = []
