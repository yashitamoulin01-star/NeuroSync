"""
Context-Aware Rule Engine — applies behavioral context to evidence interpretation.

Rules are not weighted equations. They are context-aware adjustments that modify
how evidence is interpreted based on the candidate's current behavioral state and
the interview segment.

Example: high stress during the introduction is expected (warm-up anxiety).
         The same stress signal during system design discussion means something different.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from backend.models.evidence import EvidenceDimension
from backend.reasoning.graph.evidence_graph import EvidenceGraph
from backend.reasoning.state_machine.behavioral_state import BehavioralState


@dataclass
class RuleContext:
    state:           BehavioralState
    graph:           EvidenceGraph
    elapsed_seconds: float
    confidence:      float
    stress:          float
    communication:   float
    engagement:      float
    consistency:     float
    segment:         str


@dataclass
class RuleResult:
    rule_name:  str
    fired:      bool
    action:     str
    dimension:  Optional[str] = None  # which dimension is adjusted
    adjustment: float = 0.0           # score delta to apply
    note:       str = ""


@dataclass
class ContextRule:
    name:        str
    description: str
    priority:    int
    evaluate:    Callable[[RuleContext], Optional[RuleResult]]


# ── Built-in rules ────────────────────────────────────────────────────────────

def _warming_up_stress(ctx: RuleContext) -> Optional[RuleResult]:
    """Stress during first 60s is expected warm-up anxiety; reduce its pull."""
    if ctx.state == BehavioralState.WARMING_UP and ctx.stress > 0.45:
        return RuleResult(
            rule_name="warming_up_stress_forgiveness", fired=True,
            action="reduce_stress", dimension="stress", adjustment=-0.10,
            note="Elevated stress during introduction is expected; warm-up discount applied.",
        )
    return None


def _stressed_but_communicating(ctx: RuleContext) -> Optional[RuleResult]:
    """Candidate under stress but maintaining clear communication — resilience signal."""
    if ctx.state == BehavioralState.STRESSED and ctx.communication > 0.62:
        return RuleResult(
            rule_name="stress_resilient_communication", fired=True,
            action="boost_communication", dimension="communication", adjustment=0.07,
            note="Coherent communication maintained under stress — resilience indicator.",
        )
    return None


def _recovery_boost(ctx: RuleContext) -> Optional[RuleResult]:
    """Rising confidence during RECOVERING state signals adaptability."""
    if ctx.state == BehavioralState.RECOVERING and ctx.confidence > 0.55:
        return RuleResult(
            rule_name="recovery_confidence_boost", fired=True,
            action="boost_confidence", dimension="confidence", adjustment=0.06,
            note="Positive recovery trajectory — adaptability indicator.",
        )
    return None


def _high_conflict_flag(ctx: RuleContext) -> Optional[RuleResult]:
    """Cross-modal evidence conflict reduces certainty (handled in calibration)."""
    if ctx.graph.conflict_score() > 0.40:
        return RuleResult(
            rule_name="cross_modal_conflict", fired=True,
            action="flag_mixed_evidence", dimension=None, adjustment=0.0,
            note=f"Cross-modal conflict ({ctx.graph.conflict_score():.0%}) — certainty reduced.",
        )
    return None


def _strong_agreement_bonus(ctx: RuleContext) -> Optional[RuleResult]:
    """High cross-modal agreement increases confidence in the estimate."""
    if ctx.graph.cross_modal_agreement() > 0.78 and len(ctx.graph.nodes) >= 6:
        return RuleResult(
            rule_name="strong_cross_modal_agreement", fired=True,
            action="increase_prediction_confidence", dimension=None, adjustment=0.0,
            note=f"Strong cross-modal agreement ({ctx.graph.cross_modal_agreement():.0%}) — high estimate confidence.",
        )
    return None


def _fatigue_engagement_context(ctx: RuleContext) -> Optional[RuleResult]:
    """Low engagement in FATIGUED state is not the same as disinterest."""
    if ctx.state == BehavioralState.FATIGUED and ctx.engagement < 0.40:
        return RuleResult(
            rule_name="fatigue_engagement_context", fired=True,
            action="normalize_engagement", dimension="engagement", adjustment=0.05,
            note="Low engagement interpreted as fatigue rather than disinterest.",
        )
    return None


BUILT_IN_RULES: List[ContextRule] = [
    ContextRule("cross_modal_conflict",          "High conflict reduces certainty",      10, _high_conflict_flag),
    ContextRule("strong_cross_modal_agreement",  "Agreement increases confidence",        9, _strong_agreement_bonus),
    ContextRule("warming_up_stress_forgiveness", "Early stress is contextual",            8, _warming_up_stress),
    ContextRule("recovery_confidence_boost",     "Recovery trajectory reward",            7, _recovery_boost),
    ContextRule("stress_resilient_communication","Resilient communication bonus",         6, _stressed_but_communicating),
    ContextRule("fatigue_engagement_context",    "Fatigue context for engagement",        5, _fatigue_engagement_context),
]


def evaluate_rules(
    ctx:   RuleContext,
    rules: Optional[List[ContextRule]] = None,
) -> List[RuleResult]:
    """Evaluate all rules in priority order and return fired results."""
    active = rules or BUILT_IN_RULES
    fired: List[RuleResult] = []
    for rule in sorted(active, key=lambda r: -r.priority):
        result = rule.evaluate(ctx)
        if result and result.fired:
            fired.append(result)
    return fired


def aggregate_adjustments(results: List[RuleResult]) -> Dict[str, float]:
    """Merge rule results into per-dimension score adjustments."""
    adj: Dict[str, float] = {}
    for r in results:
        if r.dimension and r.adjustment != 0.0:
            adj[r.dimension] = adj.get(r.dimension, 0.0) + r.adjustment
    return adj
