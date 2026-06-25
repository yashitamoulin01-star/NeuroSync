"""
CBIP — Pattern Discovery.

Discovers which behavioral archetypes recur across candidates and
organisations.  Patterns are NOT hardcoded rules — they are seed
archetypes whose confidence grows as validated observations accumulate.

A pattern gains confidence when:
  • Many sessions match its dimensional thresholds (observation count)
  • Those sessions also carry higher-level validation (recruiter/hiring)
  • The mean validation confidence of matching sessions is high

The production reasoning engine is NOT modified.  Discovered patterns
enrich the knowledge base consulted during coaching and reporting.
"""

from __future__ import annotations
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.behavioral_knowledge.models import PatternObservation, SEED_PATTERNS
from backend.behavioral_knowledge.repository import (
    insert_pattern_observation,
    get_all_observations,
    get_all_patterns,
    update_pattern_stats,
    count_total_observations,
    get_session_validation_confidence,
)

logger = logging.getLogger(__name__)

_DIM_KEYS = [
    "avg_confidence", "avg_engagement", "avg_communication",
    "avg_stress", "avg_consistency",
]


def record_session_observation(
    session: Dict[str, Any],
    candidate_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> PatternObservation:
    """
    Store a lightweight metric snapshot from a completed session so that
    pattern discovery can analyse it alongside all other sessions.
    Called automatically when behavioral memory is updated.
    """
    session_id = str(session.get("id", session.get("session_id", "")))

    # Pull the highest validation confidence already recorded for this session
    val_conf = get_session_validation_confidence(session_id)

    obs = PatternObservation(
        obs_id=str(uuid.uuid4()),
        session_id=session_id,
        candidate_id=candidate_id,
        org_id=org_id,
        avg_confidence=float(session.get("avg_confidence",    0) or 0),
        avg_engagement=float(session.get("avg_engagement",    0) or 0),
        avg_communication=float(session.get("avg_communication", 0) or 0),
        avg_stress=float(session.get("avg_stress",           0) or 0),
        avg_consistency=float(session.get("avg_consistency",  0) or 0),
        overall_score=float(session.get("overall_score",     0) or 0),
        validation_confidence=val_conf,
        recorded_at=time.time(),
    )
    insert_pattern_observation(obs)
    return obs


def _obs_matches_pattern(obs: Dict[str, Any], dims: List[str], threshold: float) -> bool:
    """Return True when all listed dimensions meet or exceed the threshold."""
    for dim in dims:
        val = obs.get(dim, 0.0) or 0.0
        # For stress the pattern checks for LOW stress (composure), so invert
        if dim == "avg_stress":
            if 1.0 - val < threshold:
                return False
        else:
            if val < threshold:
                return False
    return True


def refresh_pattern_stats() -> List[Dict[str, Any]]:
    """
    Re-compute observation counts and confidence for every seed pattern.
    Should be called after new sessions are ingested (triggered automatically
    via record_session_observation in the router).  Cheap for typical DB sizes.
    """
    observations = get_all_observations(limit=10_000)
    patterns     = get_all_patterns()

    summary = []
    for pat in patterns:
        dims      = pat.dimensions
        threshold = pat.threshold

        matching = [o for o in observations if _obs_matches_pattern(o, dims, threshold)]
        obs_count = len(matching)

        if obs_count == 0:
            update_pattern_stats(pat.pattern_id, 0, 0, 0.0)
            summary.append({
                "pattern_id": pat.pattern_id,
                "name": pat.name,
                "observation_count": 0,
                "validated_count": 0,
                "confidence": 0.0,
            })
            continue

        # Validated = observations that carry recruiter or hiring-level confidence
        validated = [o for o in matching if o.get("validation_confidence", 0.20) >= 0.70]
        val_count = len(validated)

        # Confidence: fraction validated × mean validation confidence of all matching obs
        mean_conf = sum(o.get("validation_confidence", 0.20) for o in matching) / obs_count
        if obs_count >= 5:
            pattern_conf = round(
                (val_count / obs_count) * mean_conf
                + (1 - val_count / obs_count) * mean_conf * 0.4,
                4,
            )
        else:
            # Not enough data — confidence stays provisional
            pattern_conf = round(mean_conf * 0.3, 4)

        update_pattern_stats(pat.pattern_id, obs_count, val_count, pattern_conf)
        summary.append({
            "pattern_id":        pat.pattern_id,
            "name":              pat.name,
            "observation_count": obs_count,
            "validated_count":   val_count,
            "confidence":        pattern_conf,
        })

    logger.debug("CBIP pattern refresh: %d patterns updated", len(summary))
    return summary


def get_patterns_for_api() -> List[Dict[str, Any]]:
    """Return all patterns serialised for the API response."""
    patterns = get_all_patterns()
    result = []
    for p in patterns:
        result.append({
            "pattern_id":        p.pattern_id,
            "name":              p.name,
            "description":       p.description,
            "dimensions":        p.dimensions,
            "threshold":         p.threshold,
            "observation_count": p.observation_count,
            "validated_count":   p.validated_count,
            "confidence":        p.confidence,
            "confidence_label":  _conf_label(p.confidence),
            "updated_at":        p.updated_at,
        })
    return result


def _conf_label(c: float) -> str:
    if c >= 0.60: return "validated"
    if c >= 0.30: return "emerging"
    if c > 0:     return "provisional"
    return "insufficient_data"
