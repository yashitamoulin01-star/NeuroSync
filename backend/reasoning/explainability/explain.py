"""
Explainability Engine — makes every reasoning decision inspectable.

Every score exposes:
  Observed Behaviors → Supporting Evidence → Conflicting Evidence
  → Reasoning Path → Calibration → Final Estimate

Nothing should be hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.models.evidence import EvidenceDimension, EvidencePolarity
from backend.reasoning.graph.evidence_graph import EvidenceGraph


_DIM_LABELS = {
    "confidence":    "Self-Confidence",
    "stress":        "Stress Level",
    "communication": "Communication Quality",
    "engagement":    "Engagement",
    "consistency":   "Behavioral Consistency",
}

_DIM_ENUM = {
    "confidence":    EvidenceDimension.CONFIDENCE,
    "stress":        EvidenceDimension.STRESS,
    "communication": EvidenceDimension.COMMUNICATION,
    "engagement":    EvidenceDimension.ENGAGEMENT,
    "consistency":   EvidenceDimension.CONSISTENCY,
}


@dataclass
class DimensionExplanation:
    dimension:            str
    label:                str
    raw_score:            float
    calibrated_score:     float
    supporting_behaviors: List[str]
    conflicting_behaviors:List[str]
    reasoning_path:       List[str]
    calibration_note:     str
    evidence_count:       int
    cross_modal_reinforced: bool

    def to_dict(self) -> Dict:
        return {
            "dimension":              self.dimension,
            "label":                  self.label,
            "raw_score":              round(self.raw_score, 3),
            "calibrated_score":       round(self.calibrated_score, 3),
            "supporting_behaviors":   self.supporting_behaviors,
            "conflicting_behaviors":  self.conflicting_behaviors,
            "reasoning_path":         self.reasoning_path,
            "calibration_note":       self.calibration_note,
            "evidence_count":         self.evidence_count,
            "cross_modal_reinforced": self.cross_modal_reinforced,
        }


@dataclass
class FullExplanation:
    session_id:                  str
    behavioral_state:            str
    segment:                     str
    pattern:                     str
    dimensions:                  Dict[str, DimensionExplanation]
    overall_reasoning_confidence:str
    conflict_summary:            str
    recommendation:              str
    audit_notes:                 List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "session_id":                   self.session_id,
            "behavioral_state":             self.behavioral_state,
            "segment":                      self.segment,
            "pattern":                      self.pattern,
            "dimensions":                   {k: v.to_dict() for k, v in self.dimensions.items()},
            "overall_reasoning_confidence": self.overall_reasoning_confidence,
            "conflict_summary":             self.conflict_summary,
            "recommendation":              self.recommendation,
            "audit_notes":                 self.audit_notes,
        }


def _explain_dimension(
    dim_name:       str,
    ev_dim:         EvidenceDimension,
    raw_score:      float,
    calibrated:     float,
    graph:          EvidenceGraph,
    calibration_note: str,
) -> DimensionExplanation:
    items     = graph.evidence_for(ev_dim)
    positive  = [ev for ev in items if ev.polarity == EvidencePolarity.POSITIVE]
    negative  = [ev for ev in items if ev.polarity == EvidencePolarity.NEGATIVE]
    reinforced= bool(graph.reinforcements(ev_dim))

    path: List[str] = []
    if positive:
        srcs = ", ".join(dict.fromkeys(
            ev.source_modalities[0] for ev in positive[:2] if ev.source_modalities
        ))
        path.append(f"{len(positive)} positive signal(s) from {srcs or 'pipeline'}.")
    if negative:
        srcs = ", ".join(dict.fromkeys(
            ev.source_modalities[0] for ev in negative[:2] if ev.source_modalities
        ))
        path.append(f"{len(negative)} negative signal(s) from {srcs or 'pipeline'}.")
    if reinforced:
        path.append("Cross-modal agreement detected — higher estimate confidence.")
    if abs(calibrated - raw_score) > 0.015:
        delta = calibrated - raw_score
        path.append(f"Context rule adjusted score {delta:+.0%}.")
    path.append(f"Final calibrated estimate: {calibrated:.0%}.")

    return DimensionExplanation(
        dimension             = dim_name,
        label                 = _DIM_LABELS.get(dim_name, dim_name.title()),
        raw_score             = raw_score,
        calibrated_score      = calibrated,
        supporting_behaviors  = [ev.description for ev in positive[:3]],
        conflicting_behaviors = [ev.description for ev in negative[:3]],
        reasoning_path        = path,
        calibration_note      = calibration_note,
        evidence_count        = len(items),
        cross_modal_reinforced= reinforced,
    )


def _recommend(
    calibrated:           Dict[str, float],
    state:                str,
    pattern:              str,
    reasoning_confidence: str,
) -> str:
    if reasoning_confidence == "low":
        return "Insufficient data for a reliable recommendation. Continue observation."

    conf  = calibrated.get("confidence",    0.5)
    stress= calibrated.get("stress",        0.5)
    comm  = calibrated.get("communication", 0.5)

    if conf > 0.70 and stress < 0.35 and comm > 0.65:
        return "Strong candidate signal. Recommend proceeding with next interview stage."
    if pattern == "recovering":
        return "Candidate demonstrated recovery. Follow up on initial hesitation areas."
    if conf < 0.40 and stress > 0.65:
        return "Candidate showing high stress. Consider rephrasing or offering reassurance."
    if comm > 0.70 and conf < 0.50:
        return "Strong communication, uncertain confidence. Follow-up probe recommended."
    return "Mixed signals. Review specific behavioral timestamps for additional context."


def build_explanation(
    session_id:           str,
    raw_scores:           Dict[str, float],
    calibrated_scores:    Dict[str, float],
    graph:                EvidenceGraph,
    behavioral_state:     str,
    segment:              str,
    pattern:              str,
    reasoning_confidence: str,
    conflict_count:       int,
    rule_notes:           List[str],
) -> FullExplanation:
    dimensions: Dict[str, DimensionExplanation] = {}
    for dim_name, ev_dim in _DIM_ENUM.items():
        raw  = raw_scores.get(dim_name, 0.5)
        cal  = calibrated_scores.get(dim_name, raw)
        note = next((n for n in rule_notes if dim_name in n.lower()), "")
        dimensions[dim_name] = _explain_dimension(dim_name, ev_dim, raw, cal, graph, note)

    conflict_summary = (
        f"{conflict_count} cross-modal conflict(s) — wider uncertainty bounds apply."
        if conflict_count > 0
        else "No significant cross-modal conflicts detected."
    )

    return FullExplanation(
        session_id                   = session_id,
        behavioral_state             = behavioral_state,
        segment                      = segment,
        pattern                      = pattern,
        dimensions                   = dimensions,
        overall_reasoning_confidence = reasoning_confidence,
        conflict_summary             = conflict_summary,
        recommendation               = _recommend(
            calibrated_scores, behavioral_state, pattern, reasoning_confidence
        ),
        audit_notes = rule_notes,
    )
