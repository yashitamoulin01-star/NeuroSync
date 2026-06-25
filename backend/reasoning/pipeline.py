"""
Reasoning pipeline — orchestrates the full intelligence chain.

Phase 3 architecture:
  Raw Features
    → Evidence Extraction
    → Evidence Graph
    → Quality Assessment
    → Contradiction Detection
    → Behavioral Reasoning
    → Temporal Analysis
    → Behavioral State Machine
    → Context-Aware Rules
    → Confidence Calibration
    → Insight Generation
    → Explainability
    → Decision Trace
    → FusedAnalytics

Every composite score is traceable. Every conclusion is reconstructable.
This is the difference between a model that computes and a system that reasons.
"""

import time
import logging
from typing import Dict, List, Optional

from backend.models.evidence import (
    BehavioralEvidence,
    EvidenceDimension,
    EvidencePolarity,
    ModalityQuality,
    PredictionReliability,
    ScoreBreakdown,
)
from backend.models.schemas import (
    FaceMetrics,
    AudioMetrics,
    NLPMetrics,
    FusedAnalytics,
    BehavioralInsight,
    ModalityType,
)
from backend.reasoning.extractors import (
    extract_face_evidence,
    extract_audio_evidence,
    extract_nlp_evidence,
    extract_cross_modal_evidence,
)
from backend.reasoning.reasoner import reasoner
from backend.reasoning.graph.evidence_graph import EvidenceGraph
from backend.reasoning.timeline.temporal_engine import (
    ScoreSnapshot,
    TemporalAnalysis,
    analyze_temporal,
)
from backend.reasoning.state_machine.behavioral_state import (
    BehavioralState,
    next_state,
)
from backend.reasoning.rules.context_rules import (
    RuleContext,
    evaluate_rules,
    aggregate_adjustments,
)
from backend.reasoning.calibration.confidence_engine import calibrate
from backend.reasoning.audit.decision_trace import DecisionTrace
from backend.reasoning.explainability.explain import build_explanation

logger = logging.getLogger(__name__)

_MODALITY_MAP = {
    "face":  ModalityType.FACE,
    "audio": ModalityType.AUDIO,
    "nlp":   ModalityType.NLP,
}


# ── Stage helpers ─────────────────────────────────────────────────────────────

def _build_quality(
    face:     Optional[FaceMetrics],
    audio:    Optional[AudioMetrics],
    nlp:      Optional[NLPMetrics],
    evidence: List[BehavioralEvidence],
) -> ModalityQuality:
    face_active  = face  is not None and face.face_detected
    audio_active = audio is not None and audio.is_speaking
    nlp_active   = nlp   is not None and bool(nlp.transcript_chunk.strip())

    dims_with_evidence = len(set(ev.dimension for ev in evidence))
    coverage = dims_with_evidence / len(EvidenceDimension) if evidence else 0.0

    return ModalityQuality(
        face_available   = face_active,
        face_quality     = round(face.eye_contact_score, 3)           if face_active  else 0.0,
        audio_available  = audio_active,
        audio_quality    = round(audio.energy_level, 3)               if audio_active else 0.0,
        nlp_available    = nlp_active,
        nlp_quality      = round(min(nlp.words_per_chunk / 20.0, 1.0), 3) if nlp_active else 0.0,
        transcript_words = nlp.words_per_chunk if nlp_active else 0,
        evidence_coverage= round(coverage, 3),
    )


def _apply_calibration_to_scores(
    scores:        ScoreBreakdown,
    calibrated:    Dict[str, float],
) -> ScoreBreakdown:
    """Return a new ScoreBreakdown using calibration-adjusted values."""
    return ScoreBreakdown(
        confidence    = calibrated.get("confidence",    scores.confidence),
        stress        = calibrated.get("stress",        scores.stress),
        communication = calibrated.get("communication", scores.communication),
        engagement    = calibrated.get("engagement",    scores.engagement),
        consistency   = calibrated.get("consistency",   scores.consistency),
        reliability   = scores.reliability,
        evidence_count= scores.evidence_count,
        evidence_coverage = scores.evidence_coverage,
    )


def _generate_insights(
    evidence: List[BehavioralEvidence],
    scores:   ScoreBreakdown,
) -> List[BehavioralInsight]:
    """Evidence-grounded insights, suppressed when reliability is insufficient."""
    if scores.reliability == PredictionReliability.INSUFFICIENT:
        return []

    insights: List[BehavioralInsight] = []
    emitted: set = set()

    def _add(insight: BehavioralInsight) -> None:
        if insight.type not in emitted:
            insights.append(insight)
            emitted.add(insight.type)

    def _modalities(evs: List[BehavioralEvidence]) -> List[ModalityType]:
        seen: set = set()
        result = []
        for ev in evs:
            for src in ev.source_modalities:
                if src not in seen and src in _MODALITY_MAP:
                    seen.add(src)
                    result.append(_MODALITY_MAP[src])
        return result

    # Stress spike — cross-modal compound version preferred
    compound_stress = next((e for e in evidence if e.id == "cross.stress.face_audio"), None)
    if compound_stress and scores.stress > 0.55:
        _add(BehavioralInsight(
            type="stress_spike",
            description=compound_stress.description,
            severity=round(scores.stress, 3),
            modalities_involved=_modalities([compound_stress]),
        ))
    elif scores.stress > 0.62:
        stress_ev = [e for e in evidence
                     if e.dimension == EvidenceDimension.STRESS
                     and e.polarity == EvidencePolarity.NEGATIVE]
        if stress_ev:
            citations = " · ".join(e.description for e in stress_ev[:2])
            _add(BehavioralInsight(
                type="stress_spike",
                description=f"Elevated stress — {citations}",
                severity=round(scores.stress, 3),
                modalities_involved=_modalities(stress_ev),
            ))

    # Gaze aversion
    gaze_ev = next((e for e in evidence if e.id == "face.eye_contact.reduced"), None)
    if gaze_ev:
        _add(BehavioralInsight(
            type="gaze_aversion",
            description=gaze_ev.description,
            severity=round(1.0 - (gaze_ev.measurement or 0.5), 3),
            modalities_involved=[ModalityType.FACE],
        ))

    # Hesitation burst
    hes_ev = next((e for e in evidence if "hesitation.communication" in e.id), None)
    if hes_ev:
        _add(BehavioralInsight(
            type="hesitation_burst",
            description=hes_ev.description,
            severity=round(hes_ev.measurement or 0.5, 3),
            modalities_involved=[ModalityType.NLP],
        ))

    # Filler word burst
    filler_ev = next((e for e in evidence if e.id == "nlp.filler_words.multiple"), None)
    if filler_ev:
        _add(BehavioralInsight(
            type="filler_words",
            description=filler_ev.description,
            severity=round(min((filler_ev.measurement or 0) / 8.0, 1.0), 3),
            modalities_involved=[ModalityType.NLP],
        ))

    # Strong delivery
    if scores.confidence > 0.70 and scores.stress < 0.38:
        conf_ev = [e for e in evidence
                   if e.dimension == EvidenceDimension.CONFIDENCE
                   and e.polarity == EvidencePolarity.POSITIVE]
        if len(conf_ev) >= 2:
            cross_conf = next((e for e in conf_ev if e.id.startswith("cross.")), None)
            anchor = cross_conf or conf_ev[0]
            _add(BehavioralInsight(
                type="strong_delivery",
                description=f"Confident delivery — {anchor.description}",
                severity=0.0,
                modalities_involved=_modalities(conf_ev[:2]),
            ))

    return insights


# ── Public pipeline ───────────────────────────────────────────────────────────

def run_reasoning_pipeline(
    face:           Optional[FaceMetrics],
    audio:          Optional[AudioMetrics],
    nlp:            Optional[NLPMetrics],
    session_id:     str,
    session_start:  float,
    total_words:    int,
    total_fillers:  int,
    avg_pace:       float,
    # Phase 3: temporal context (optional — backward-compatible)
    score_history:     Optional[List[ScoreSnapshot]] = None,
    behavioral_state:  str = "warming_up",
    window_index:      int = 0,
) -> FusedAnalytics:
    """
    Full reasoning pipeline: evidence → graph → reasoning → calibration → analytics.

    Pipeline stages:
      1.  Evidence extraction   — per modality, no fabrication
      2.  Cross-modal evidence  — only when both sources active
      3.  Evidence Graph        — relationship map, contradiction detection
      4.  Quality assessment    — per-modality availability / signal strength
      5.  Behavioral reasoning  — evidence → raw scores + reliability
      6.  Temporal analysis     — trend detection over session history
      7.  Behavioral state      — state machine transition
      8.  Context rules         — context-aware evidence interpretation
      9.  Confidence calibration— certainty about own conclusions
      10. Insight generation    — evidence-grounded, deduped
      11. Explainability        — full reasoning trace per dimension
      12. Decision trace        — reconstructable audit record
      13. FusedAnalytics        — backward-compatible schema + new Phase 3 fields
    """
    t0  = time.perf_counter()
    now = time.time()
    session_duration = now - session_start

    # Stage 1–2: Evidence extraction
    face_ev  = extract_face_evidence(face)
    audio_ev = extract_audio_evidence(audio)
    nlp_ev   = extract_nlp_evidence(nlp)
    cross_ev = extract_cross_modal_evidence(face, audio, nlp)
    all_evidence = face_ev + audio_ev + nlp_ev + cross_ev

    # Stage 3: Evidence Graph — build relationships
    graph = EvidenceGraph()
    graph.add_many(all_evidence).build()
    conflict_count = sum(1 for e in graph.edges
                         if e.edge_type.value == "contradicts")  # type: ignore[attr-defined]

    # Stage 4: Quality assessment
    quality = _build_quality(face, audio, nlp, all_evidence)

    # Stage 5: Behavioral reasoning → raw scores
    raw_scores = reasoner.reason(
        evidence         = all_evidence,
        quality          = quality,
        session_duration = session_duration,
        total_words      = total_words,
    )

    # Stage 6: Temporal analysis
    temporal: Optional[TemporalAnalysis] = None
    if score_history:
        temporal = analyze_temporal(score_history)

    segment = temporal.segment if temporal else "introduction"
    pattern = temporal.pattern if temporal else "settling"
    trends  = temporal.trends  if temporal else {}

    # Stage 7: Behavioral state machine
    current_bs = BehavioralState(behavioral_state) if behavioral_state in BehavioralState._value2member_map_ else BehavioralState.WARMING_UP
    state_result = next_state(
        current         = current_bs,
        elapsed_seconds = session_duration,
        confidence      = raw_scores.confidence,
        stress          = raw_scores.stress,
        communication   = raw_scores.communication,
        engagement      = raw_scores.engagement,
        pattern         = pattern,
    )
    new_state = state_result.current

    # Stage 8: Context-aware rules
    rule_ctx = RuleContext(
        state           = new_state,
        graph           = graph,
        elapsed_seconds = session_duration,
        confidence      = raw_scores.confidence,
        stress          = raw_scores.stress,
        communication   = raw_scores.communication,
        engagement      = raw_scores.engagement,
        consistency     = raw_scores.consistency,
        segment         = segment,
    )
    rule_results = evaluate_rules(rule_ctx)
    rule_adjustments = aggregate_adjustments(rule_results)
    rule_notes = [r.note for r in rule_results if r.note]

    # Active modalities for calibration
    active_modalities: List[str] = []
    if quality.face_available:  active_modalities.append("face")
    if quality.audio_available: active_modalities.append("audio")
    if quality.nlp_available:   active_modalities.append("nlp")

    # Stage 9: Confidence calibration
    raw_score_dict = {
        "confidence":    raw_scores.confidence,
        "stress":        raw_scores.stress,
        "communication": raw_scores.communication,
        "engagement":    raw_scores.engagement,
        "consistency":   raw_scores.consistency,
    }
    cal = calibrate(
        scores                = raw_score_dict,
        reliability           = raw_scores.reliability,
        modality_quality      = quality,
        conflict_score        = graph.conflict_score(),
        cross_modal_agreement = graph.cross_modal_agreement(),
        evidence_count        = len(all_evidence),
        rule_adjustments      = rule_adjustments,
        elapsed_seconds       = session_duration,
    )
    calibrated_scores = cal.behavior_estimate

    # Build updated ScoreBreakdown with calibrated values
    adjusted_breakdown = _apply_calibration_to_scores(raw_scores, calibrated_scores)

    # Stage 10: Insight generation (uses calibrated scores)
    insights = _generate_insights(all_evidence, adjusted_breakdown)

    # Stage 11: Explainability
    explanation = build_explanation(
        session_id           = session_id,
        raw_scores           = raw_score_dict,
        calibrated_scores    = calibrated_scores,
        graph                = graph,
        behavioral_state     = new_state.value,
        segment              = segment,
        pattern              = pattern,
        reasoning_confidence = cal.reasoning_confidence,
        conflict_count       = conflict_count,
        rule_notes           = rule_notes,
    )

    # Stage 12: Decision trace
    latency_ms = (time.perf_counter() - t0) * 1000.0
    trace = DecisionTrace(
        session_id            = session_id,
        window_index          = window_index,
        timestamp             = now,
        elapsed_seconds       = session_duration,
        evidence_count        = len(all_evidence),
        conflict_count        = conflict_count,
        modalities_active     = active_modalities,
        behavioral_state      = new_state.value,
        segment               = segment,
        pattern               = pattern,
        state_changed         = state_result.changed,
        state_change_reason   = state_result.reason,
        raw_scores            = raw_score_dict,
        calibrated_scores     = calibrated_scores,
        reliability           = raw_scores.reliability.value,
        prediction_confidence = cal.prediction_confidence,
        signal_quality        = cal.signal_quality,
        rules_fired           = [r.rule_name for r in rule_results],
        rule_notes            = rule_notes,
        trends                = trends,
        insights              = [i.type for i in insights],
    )

    # Stage 13: FusedAnalytics
    return FusedAnalytics(
        timestamp              = now,
        session_id             = session_id,
        overall_confidence     = calibrated_scores.get("confidence",    raw_scores.confidence),
        communication_quality  = calibrated_scores.get("communication", raw_scores.communication),
        engagement_score       = calibrated_scores.get("engagement",    raw_scores.engagement),
        stress_level           = calibrated_scores.get("stress",        raw_scores.stress),
        behavioral_consistency = calibrated_scores.get("consistency",   raw_scores.consistency),
        face                   = face,
        audio                  = audio,
        nlp                    = nlp,
        insights               = insights,
        evidence               = all_evidence,
        score_breakdown        = adjusted_breakdown,
        data_quality           = quality,
        session_duration       = session_duration,
        total_words_spoken     = total_words,
        total_filler_words     = total_fillers,
        avg_speaking_pace      = avg_pace,
        # Phase 3 fields
        behavioral_state       = new_state.value,
        behavioral_pattern     = pattern,
        segment                = segment,
        trends                 = trends,
        conflict_count         = conflict_count,
        calibration            = cal.to_dict(),
        explanation            = explanation.to_dict(),
        decision_trace         = trace.to_dict(),
    )
