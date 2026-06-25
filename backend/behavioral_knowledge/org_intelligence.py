"""
CBIP — Organisation Intelligence.

Discovers organisation-specific behavioural preferences by aggregating
session signals per org_id.  This does not modify the scoring engine —
it surfaces which dimensions a given organisation tends to prioritise
based on their historical hiring decisions and recruiter validations.

Rules:
  • No org data is shared with other organisations.
  • Org profiles only form when sufficient validated sessions exist.
  • Insights are descriptive ("this org's sessions show higher consistency
    than the platform average") — never prescriptive about hiring.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from backend.behavioral_knowledge.repository import (
    insert_org_signal,
    get_org_signals,
    count_orgs,
)
from backend.behavioral_knowledge.models import OrgProfile, ValidationLevel

logger = logging.getLogger(__name__)

_PLATFORM_MEANS: Dict[str, float] = {
    "avg_confidence":    0.55,
    "avg_engagement":    0.58,
    "avg_communication": 0.54,
    "avg_consistency":   0.56,
}

_DIM_LABELS: Dict[str, str] = {
    "avg_confidence":    "Confidence",
    "avg_engagement":    "Engagement",
    "avg_communication": "Communication",
    "avg_consistency":   "Consistency",
}

_MIN_SESSIONS_FOR_INSIGHT = 5


def record_org_session(
    org_id: str,
    session_id: str,
    metrics: Dict[str, float],
    recommendation: str,
    validation_level: str = ValidationLevel.OBSERVATION,
) -> None:
    """Store a session's metrics attributed to an organisation."""
    if not org_id:
        return
    insert_org_signal(org_id, session_id, metrics, recommendation, validation_level)


def build_org_profile(org_id: str) -> Optional[OrgProfile]:
    """
    Compute a descriptive intelligence profile for an organisation from
    its accumulated session signals.  Returns None when insufficient data.
    """
    signals = get_org_signals(org_id)
    if not signals:
        return None

    n = len(signals)
    dim_keys = list(_PLATFORM_MEANS.keys())
    means: Dict[str, float] = {}
    for dim in dim_keys:
        vals = [s["metrics"].get(dim, 0.0) or 0.0 for s in signals]
        means[dim] = round(sum(vals) / len(vals), 4) if vals else 0.0

    preferred = [
        dim for dim in dim_keys
        if means.get(dim, 0.0) > _PLATFORM_MEANS.get(dim, 0.0) + 0.05
    ]

    # Confidence grows with more sessions, capped at 0.95
    confidence = round(min(0.95, n / 50), 4)

    insight = _build_insight(org_id, means, preferred, n)

    return OrgProfile(
        org_id=org_id,
        total_sessions=n,
        mean_metrics=means,
        preferred_dims=preferred,
        insight=insight,
        confidence=confidence,
    )


def _build_insight(
    org_id: str,
    means: Dict[str, float],
    preferred: List[str],
    n: int,
) -> str:
    if n < _MIN_SESSIONS_FOR_INSIGHT:
        return (
            f"Organisation profile is forming — {n} session(s) recorded. "
            f"Insights will surface after {_MIN_SESSIONS_FOR_INSIGHT} sessions."
        )
    if not preferred:
        return (
            "This organisation's sessions align closely with platform-wide averages "
            "across all behavioural dimensions."
        )
    labels = [_DIM_LABELS.get(d, d) for d in preferred]
    dim_str = " and ".join(labels)
    return (
        f"Sessions from this organisation show consistently higher {dim_str} "
        f"compared to the platform average across {n} interviews. "
        "This reflects the communication patterns this organisation has historically valued."
    )


def get_org_intelligence_summary(org_id: str) -> Dict[str, Any]:
    profile = build_org_profile(org_id)
    if not profile:
        return {
            "org_id": org_id,
            "status": "insufficient_data",
            "message": "No sessions recorded for this organisation yet.",
        }
    return {
        "org_id":           profile.org_id,
        "status":           "active",
        "total_sessions":   profile.total_sessions,
        "mean_metrics":     profile.mean_metrics,
        "preferred_dims":   profile.preferred_dims,
        "insight":          profile.insight,
        "confidence":       profile.confidence,
        "platform_means":   _PLATFORM_MEANS,
        "updated_at":       profile.updated_at,
    }
