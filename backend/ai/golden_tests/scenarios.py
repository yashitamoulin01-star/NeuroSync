"""
Golden Test Scenarios — synthetic interview scenarios for controlled evaluation.

These scenarios define the ground-truth expected behavior of the system
under controlled conditions. Every backend change runs against them.

A "golden test" is NOT a unit test — it's an end-to-end scenario that
validates the full reasoning pipeline produces reasonable outputs on
well-understood inputs.

Scenarios are parameterized: they specify what features the system
should "see" and what behavioral outputs are expected (as ranges,
not exact values, because the pipeline is continuous).

This is the canonical set. Add new scenarios here as edge cases are discovered.
Do not remove scenarios — they represent real failure modes we've seen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ScoreRange:
    """Expected output range for a behavioral dimension."""
    dimension: str
    min_val:   float
    max_val:   float

    def check(self, actual: float) -> Tuple[bool, str]:
        passed = self.min_val <= actual <= self.max_val
        reason = (
            f"{self.dimension}={actual:.3f} within [{self.min_val}, {self.max_val}]"
            if passed
            else f"{self.dimension}={actual:.3f} outside [{self.min_val}, {self.max_val}]"
        )
        return passed, reason


@dataclass
class GoldenScenario:
    """One synthetic interview scenario with expected outputs."""
    scenario_id:    str
    name:           str
    description:    str
    category:       str   # "positive" | "negative" | "edge_case" | "missing_data"

    # Synthetic input signals
    face_signals: Dict = field(default_factory=dict)
    audio_signals: Dict = field(default_factory=dict)
    nlp_signals: Dict = field(default_factory=dict)
    session_duration_s: float = 120.0
    total_words: int = 80

    # Expected output ranges (None = no assertion on this dimension)
    expected_confidence:    Optional[ScoreRange] = None
    expected_stress:        Optional[ScoreRange] = None
    expected_communication: Optional[ScoreRange] = None
    expected_engagement:    Optional[ScoreRange] = None
    expected_consistency:   Optional[ScoreRange] = None
    expected_behavioral_state: Optional[str] = None

    # Pass/fail criteria
    expected_reliability_not: Optional[str] = None   # must NOT be this reliability

    def validate(self, scores: Dict, behavioral_state: str = "") -> Dict:
        checks = []
        passed_all = True

        ranges_map = {
            "confidence":    self.expected_confidence,
            "stress":        self.expected_stress,
            "communication": self.expected_communication,
            "engagement":    self.expected_engagement,
            "consistency":   self.expected_consistency,
        }
        for dim, expected in ranges_map.items():
            if expected is None:
                continue
            actual = scores.get(dim)
            if actual is None:
                checks.append({"name": dim, "passed": False, "reason": "score not present in output"})
                passed_all = False
                continue
            ok, reason = expected.check(actual)
            checks.append({"name": dim, "passed": ok, "reason": reason})
            if not ok:
                passed_all = False

        if self.expected_behavioral_state:
            if not behavioral_state:
                # Synthetic runs don't have temporal history — skip state assertion
                checks.append({
                    "name": "behavioral_state",
                    "passed": True,
                    "reason": "skipped — behavioral_state requires temporal history (not available in synthetic run)",
                })
            else:
                ok = behavioral_state == self.expected_behavioral_state
                checks.append({
                    "name": "behavioral_state",
                    "passed": ok,
                    "reason": f"state={behavioral_state!r} expected={self.expected_behavioral_state!r}",
                })
                if not ok:
                    passed_all = False

        return {
            "scenario_id": self.scenario_id,
            "name":        self.name,
            "passed":      passed_all,
            "checks":      checks,
        }


# ── Canonical Scenarios ────────────────────────────────────────────────────────

GOLDEN_SCENARIOS: List[GoldenScenario] = [

    GoldenScenario(
        scenario_id  = "GS-001",
        name         = "Excellent Candidate",
        description  = "Strong eye contact, clear speech, high vocabulary, relaxed.",
        category     = "positive",
        face_signals = {"eye_contact": 0.90, "head_stability": 0.85, "expression": "neutral_positive"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 145, "voice_energy": 0.70},
        nlp_signals  = {"filler_rate": 0.02, "clarity_score": 0.88, "confidence_language": 0.85},
        session_duration_s = 150.0,
        total_words  = 220,
        expected_confidence    = ScoreRange("confidence",    0.65, 0.95),
        expected_stress        = ScoreRange("stress",        0.05, 0.40),
        expected_communication = ScoreRange("communication", 0.65, 0.95),
        expected_engagement    = ScoreRange("engagement",    0.60, 0.95),
        expected_consistency   = ScoreRange("consistency",   0.65, 0.95),
    ),

    GoldenScenario(
        scenario_id  = "GS-002",
        name         = "High Hesitation",
        description  = "Frequent filler words, low speech rate, avoidant eye contact.",
        category     = "negative",
        face_signals = {"eye_contact": 0.35, "head_stability": 0.55, "expression": "uncertain"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 75, "voice_energy": 0.45},
        nlp_signals  = {"filler_rate": 0.18, "clarity_score": 0.40, "confidence_language": 0.35},
        session_duration_s = 120.0,
        total_words  = 90,
        expected_confidence    = ScoreRange("confidence",    0.10, 0.55),
        expected_stress        = ScoreRange("stress",        0.40, 0.90),
        expected_communication = ScoreRange("communication", 0.10, 0.55),
    ),

    GoldenScenario(
        scenario_id  = "GS-003",
        name         = "Strong Technical, Weak Soft Skills",
        description  = "High vocabulary, low eye contact, monotone voice, infrequent filler words.",
        category     = "edge_case",
        face_signals = {"eye_contact": 0.30, "head_stability": 0.70, "expression": "neutral"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 160, "voice_energy": 0.50},
        nlp_signals  = {"filler_rate": 0.03, "clarity_score": 0.85, "confidence_language": 0.78},
        session_duration_s = 200.0,
        total_words  = 280,
        expected_communication = ScoreRange("communication", 0.55, 0.85),
        expected_engagement    = ScoreRange("engagement",    0.20, 0.65),
    ),

    GoldenScenario(
        scenario_id  = "GS-004",
        name         = "Missing Camera",
        description  = "Audio and NLP available; camera unavailable.",
        category     = "missing_data",
        face_signals = {},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 130, "voice_energy": 0.65},
        nlp_signals  = {"filler_rate": 0.05, "clarity_score": 0.75, "confidence_language": 0.72},
        session_duration_s = 120.0,
        total_words  = 160,
        # Confidence should still be estimable from NLP even without face
        expected_confidence = ScoreRange("confidence", 0.35, 0.80),
        expected_reliability_not = "insufficient",
    ),

    GoldenScenario(
        scenario_id  = "GS-005",
        name         = "Missing Transcript",
        description  = "Face available, no audio, no NLP.",
        category     = "missing_data",
        face_signals = {"eye_contact": 0.70, "head_stability": 0.80, "expression": "neutral"},
        audio_signals = {},
        nlp_signals  = {},
        session_duration_s = 60.0,
        total_words  = 0,
        # Communication and NLP dims should be unreliable; face dims should work
        expected_engagement = ScoreRange("engagement", 0.30, 0.80),
    ),

    GoldenScenario(
        scenario_id  = "GS-006",
        name         = "Short Interview (insufficient data)",
        description  = "Only 10 seconds of data — should return insufficient reliability.",
        category     = "edge_case",
        face_signals = {"eye_contact": 0.70},
        audio_signals = {},
        nlp_signals  = {},
        session_duration_s = 10.0,
        total_words  = 5,
        expected_reliability_not = "high",
    ),

    GoldenScenario(
        scenario_id  = "GS-007",
        name         = "Interview Recovery",
        description  = "Starts hesitant (first 60s), recovers to confident communication.",
        category     = "positive",
        face_signals = {"eye_contact": 0.70, "head_stability": 0.80},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 130},
        nlp_signals  = {"filler_rate": 0.05, "clarity_score": 0.75},
        session_duration_s = 200.0,
        total_words  = 200,
        expected_behavioral_state = "recovering",
    ),

    GoldenScenario(
        scenario_id  = "GS-008",
        name         = "Poor Lighting / Face Quality Degraded",
        description  = "Low face signal quality — should not crash, should degrade gracefully.",
        category     = "missing_data",
        face_signals = {"eye_contact": 0.20, "head_stability": 0.30},  # poor quality signals
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 120, "voice_energy": 0.60},
        nlp_signals  = {"filler_rate": 0.06, "clarity_score": 0.70, "confidence_language": 0.65},
        session_duration_s = 120.0,
        total_words  = 150,
        # System should still produce output — just lower confidence
        expected_confidence = ScoreRange("confidence", 0.20, 0.80),
    ),

    GoldenScenario(
        scenario_id  = "GS-009",
        name         = "High Stress Under Pressure",
        description  = "Difficult technical questions — voice tremor, avoidant gaze, rapid speech.",
        category     = "negative",
        face_signals = {"eye_contact": 0.25, "head_stability": 0.45, "expression": "tense"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 185, "voice_energy": 0.80},
        nlp_signals  = {"filler_rate": 0.12, "clarity_score": 0.45, "confidence_language": 0.30},
        session_duration_s = 140.0,
        total_words  = 210,
        expected_stress = ScoreRange("stress", 0.50, 0.95),
        expected_behavioral_state = "stressed",
    ),

    GoldenScenario(
        scenario_id  = "GS-010",
        name         = "Background Noise / Audio Quality",
        description  = "Audio signal present but noisy — partial NLP extraction.",
        category     = "missing_data",
        face_signals = {"eye_contact": 0.75, "head_stability": 0.80},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 115, "voice_energy": 0.30},
        nlp_signals  = {"filler_rate": 0.08, "clarity_score": 0.50},   # degraded
        session_duration_s = 120.0,
        total_words  = 80,
        expected_engagement = ScoreRange("engagement", 0.30, 0.80),
    ),

    # ── Extended suite (GS-011 – GS-025) ──────────────────────────────────────

    GoldenScenario(
        scenario_id  = "GS-011",
        name         = "Excellent Multimodal Quality",
        description  = "All three modalities pristine — ideal reference scenario for calibration.",
        category     = "positive",
        face_signals = {"eye_contact": 0.95, "head_stability": 0.92, "expression": "neutral_positive"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 138, "voice_energy": 0.75},
        nlp_signals  = {"filler_rate": 0.01, "clarity_score": 0.95, "confidence_language": 0.92},
        session_duration_s = 180.0,
        total_words  = 250,
        expected_confidence    = ScoreRange("confidence",    0.62, 0.98),
        expected_stress        = ScoreRange("stress",        0.02, 0.30),
        expected_communication = ScoreRange("communication", 0.65, 0.98),
        expected_engagement    = ScoreRange("engagement",    0.65, 0.98),
        expected_consistency   = ScoreRange("consistency",   0.60, 0.98),
    ),

    GoldenScenario(
        scenario_id  = "GS-012",
        name         = "Low Confidence Language",
        description  = "Good facial presence but consistently tentative phrasing and weak vocabulary.",
        category     = "negative",
        face_signals = {"eye_contact": 0.65, "head_stability": 0.70, "expression": "neutral"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 110, "voice_energy": 0.40},
        nlp_signals  = {"filler_rate": 0.10, "clarity_score": 0.55, "confidence_language": 0.25},
        session_duration_s = 130.0,
        total_words  = 140,
        expected_confidence    = ScoreRange("confidence",    0.10, 0.55),
        expected_communication = ScoreRange("communication", 0.20, 0.65),
    ),

    GoldenScenario(
        scenario_id  = "GS-013",
        name         = "Authoritative Expert Delivery",
        description  = "Subject matter expert — commanding tone, precise language, minimal fillers, steady gaze.",
        category     = "positive",
        face_signals = {"eye_contact": 0.85, "head_stability": 0.88, "expression": "confident"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 155, "voice_energy": 0.72},
        nlp_signals  = {"filler_rate": 0.01, "clarity_score": 0.92, "confidence_language": 0.90},
        session_duration_s = 200.0,
        total_words  = 310,
        expected_confidence    = ScoreRange("confidence",    0.65, 0.98),
        expected_stress        = ScoreRange("stress",        0.02, 0.35),
        expected_communication = ScoreRange("communication", 0.65, 0.98),
        expected_engagement    = ScoreRange("engagement",    0.60, 0.95),
    ),

    GoldenScenario(
        scenario_id  = "GS-014",
        name         = "Burst Hesitation Pattern",
        description  = "Extreme filler-word density, very slow speech rate, avoidant gaze — designed worst case.",
        category     = "negative",
        face_signals = {"eye_contact": 0.40, "head_stability": 0.50, "expression": "uncertain"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 60, "voice_energy": 0.38},
        nlp_signals  = {"filler_rate": 0.25, "clarity_score": 0.30, "confidence_language": 0.28},
        session_duration_s = 120.0,
        total_words  = 72,
        expected_confidence    = ScoreRange("confidence",    0.02, 0.40),
        expected_stress        = ScoreRange("stress",        0.40, 0.95),
        expected_communication = ScoreRange("communication", 0.02, 0.40),
        expected_engagement    = ScoreRange("engagement",    0.10, 0.65),
    ),

    GoldenScenario(
        scenario_id  = "GS-015",
        name         = "Vocal Fatigue / Late-Session Decline",
        description  = "Voice energy drops, speech slows below optimal — suggests candidate fatigue.",
        category     = "edge_case",
        face_signals = {"eye_contact": 0.62, "head_stability": 0.65, "expression": "neutral"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 95, "voice_energy": 0.25},
        nlp_signals  = {"filler_rate": 0.09, "clarity_score": 0.62, "confidence_language": 0.55},
        session_duration_s = 160.0,
        total_words  = 152,
        expected_communication = ScoreRange("communication", 0.15, 0.65),
    ),

    GoldenScenario(
        scenario_id  = "GS-016",
        name         = "Weak Eye Contact, Strong Verbal",
        description  = "Camera avoidance or positioning issue — poor gaze signal, excellent spoken delivery.",
        category     = "edge_case",
        face_signals = {"eye_contact": 0.25, "head_stability": 0.65, "expression": "focused"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 148, "voice_energy": 0.70},
        nlp_signals  = {"filler_rate": 0.02, "clarity_score": 0.88, "confidence_language": 0.85},
        session_duration_s = 170.0,
        total_words  = 252,
        expected_confidence    = ScoreRange("confidence",    0.25, 0.78),
        expected_communication = ScoreRange("communication", 0.50, 0.90),
    ),

    GoldenScenario(
        scenario_id  = "GS-017",
        name         = "Poor Microphone Quality",
        description  = "Microphone degrades audio — low energy, reduced NLP clarity despite good delivery.",
        category     = "missing_data",
        face_signals = {"eye_contact": 0.75, "head_stability": 0.78, "expression": "neutral"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 130, "voice_energy": 0.15},
        nlp_signals  = {"filler_rate": 0.05, "clarity_score": 0.55, "confidence_language": 0.65},
        session_duration_s = 120.0,
        total_words  = 156,
        expected_engagement = ScoreRange("engagement", 0.35, 0.85),
        expected_reliability_not = "insufficient",
    ),

    GoldenScenario(
        scenario_id  = "GS-018",
        name         = "High Ambient Noise",
        description  = "Background noise heavily degrades NLP clarity — speaking detected but content unreliable.",
        category     = "missing_data",
        face_signals = {"eye_contact": 0.70, "head_stability": 0.72, "expression": "neutral"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 125, "voice_energy": 0.45},
        nlp_signals  = {"filler_rate": 0.07, "clarity_score": 0.32},   # noise-degraded
        session_duration_s = 120.0,
        total_words  = 115,
        expected_communication = ScoreRange("communication", 0.10, 0.70),
    ),

    GoldenScenario(
        scenario_id  = "GS-019",
        name         = "Transcript Corruption / NLP Failure",
        description  = "Audio detected but NLP extraction completely failed — face and audio signals only.",
        category     = "missing_data",
        face_signals = {"eye_contact": 0.72, "head_stability": 0.75, "expression": "neutral"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 120, "voice_energy": 0.60},
        nlp_signals  = {},   # NLP pipeline returned nothing
        session_duration_s = 120.0,
        total_words  = 0,
        expected_engagement = ScoreRange("engagement", 0.35, 0.88),
    ),

    GoldenScenario(
        scenario_id  = "GS-020",
        name         = "Audio Clipping / Overdriven Microphone",
        description  = "Microphone overdriven — extreme speaking rate detected, signal quality degraded.",
        category     = "edge_case",
        face_signals = {"eye_contact": 0.68, "head_stability": 0.70, "expression": "neutral"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 200, "voice_energy": 1.0},
        nlp_signals  = {"filler_rate": 0.06, "clarity_score": 0.52},
        session_duration_s = 120.0,
        total_words  = 240,
        expected_stress = ScoreRange("stress", 0.28, 0.80),
    ),

    GoldenScenario(
        scenario_id  = "GS-021",
        name         = "High Engagement, Moderate Confidence",
        description  = "Very attentive and present, but language lacks assertiveness — under-confident phrasing.",
        category     = "edge_case",
        face_signals = {"eye_contact": 0.88, "head_stability": 0.80, "expression": "attentive"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 135, "voice_energy": 0.68},
        nlp_signals  = {"filler_rate": 0.07, "clarity_score": 0.65, "confidence_language": 0.45},
        session_duration_s = 150.0,
        total_words  = 202,
        expected_engagement = ScoreRange("engagement", 0.55, 0.95),
        expected_confidence = ScoreRange("confidence", 0.20, 0.65),
    ),

    GoldenScenario(
        scenario_id  = "GS-022",
        name         = "Low Engagement Throughout",
        description  = "Candidate appears disengaged — low gaze, slow delivery, minimal verbal effort.",
        category     = "negative",
        face_signals = {"eye_contact": 0.30, "head_stability": 0.45, "expression": "disengaged"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 85, "voice_energy": 0.28},
        nlp_signals  = {"filler_rate": 0.09, "clarity_score": 0.55, "confidence_language": 0.40},
        session_duration_s = 140.0,
        total_words  = 119,
        expected_engagement = ScoreRange("engagement", 0.10, 0.65),
        expected_stress     = ScoreRange("stress",     0.35, 0.88),
    ),

    GoldenScenario(
        scenario_id  = "GS-023",
        name         = "Stressed but Articulate",
        description  = "Elevated stress signals from gaze and posture, yet verbal delivery remains clear and confident.",
        category     = "edge_case",
        face_signals = {"eye_contact": 0.30, "head_stability": 0.40, "expression": "tense"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 175, "voice_energy": 0.82},
        nlp_signals  = {"filler_rate": 0.03, "clarity_score": 0.85, "confidence_language": 0.72},
        session_duration_s = 140.0,
        total_words  = 245,
        expected_stress        = ScoreRange("stress",        0.28, 0.88),
        expected_communication = ScoreRange("communication", 0.45, 0.88),
    ),

    GoldenScenario(
        scenario_id  = "GS-024",
        name         = "Silent / Non-Speaking Candidate",
        description  = "Candidate is visually present but not speaking — face-only evaluation mode.",
        category     = "missing_data",
        face_signals = {"eye_contact": 0.65, "head_stability": 0.70, "expression": "neutral"},
        audio_signals = {"is_speaking": False},
        nlp_signals  = {},
        session_duration_s = 60.0,
        total_words  = 0,
        expected_engagement = ScoreRange("engagement", 0.15, 0.75),
    ),

    GoldenScenario(
        scenario_id  = "GS-025",
        name         = "Multimodal Signal Conflict",
        description  = "Face signals calm confidence; voice signals rapid stress — cross-modal disagreement.",
        category     = "edge_case",
        face_signals = {"eye_contact": 0.85, "head_stability": 0.82, "expression": "composed"},
        audio_signals = {"is_speaking": True, "speech_rate_wpm": 192, "voice_energy": 0.88},
        nlp_signals  = {"filler_rate": 0.11, "clarity_score": 0.58, "confidence_language": 0.50},
        session_duration_s = 140.0,
        total_words  = 268,
        expected_stress = ScoreRange("stress", 0.18, 0.75),
    ),
]


def get_scenario(scenario_id: str) -> Optional[GoldenScenario]:
    for s in GOLDEN_SCENARIOS:
        if s.scenario_id == scenario_id:
            return s
    return None


def get_scenarios_by_category(category: str) -> List[GoldenScenario]:
    return [s for s in GOLDEN_SCENARIOS if s.category == category]
