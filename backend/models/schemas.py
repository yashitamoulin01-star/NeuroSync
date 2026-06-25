from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
import time

from backend.models.evidence import BehavioralEvidence, ModalityQuality, ScoreBreakdown


class ModalityType(str, Enum):
    FACE = "face"
    AUDIO = "audio"
    NLP = "nlp"
    FUSION = "fusion"


# ── Face ──────────────────────────────────────────────────────────────────────

class GazeDirection(str, Enum):
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class FaceMetrics(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    eye_contact_score: float = Field(0.0, ge=0.0, le=1.0)
    gaze_direction: GazeDirection = GazeDirection.UNKNOWN
    blink_rate: float = 0.0                  # blinks per minute
    head_stability: float = Field(0.0, ge=0.0, le=1.0)
    facial_tension: float = Field(0.0, ge=0.0, le=1.0)
    expression_label: str = "neutral"
    face_detected: bool = False


# ── Audio ─────────────────────────────────────────────────────────────────────

class AudioMetrics(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    pitch_mean: float = 0.0
    pitch_variance: float = 0.0
    speaking_pace: float = 0.0              # words per minute
    pause_ratio: float = Field(0.0, ge=0.0, le=1.0)
    energy_level: float = Field(0.0, ge=0.0, le=1.0)
    vocal_stability: float = Field(0.0, ge=0.0, le=1.0)
    voice_stress_score: float = Field(0.0, ge=0.0, le=1.0)
    is_speaking: bool = False


# ── NLP ───────────────────────────────────────────────────────────────────────

class FillerWordEvent(BaseModel):
    word: str
    timestamp: float
    position_in_transcript: int


class NLPMetrics(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    transcript_chunk: str = ""
    filler_word_count: int = 0
    filler_words_detected: List[FillerWordEvent] = []
    confidence_language_score: float = Field(0.0, ge=0.0, le=1.0)
    hesitation_score: float = Field(0.0, ge=0.0, le=1.0)
    clarity_score: float = Field(0.0, ge=0.0, le=1.0)
    sentiment_polarity: float = Field(0.0, ge=-1.0, le=1.0)
    words_per_chunk: int = 0


# ── Fusion ────────────────────────────────────────────────────────────────────

class BehavioralInsight(BaseModel):
    type: str                               # e.g. "stress_spike", "low_eye_contact"
    description: str                        # human-readable explanation
    severity: float = Field(0.0, ge=0.0, le=1.0)
    timestamp: float = Field(default_factory=time.time)
    modalities_involved: List[ModalityType] = []


class FusedAnalytics(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    session_id: str

    # Composite scores (all 0–1)
    overall_confidence: float = Field(0.0, ge=0.0, le=1.0)
    communication_quality: float = Field(0.0, ge=0.0, le=1.0)
    engagement_score: float = Field(0.0, ge=0.0, le=1.0)
    stress_level: float = Field(0.0, ge=0.0, le=1.0)
    behavioral_consistency: float = Field(0.0, ge=0.0, le=1.0)

    face: Optional[FaceMetrics] = None
    audio: Optional[AudioMetrics] = None
    nlp: Optional[NLPMetrics] = None

    insights: List[BehavioralInsight] = []

    # Reasoning layer outputs — every score is now traceable
    evidence:       List[BehavioralEvidence] = Field(default_factory=list)
    score_breakdown: Optional[ScoreBreakdown] = None
    data_quality:   Optional[ModalityQuality] = None

    # Running session stats
    session_duration: float = 0.0
    total_words_spoken: int = 0
    total_filler_words: int = 0
    avg_speaking_pace: float = 0.0

    # Phase 3: temporal intelligence and explainability
    behavioral_state:   Optional[str]            = None  # BehavioralState.value
    behavioral_pattern: Optional[str]            = None  # BehavioralPattern.value
    segment:            Optional[str]            = None  # interview segment
    trends:             Optional[Dict[str, str]] = None  # dimension → Trend.value
    conflict_count:     int                      = 0
    calibration:        Optional[Dict[str, Any]] = None  # CalibrationResult.to_dict()
    explanation:        Optional[Dict[str, Any]] = None  # FullExplanation — REST only
    decision_trace:     Optional[Dict[str, Any]] = None  # DecisionTrace — REST only


# ── WebSocket message envelope ────────────────────────────────────────────────

class WSMessageType(str, Enum):
    ANALYTICS_UPDATE = "analytics_update"
    TRANSCRIPT_UPDATE = "transcript_update"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class WSMessage(BaseModel):
    type: WSMessageType
    session_id: str
    payload: dict = {}
    timestamp: float = Field(default_factory=time.time)


# ── Session ───────────────────────────────────────────────────────────────────

class SessionConfig(BaseModel):
    user_id: Optional[str] = None
    session_name: str = "Interview Session"
    mode: str = "interview"                  # interview | coaching | presentation


class SessionSummary(BaseModel):
    session_id: str
    duration: float
    avg_confidence: float
    avg_eye_contact: float
    avg_stress: float
    total_filler_words: int
    avg_speaking_pace: float
    avg_communication_quality: float
    top_insights: List[BehavioralInsight] = []
    transcript: str = ""
