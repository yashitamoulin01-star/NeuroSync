"""
Behavioral reasoner — converts an evidence pool into calibrated per-dimension scores.

Scoring model (asymptotic pull):
    positive → score += contribution * (1 - score)   # approaches 1.0
    negative → score -= contribution * score          # approaches 0.0

This keeps every score in [0, 1] without clamping and gives diminishing returns
on stacked same-polarity evidence, which matches real human behavior.

Baselines represent the neutral prior for each dimension before evidence is
observed. They are NOT fallback values — they are the starting point.
"""

from typing import List, Dict

from backend.core.interfaces.reasoning import IReasoningEngine
from backend.models.evidence import (
    BehavioralEvidence,
    EvidenceDimension,
    EvidencePolarity,
    ModalityQuality,
    PredictionReliability,
    ScoreBreakdown,
)

_BASELINES: Dict[EvidenceDimension, float] = {
    EvidenceDimension.CONFIDENCE:    0.50,
    EvidenceDimension.STRESS:        0.28,
    EvidenceDimension.COMMUNICATION: 0.55,
    EvidenceDimension.ENGAGEMENT:    0.50,
    EvidenceDimension.CONSISTENCY:   0.65,
}

# For descending dimensions (lower is better) the polarity semantics invert:
#   POSITIVE evidence → decreases the score (good signal means less of it)
#   NEGATIVE evidence → increases the score (bad signal means more of it)
_DESCENDING_DIMS = {EvidenceDimension.STRESS}

# Reliability thresholds (0–1 composite score)
_HIGH_THRESHOLD   = 0.68
_MEDIUM_THRESHOLD = 0.40


class BehavioralReasoner(IReasoningEngine):

    def reason(
        self,
        evidence: List[BehavioralEvidence],
        quality: ModalityQuality,
        session_duration: float = 0.0,
        total_words: int = 0,
    ) -> ScoreBreakdown:
        reliability = self._assess_reliability(
            evidence=evidence,
            quality=quality,
            session_duration=session_duration,
            total_words=total_words,
        )

        if reliability == PredictionReliability.INSUFFICIENT:
            # Return baselines so the frontend can render gracefully.
            # reliability="insufficient" is the signal to show "not enough data."
            return ScoreBreakdown(
                confidence    = _BASELINES[EvidenceDimension.CONFIDENCE],
                stress        = _BASELINES[EvidenceDimension.STRESS],
                communication = _BASELINES[EvidenceDimension.COMMUNICATION],
                engagement    = _BASELINES[EvidenceDimension.ENGAGEMENT],
                consistency   = _BASELINES[EvidenceDimension.CONSISTENCY],
                reliability   = PredictionReliability.INSUFFICIENT,
                evidence_count    = len(evidence),
                evidence_coverage = quality.evidence_coverage,
            )

        by_dim: Dict[EvidenceDimension, List[BehavioralEvidence]] = {
            d: [] for d in EvidenceDimension
        }
        for ev in evidence:
            by_dim[ev.dimension].append(ev)

        scores: Dict[EvidenceDimension, float] = {}
        for dim in EvidenceDimension:
            scores[dim] = self._score_dimension(dim, by_dim[dim], quality)

        dims_with_evidence = sum(1 for d in EvidenceDimension if by_dim[d])
        coverage = dims_with_evidence / len(EvidenceDimension)

        return ScoreBreakdown(
            confidence    = round(scores[EvidenceDimension.CONFIDENCE],    4),
            stress        = round(scores[EvidenceDimension.STRESS],        4),
            communication = round(scores[EvidenceDimension.COMMUNICATION], 4),
            engagement    = round(scores[EvidenceDimension.ENGAGEMENT],    4),
            consistency   = round(scores[EvidenceDimension.CONSISTENCY],   4),
            reliability   = reliability,
            evidence_count    = len(evidence),
            evidence_coverage = round(coverage, 3),
        )

    def _score_dimension(
        self,
        dim: EvidenceDimension,
        items: List[BehavioralEvidence],
        quality: ModalityQuality,
    ) -> float:
        score = _BASELINES[dim]

        # No evidence for this dimension — return baseline unchanged.
        # The caller knows this dimension was unobserved via evidence_coverage.
        if not items:
            return score

        descending = dim in _DESCENDING_DIMS

        # Sort: strongest pull first so the asymptotic model is deterministic.
        # For descending dimensions (STRESS) polarity semantics invert so that
        # POSITIVE evidence ("calm voice") reduces the score toward 0.
        for ev in sorted(items, key=lambda e: e.contribution, reverse=True):
            pulls_up = (ev.polarity == EvidencePolarity.POSITIVE) != descending
            if pulls_up:
                score += ev.contribution * (1.0 - score)
            else:
                score -= ev.contribution * score

        # Apply quality dampening for dimensions that depend heavily on a modality
        # that is unavailable. We blend toward the baseline rather than discarding.
        if dim == EvidenceDimension.CONFIDENCE:
            if not quality.nlp_available and not quality.face_available:
                score = _blend(score, _BASELINES[dim], 0.60)
        elif dim == EvidenceDimension.STRESS:
            if not quality.audio_available and not quality.face_available:
                score = _blend(score, _BASELINES[dim], 0.60)
        elif dim == EvidenceDimension.COMMUNICATION:
            if not quality.nlp_available:
                score = _blend(score, _BASELINES[dim], 0.45)

        return max(0.0, min(1.0, score))

    def _assess_reliability(
        self,
        evidence: List[BehavioralEvidence],
        quality: ModalityQuality,
        session_duration: float,
        total_words: int,
    ) -> PredictionReliability:
        # Hard insufficient gates
        if session_duration < 15.0:
            return PredictionReliability.INSUFFICIENT
        if len(evidence) < 2:
            return PredictionReliability.INSUFFICIENT

        active_modalities = sum([
            quality.face_available,
            quality.audio_available,
            quality.nlp_available,
        ])
        if active_modalities == 0:
            return PredictionReliability.INSUFFICIENT

        # Composite reliability score [0–1]
        r  = min(len(evidence) / 10.0, 1.0)  * 0.35
        r += min(active_modalities / 3.0, 1.0) * 0.30
        r += quality.evidence_coverage          * 0.20
        r += min(total_words / 60.0, 1.0)      * 0.10
        r += min(session_duration / 120.0, 1.0) * 0.05

        if r >= _HIGH_THRESHOLD:
            return PredictionReliability.HIGH
        if r >= _MEDIUM_THRESHOLD:
            return PredictionReliability.MEDIUM
        return PredictionReliability.LOW


def _blend(score: float, baseline: float, toward_baseline: float) -> float:
    """Blend score toward baseline when supporting modality is absent."""
    return score * (1.0 - toward_baseline) + baseline * toward_baseline


reasoner = BehavioralReasoner()
