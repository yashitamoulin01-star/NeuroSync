"""
CBIP — Coaching Intelligence.

Tracks which coaching interventions produce measurable improvement and
uses that history to rank future coaching recommendations.

The system never invents new coaching content — it ranks the existing
candidate-specific coaching suggestions produced by the Behavioral
Reasoner by their historical effectiveness across all candidates.

This means:
  • Coaching text comes from the Reasoning Engine (immutable, governed)
  • Coaching ORDERING comes from this module (learned from outcomes)
  • The production model is never touched
"""

from __future__ import annotations
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.behavioral_knowledge.repository import (
    insert_coaching_record,
    update_coaching_outcome,
    get_coaching_effectiveness,
    get_coaching_records_for_candidate,
    count_coaching_records,
)
from backend.behavioral_knowledge.models import CoachingRecord

logger = logging.getLogger(__name__)

# Static coaching library — same advice the Reasoning Engine uses, now with
# effectiveness tracking.  These never change; only their ranking changes.
_COACHING_LIBRARY: Dict[str, str] = {
    "confidence":    "Practice deliberate vocal pacing and assertive language framing.",
    "engagement":    "Sustain active listening signals: eye contact cadence and response depth.",
    "communication": "Structure responses with a clear opening, body, and summary.",
    "composure":     "Apply controlled breathing before high-stakes responses.",
    "consistency":   "Align facial expression with vocal tone for cross-modal coherence.",
}

# Effective outcomes for coaching (net positive improvement)
_POSITIVE_OUTCOMES = {"improved"}


def record_coaching_delivery(
    candidate_id: str,
    session_id: str,
    coached_dimensions: List[str],
) -> None:
    """
    Record which dimensions received coaching after a given session.
    Called automatically by the growth response builder.
    """
    delivered_at = time.time()
    for dim in coached_dimensions:
        text = _COACHING_LIBRARY.get(dim, "")
        if not text:
            continue
        rec = CoachingRecord(
            record_id=str(uuid.uuid4()),
            candidate_id=candidate_id,
            session_id=session_id,
            dimension=dim,
            coaching_text=text,
            delivered_at=delivered_at,
        )
        insert_coaching_record(rec)


def resolve_coaching_outcome(
    candidate_id: str,
    new_session_id: str,
    old_scores: Dict[str, float],
    new_scores: Dict[str, float],
) -> None:
    """
    Compare two consecutive sessions' dimension scores.
    For any coached dimensions that improved, mark outcome as 'improved'.
    Called when a new session is finalised for a candidate who has prior records.
    """
    records = get_coaching_records_for_candidate(candidate_id)
    pending_dims = {
        r["dimension"]
        for r in records
        if r.get("outcome") is None
    }

    for dim in pending_dims:
        old_val = old_scores.get(dim, 0.0) or 0.0
        new_val = new_scores.get(dim, 0.0) or 0.0
        delta   = new_val - old_val
        if delta > 0.03:
            outcome = "improved"
        elif delta < -0.03:
            outcome = "declined"
        else:
            outcome = "stable"

        update_coaching_outcome(
            candidate_id=candidate_id,
            dimension=dim,
            follow_up_session_id=new_session_id,
            improvement_delta=round(delta, 4),
            outcome=outcome,
        )


def get_evidence_ranked_coaching(candidate_id: str, candidate_weakest: List[str]) -> List[str]:
    """
    Return coaching tips for the candidate's weakest dimensions,
    ordered by their platform-wide effectiveness rate.

    Falls back to the same static ordering as Phase 11 if no effectiveness
    data is available yet.
    """
    effectiveness = get_coaching_effectiveness()

    def _rank(dim: str) -> float:
        stats = effectiveness.get(dim)
        if stats and stats.get("rate") is not None:
            return stats["rate"]
        return 0.0  # unknown effectiveness — ranks last, not excluded

    ranked_dims = sorted(candidate_weakest, key=_rank, reverse=True)
    return [_COACHING_LIBRARY[d] for d in ranked_dims if d in _COACHING_LIBRARY]


def get_platform_coaching_effectiveness() -> Dict[str, Any]:
    """Return effectiveness stats for API consumption."""
    raw = get_coaching_effectiveness()
    total_delivered = sum(v["delivered"] for v in raw.values())
    total_improved  = sum(v["improved"]  for v in raw.values())
    overall_rate    = (
        round(total_improved / total_delivered, 3) if total_delivered > 0 else None
    )
    return {
        "by_dimension": raw,
        "total_coaching_delivered": total_delivered,
        "total_improved": total_improved,
        "overall_effectiveness_rate": overall_rate,
    }
