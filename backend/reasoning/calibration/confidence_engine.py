"""
Confidence Calibration Engine — expresses certainty about the backend's own conclusions.

Current system outputs:   Confidence 82%
Calibrated system outputs:
  Behavior Estimate:       82%
  Prediction Confidence:   91%
  Evidence Quality:        88%
  Signal Quality:          excellent
  Cross-Modal Agreement:   94%
  Reasoning Confidence:    high

The backend should not only report what it observed — it should report
how certain it is about what it observed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.models.evidence import ModalityQuality, PredictionReliability


@dataclass
class CalibrationResult:
    behavior_estimate:     Dict[str, float]  # dimension → calibrated score
    prediction_confidence: float             # 0–1
    evidence_quality:      float             # 0–1
    signal_quality:        str               # "poor" | "fair" | "good" | "excellent"
    model_agreement:       float             # cross-modal agreement
    reasoning_confidence:  str               # "low" | "medium" | "high"
    calibration_notes:     List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "behavior_estimate":     {k: round(v, 3) for k, v in self.behavior_estimate.items()},
            "prediction_confidence": round(self.prediction_confidence, 3),
            "evidence_quality":      round(self.evidence_quality, 3),
            "signal_quality":        self.signal_quality,
            "model_agreement":       round(self.model_agreement, 3),
            "reasoning_confidence":  self.reasoning_confidence,
            "calibration_notes":     self.calibration_notes,
        }


def _quality_label(score: float) -> str:
    if score >= 0.85: return "excellent"
    if score >= 0.65: return "good"
    if score >= 0.40: return "fair"
    return "poor"


def _conf_label(score: float) -> str:
    if score >= 0.75: return "high"
    if score >= 0.45: return "medium"
    return "low"


_RELIABILITY_WEIGHT = {
    PredictionReliability.HIGH:         0.90,
    PredictionReliability.MEDIUM:       0.65,
    PredictionReliability.LOW:          0.35,
    PredictionReliability.INSUFFICIENT: 0.15,
}

_DIM_ADJUST_MAP = {
    "reduce_stress":        "stress",
    "boost_confidence":     "confidence",
    "boost_communication":  "communication",
    "normalize_engagement": "engagement",
}


def calibrate(
    scores:              Dict[str, float],
    reliability:         PredictionReliability,
    modality_quality:    Optional[ModalityQuality],
    conflict_score:      float,
    cross_modal_agreement: float,
    evidence_count:      int,
    rule_adjustments:    Dict[str, float],   # dimension → delta (from rule engine)
    elapsed_seconds:     float,
) -> CalibrationResult:
    """
    Produce a calibrated estimate with meta-confidence about the conclusion.

    Rule adjustments are applied first, then meta-confidence is computed
    from reliability, signal quality, time elapsed, and evidence conflict.
    """
    notes: List[str] = []

    # Apply rule adjustments to raw scores
    calibrated = dict(scores)
    for dim, delta in rule_adjustments.items():
        if dim in calibrated and delta != 0.0:
            calibrated[dim] = max(0.0, min(1.0, calibrated[dim] + delta))
            sign = "+" if delta > 0 else ""
            notes.append(f"Context rule adjusted {dim}: {sign}{delta:.2f}")

    # Evidence quality: evidence count + modality coverage + active modality count
    mq = modality_quality
    active_mods = sum([
        1 if (mq and mq.face_available)  else 0,
        1 if (mq and mq.audio_available) else 0,
        1 if (mq and mq.nlp_available)   else 0,
    ])
    coverage = mq.evidence_coverage if mq else 0.5
    ev_quality = (
        0.40 * min(1.0, evidence_count / 12.0) +
        0.30 * coverage +
        0.30 * (active_mods / 3.0)
    )

    # Prediction confidence
    rel_w     = _RELIABILITY_WEIGHT.get(reliability, 0.5)
    conflict_p = conflict_score * 0.30   # high conflict reduces certainty
    time_w    = min(1.0, elapsed_seconds / 90.0)   # full weight after 90s

    pred_conf = (
        0.40 * rel_w +
        0.25 * cross_modal_agreement +
        0.20 * time_w +
        0.15 * ev_quality
    ) - conflict_p
    pred_conf = max(0.0, min(1.0, pred_conf))

    if conflict_score > 0.40:
        notes.append(
            f"Cross-modal conflicts ({conflict_score:.0%}) reduce prediction certainty."
        )
    if active_mods < 2:
        notes.append(f"Only {active_mods} modality active — wider uncertainty intervals.")
    if elapsed_seconds < 30:
        notes.append("Early session — estimates will improve with more data.")

    return CalibrationResult(
        behavior_estimate     = calibrated,
        prediction_confidence = pred_conf,
        evidence_quality      = ev_quality,
        signal_quality        = _quality_label(ev_quality),
        model_agreement       = round(cross_modal_agreement, 3),
        reasoning_confidence  = _conf_label(pred_conf),
        calibration_notes     = notes,
    )
