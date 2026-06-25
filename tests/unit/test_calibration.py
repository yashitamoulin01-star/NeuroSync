"""
Unit tests for the Confidence Calibration Engine — Phase 3.
"""

from __future__ import annotations

import pytest

from backend.models.evidence import ModalityQuality, PredictionReliability
from backend.reasoning.calibration.confidence_engine import CalibrationResult, calibrate


def _quality(face=True, audio=True, nlp=True, words=60) -> ModalityQuality:
    return ModalityQuality(
        face_available=face,  face_quality=0.80 if face else 0.0,
        audio_available=audio, audio_quality=0.75 if audio else 0.0,
        nlp_available=nlp,    nlp_quality=0.70 if nlp else 0.0,
        transcript_words=words,
        evidence_coverage=0.85 if nlp else 0.40,
    )


_BASE_SCORES = {
    "confidence": 0.72,
    "stress":     0.30,
    "communication": 0.65,
    "engagement": 0.60,
    "consistency": 0.70,
}


class TestCalibrateReturnType:

    def test_returns_calibration_result(self):
        result = calibrate(
            scores=_BASE_SCORES,
            reliability=PredictionReliability.HIGH,
            modality_quality=_quality(),
            conflict_score=0.05,
            cross_modal_agreement=0.88,
            evidence_count=12,
            rule_adjustments={},
            elapsed_seconds=120.0,
        )
        assert isinstance(result, CalibrationResult)

    def test_behavior_estimate_has_all_dims(self):
        result = calibrate(
            scores=_BASE_SCORES,
            reliability=PredictionReliability.MEDIUM,
            modality_quality=_quality(),
            conflict_score=0.10,
            cross_modal_agreement=0.75,
            evidence_count=8,
            rule_adjustments={},
            elapsed_seconds=90.0,
        )
        for dim in ("confidence", "stress", "communication", "engagement", "consistency"):
            assert dim in result.behavior_estimate
            val = result.behavior_estimate[dim]
            assert 0.0 <= val <= 1.0


class TestPredictionConfidence:

    def test_high_quality_gives_high_confidence(self):
        result = calibrate(
            scores=_BASE_SCORES,
            reliability=PredictionReliability.HIGH,
            modality_quality=_quality(words=120),
            conflict_score=0.0,
            cross_modal_agreement=1.0,
            evidence_count=15,
            rule_adjustments={},
            elapsed_seconds=180.0,
        )
        assert result.prediction_confidence > 0.55

    def test_conflict_reduces_confidence(self):
        low_conflict = calibrate(
            scores=_BASE_SCORES,
            reliability=PredictionReliability.HIGH,
            modality_quality=_quality(),
            conflict_score=0.0,
            cross_modal_agreement=0.90,
            evidence_count=12,
            rule_adjustments={},
            elapsed_seconds=120.0,
        )
        high_conflict = calibrate(
            scores=_BASE_SCORES,
            reliability=PredictionReliability.HIGH,
            modality_quality=_quality(),
            conflict_score=0.80,
            cross_modal_agreement=0.40,
            evidence_count=12,
            rule_adjustments={},
            elapsed_seconds=120.0,
        )
        assert high_conflict.prediction_confidence < low_conflict.prediction_confidence

    def test_insufficient_quality_low_confidence(self):
        result = calibrate(
            scores=_BASE_SCORES,
            reliability=PredictionReliability.LOW,
            modality_quality=_quality(face=False, audio=False, words=5),
            conflict_score=0.5,
            cross_modal_agreement=0.3,
            evidence_count=2,
            rule_adjustments={},
            elapsed_seconds=10.0,
        )
        assert result.prediction_confidence < 0.5


class TestRuleAdjustments:

    def test_positive_rule_adjustments_applied(self):
        base = calibrate(
            scores=_BASE_SCORES,
            reliability=PredictionReliability.MEDIUM,
            modality_quality=_quality(),
            conflict_score=0.1,
            cross_modal_agreement=0.75,
            evidence_count=8,
            rule_adjustments={},
            elapsed_seconds=90.0,
        )
        adjusted = calibrate(
            scores=_BASE_SCORES,
            reliability=PredictionReliability.MEDIUM,
            modality_quality=_quality(),
            conflict_score=0.1,
            cross_modal_agreement=0.75,
            evidence_count=8,
            rule_adjustments={"confidence": 0.10},
            elapsed_seconds=90.0,
        )
        assert adjusted.behavior_estimate["confidence"] >= base.behavior_estimate["confidence"]


class TestSignalQualityLabels:

    def test_excellent_signal_label(self):
        result = calibrate(
            scores=_BASE_SCORES,
            reliability=PredictionReliability.HIGH,
            modality_quality=_quality(words=120),
            conflict_score=0.0,
            cross_modal_agreement=1.0,
            evidence_count=20,
            rule_adjustments={},
            elapsed_seconds=300.0,
        )
        assert result.signal_quality in ("excellent", "good")

    def test_poor_signal_label(self):
        result = calibrate(
            scores=_BASE_SCORES,
            reliability=PredictionReliability.LOW,
            modality_quality=_quality(face=False, audio=False, words=0),
            conflict_score=0.9,
            cross_modal_agreement=0.1,
            evidence_count=1,
            rule_adjustments={},
            elapsed_seconds=5.0,
        )
        assert result.signal_quality in ("poor", "fair")
