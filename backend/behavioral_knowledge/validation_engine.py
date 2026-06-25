"""
CBIP — Validation Engine.

Implements the five-level Validation Pyramid.  Every piece of behavioral
knowledge is assigned a confidence score proportional to the validation
level that produced it.  Knowledge only becomes trusted through repeated
multi-level confirmation.

Confidence hierarchy:
  L1 Automatic observation       0.20
  L2 Candidate feedback          0.45
  L3 Recruiter validation        0.70
  L4 Hiring decision             0.90
  L5 Long-term performance       1.00
"""

from __future__ import annotations
import uuid
import time
import logging
from typing import Any, Dict, List, Optional

from backend.behavioral_knowledge.models import (
    ValidationEvent, ValidationLevel, VALIDATION_CONFIDENCE,
)
from backend.behavioral_knowledge.repository import (
    insert_validation_event,
    list_validation_events,
    count_validation_events_by_level,
)

logger = logging.getLogger(__name__)


def record_event(
    session_id: str,
    level: ValidationLevel,
    signal: str,
    candidate_id: Optional[str] = None,
    org_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ValidationEvent:
    confidence = VALIDATION_CONFIDENCE[level]
    event = ValidationEvent(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        candidate_id=candidate_id,
        org_id=org_id,
        level=level,
        signal=signal,
        confidence=confidence,
        metadata=metadata or {},
        recorded_at=time.time(),
    )
    insert_validation_event(event)
    logger.debug(
        "CBIP validation event: level=%s signal=%s session=%s confidence=%.2f",
        level, signal, session_id, confidence,
    )
    return event


def record_observation(
    session_id: str,
    candidate_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> ValidationEvent:
    """L1 — automatic observation fired after every completed session."""
    return record_event(
        session_id=session_id,
        level=ValidationLevel.OBSERVATION,
        signal="session_completed",
        candidate_id=candidate_id,
        org_id=org_id,
    )


def record_candidate_feedback(
    session_id: str,
    candidate_id: str,
    helpful: bool,
    comment: Optional[str] = None,
) -> ValidationEvent:
    """L2 — candidate subjective feedback."""
    return record_event(
        session_id=session_id,
        level=ValidationLevel.CANDIDATE_FEEDBACK,
        signal="helpful" if helpful else "not_helpful",
        candidate_id=candidate_id,
        metadata={"comment": comment},
    )


def record_recruiter_feedback(
    session_id: str,
    rating: str,
    org_id: Optional[str] = None,
    comment: Optional[str] = None,
) -> ValidationEvent:
    """L3 — recruiter expert validation."""
    return record_event(
        session_id=session_id,
        level=ValidationLevel.RECRUITER_FEEDBACK,
        signal=rating,
        org_id=org_id,
        metadata={"comment": comment},
    )


def record_hiring_decision(
    session_id: str,
    decision: str,
    candidate_id: Optional[str] = None,
    org_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> ValidationEvent:
    """L4 — organisational hiring outcome."""
    return record_event(
        session_id=session_id,
        level=ValidationLevel.HIRING_DECISION,
        signal=decision,
        candidate_id=candidate_id,
        org_id=org_id,
        metadata={"notes": notes},
    )


def record_long_term_outcome(
    session_id: str,
    outcome: str,
    candidate_id: Optional[str] = None,
    org_id: Optional[str] = None,
    months_since_hire: Optional[int] = None,
) -> ValidationEvent:
    """L5 — long-term performance signal (highest confidence)."""
    return record_event(
        session_id=session_id,
        level=ValidationLevel.LONG_TERM_OUTCOME,
        signal=outcome,
        candidate_id=candidate_id,
        org_id=org_id,
        metadata={"months_since_hire": months_since_hire},
    )


def compute_platform_knowledge_confidence() -> float:
    """
    Aggregate confidence across all recorded validation events.
    Weighted mean: sum(confidence_i) / n_events.
    Returns 0.0 when no events exist.
    """
    counts = count_validation_events_by_level()
    total_weight = 0.0
    total_events = 0
    for level, cnt in counts.items():
        conf = VALIDATION_CONFIDENCE.get(level, 0.20)
        total_weight += conf * cnt
        total_events += cnt
    if total_events == 0:
        return 0.0
    return round(total_weight / total_events, 4)


def get_recent_events(limit: int = 50) -> List[Dict[str, Any]]:
    return list_validation_events(limit=limit)


def get_events_for_session(session_id: str) -> List[Dict[str, Any]]:
    return list_validation_events(session_id=session_id)
