"""
CBIP — REST API router.

Prefix: /cbip

Validation endpoints (Validation Pyramid):
  POST /cbip/feedback/candidate          — L2 candidate feedback
  POST /cbip/feedback/recruiter          — L3 recruiter validation
  POST /cbip/outcomes/hiring             — L4 hiring decision
  POST /cbip/outcomes/performance        — L5 long-term outcome

Knowledge endpoints:
  GET  /cbip/knowledge/stats             — platform knowledge summary
  GET  /cbip/knowledge/patterns          — discovered behavioural patterns

Candidate intelligence endpoints:
  GET  /cbip/coaching/{candidate_id}     — evidence-ranked coaching
  GET  /cbip/forecast/{candidate_id}     — growth trajectory forecast

Organisation intelligence:
  GET  /cbip/org/{org_id}               — org behavioural intelligence

Internal (called automatically by session finalisation):
  POST /cbip/observe                     — record a completed session (L1)
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from backend.behavioral_knowledge.models import (
    CandidateFeedbackRequest, RecruiterFeedbackRequest,
    HiringDecisionRequest, LongTermOutcomeRequest,
    PlatformKnowledgeStats,
)
from backend.behavioral_knowledge import validation_engine as ve
from backend.behavioral_knowledge import pattern_discovery as pd
from backend.behavioral_knowledge import coaching_intelligence as ci
from backend.behavioral_knowledge import org_intelligence as oi
from backend.behavioral_knowledge import forecasting_engine as fe
from backend.behavioral_knowledge.repository import (
    count_total_observations, count_validation_events_by_level,
    get_all_patterns, count_coaching_records, count_orgs,
    get_coaching_effectiveness,
)
from backend.behavioral_memory.repository import get_profile, list_history

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cbip", tags=["cbip"])


# ── Validation Pyramid endpoints ──────────────────────────────────────────────

@router.post("/feedback/candidate")
def candidate_feedback(req: CandidateFeedbackRequest):
    """L2 — candidate subjective feedback on their own interview analysis."""
    event = ve.record_candidate_feedback(
        session_id=req.session_id,
        candidate_id=req.candidate_id,
        helpful=req.helpful,
        comment=req.comment,
    )
    return {"event_id": event.event_id, "level": event.level, "confidence": event.confidence}


@router.post("/feedback/recruiter")
def recruiter_feedback(req: RecruiterFeedbackRequest):
    """L3 — recruiter expert validation of the analysis quality."""
    valid_ratings = {"helpful", "not_helpful", "needs_review", "incorrect", "missing_context"}
    if req.rating not in valid_ratings:
        raise HTTPException(
            status_code=422,
            detail=f"rating must be one of: {', '.join(sorted(valid_ratings))}",
        )
    event = ve.record_recruiter_feedback(
        session_id=req.session_id,
        rating=req.rating,
        org_id=req.org_id,
        comment=req.comment,
    )
    # Refresh pattern confidence after high-value validation
    pd.refresh_pattern_stats()
    return {"event_id": event.event_id, "level": event.level, "confidence": event.confidence}


@router.post("/outcomes/hiring")
def hiring_decision(req: HiringDecisionRequest):
    """L4 — organisational hiring decision (ground truth signal)."""
    valid_decisions = {"strong_hire", "hire", "hold", "reject"}
    if req.decision not in valid_decisions:
        raise HTTPException(
            status_code=422,
            detail=f"decision must be one of: {', '.join(sorted(valid_decisions))}",
        )
    event = ve.record_hiring_decision(
        session_id=req.session_id,
        decision=req.decision,
        candidate_id=req.candidate_id,
        org_id=req.org_id,
        notes=req.notes,
    )
    pd.refresh_pattern_stats()
    return {"event_id": event.event_id, "level": event.level, "confidence": event.confidence}


@router.post("/outcomes/performance")
def long_term_outcome(req: LongTermOutcomeRequest):
    """L5 — long-term performance outcome (highest validation confidence)."""
    valid_outcomes = {"retained", "promoted", "performance_review", "probation", "exit"}
    if req.outcome not in valid_outcomes:
        raise HTTPException(
            status_code=422,
            detail=f"outcome must be one of: {', '.join(sorted(valid_outcomes))}",
        )
    event = ve.record_long_term_outcome(
        session_id=req.session_id,
        outcome=req.outcome,
        candidate_id=req.candidate_id,
        org_id=req.org_id,
        months_since_hire=req.months_since_hire,
    )
    pd.refresh_pattern_stats()
    return {"event_id": event.event_id, "level": event.level, "confidence": event.confidence}


# ── Internal observation endpoint (called by session finalisation) ────────────

@router.post("/observe")
def record_observation(
    session_id: str,
    candidate_id: Optional[str] = None,
    org_id: Optional[str] = None,
):
    """L1 — automatic observation. Called after every session completes."""
    event = ve.record_observation(
        session_id=session_id,
        candidate_id=candidate_id,
        org_id=org_id,
    )
    return {"event_id": event.event_id, "confidence": event.confidence}


# ── Knowledge endpoints ───────────────────────────────────────────────────────

@router.get("/knowledge/stats")
def knowledge_stats() -> PlatformKnowledgeStats:
    """Return a summary of the platform's accumulated behavioural knowledge."""
    level_counts    = count_validation_events_by_level()
    patterns        = get_all_patterns()
    effectiveness   = get_coaching_effectiveness()

    total_delivered = sum(v["delivered"] for v in effectiveness.values())
    total_improved  = sum(v["improved"]  for v in effectiveness.values())
    eff_rate        = (
        round(total_improved / total_delivered * 100, 1) if total_delivered > 0 else None
    )

    return PlatformKnowledgeStats(
        total_sessions_observed=count_total_observations(),
        total_validation_events=sum(level_counts.values()),
        recruiter_validated=level_counts.get("recruiter_feedback",  0),
        hiring_decisions=level_counts.get("hiring_decision",        0),
        long_term_outcomes=level_counts.get("long_term_outcome",    0),
        patterns_discovered=len(patterns),
        patterns_validated=sum(1 for p in patterns if p.validated_count > 0),
        orgs_tracked=count_orgs(),
        coaching_records=count_coaching_records(),
        coaching_effectiveness_pct=eff_rate,
        knowledge_confidence=ve.compute_platform_knowledge_confidence(),
    )


@router.get("/knowledge/patterns")
def knowledge_patterns():
    """Return all discovered behavioural patterns with confidence scores."""
    return {
        "patterns": pd.get_patterns_for_api(),
        "total": len(get_all_patterns()),
    }


# ── Candidate intelligence ────────────────────────────────────────────────────

@router.get("/coaching/{candidate_id}")
def enhanced_coaching(candidate_id: str):
    """
    Return evidence-ranked coaching recommendations for a candidate.
    Coaching text is identical to standard recommendations; ordering reflects
    which interventions have historically produced the most improvement.
    """
    from backend.behavioral_memory.engine import build_growth_response
    growth = build_growth_response(candidate_id)
    if not growth:
        raise HTTPException(
            status_code=404,
            detail="No profile found — complete at least one interview first.",
        )

    weakest = sorted(growth.baseline.items(), key=lambda kv: kv[1])[:2]
    weakest_dims = [k for k, _ in weakest]

    ranked = ci.get_evidence_ranked_coaching(candidate_id, weakest_dims)
    effectiveness = ci.get_platform_coaching_effectiveness()

    return {
        "candidate_id":  candidate_id,
        "coached_dims":  weakest_dims,
        "coaching_tips": ranked,
        "effectiveness": effectiveness,
        "source":        "evidence_ranked",
        "note": (
            "Coaching suggestions are ranked by their historically measured effectiveness "
            "across all candidates on the NeuroSync platform. "
            "The underlying coaching content is produced by the Behavioral Reasoning Engine "
            "and is never modified by this layer."
        ),
    }


@router.get("/forecast/{candidate_id}")
def growth_forecast(candidate_id: str):
    """
    Return a growth trajectory forecast for a candidate.
    Forecasts predict behavioural growth only — not hiring outcomes.
    """
    profile = get_profile(candidate_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="No profile found — complete at least one interview first.",
        )

    history = list_history(candidate_id, limit=20)
    forecast = fe.build_growth_forecast(candidate_id, history)

    if not forecast:
        return {
            "candidate_id":    candidate_id,
            "forecast":        None,
            "status":          "insufficient_data",
            "message": (
                f"Forecasting requires at least 3 interviews. "
                f"Current count: {profile.total_interviews}."
            ),
        }

    return {
        "candidate_id": candidate_id,
        "forecast":     forecast.model_dump(),
        "status":       "ok",
        "disclaimer": (
            "Forecasts project behavioural growth based on observed trends. "
            "They do not predict hiring outcomes or evaluate candidate suitability. "
            "All projections include uncertainty bounds and should be read as ranges, "
            "not fixed targets."
        ),
    }


# ── Organisation intelligence ─────────────────────────────────────────────────

@router.get("/org/{org_id}")
def org_intelligence(org_id: str):
    """Return behavioural intelligence for an organisation."""
    return oi.get_org_intelligence_summary(org_id)
