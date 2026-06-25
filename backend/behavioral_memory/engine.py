"""
Adaptive Behavioral Memory Engine — core logic.

EMA update:  new_ema = alpha * new_value + (1 - alpha) * old_value
Confidence:  grows linearly to 1.0 over 30 observations
Variance:    online Welford's online algorithm (single-pass)

The engine never touches production model weights.  It updates only the
candidate's personal behavioral profile stored in SQLite.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional

from backend.behavioral_memory.models import (
    CandidateProfile, MetricTrace, InterviewHistoryEntry,
    GrowthResponse,
)
from backend.behavioral_memory.repository import (
    get_profile, upsert_profile, append_history, list_history,
)

logger = logging.getLogger(__name__)

EMA_ALPHA = 0.15          # smoothing factor — recent sessions get more weight
CONFIDENCE_HORIZON = 30   # interviews needed to reach full confidence


def _ema(trace: MetricTrace, new_value: float) -> MetricTrace:
    """Return an updated MetricTrace using exponential moving average."""
    old_val   = trace.value if trace.observation_count > 0 else new_value
    n         = trace.observation_count + 1
    new_ema   = EMA_ALPHA * new_value + (1 - EMA_ALPHA) * old_val
    new_conf  = min(1.0, n / CONFIDENCE_HORIZON)

    # Welford's online variance
    delta1  = new_value - old_val
    delta2  = new_value - new_ema
    old_var = trace.variance
    new_var = old_var + (delta1 * delta2 - old_var) / n if n > 1 else 0.0

    return MetricTrace(
        value=round(new_ema, 4),
        observation_count=n,
        confidence=round(new_conf, 4),
        variance=round(abs(new_var), 4),
        last_updated=time.time(),
    )


def update_profile_from_session(candidate_id: str, session: Dict[str, Any]) -> CandidateProfile:
    """
    Pull behavioral metrics from a completed session dict and merge them
    into the candidate's persistent profile via EMA.

    Called by the session history router when a session is finalized.
    """
    profile = get_profile(candidate_id) or CandidateProfile(
        candidate_id=candidate_id, first_seen_at=time.time()
    )

    if profile.learning_paused:
        logger.info("Learning paused for candidate %s — skipping update", candidate_id)
        return profile

    # ── Behavioral averages ───────────────────────────────────────────────────
    bm = profile.behavioral
    bm.avg_confidence    = _ema(bm.avg_confidence,    float(session.get("avg_confidence",    0) or 0))
    bm.avg_engagement    = _ema(bm.avg_engagement,    float(session.get("avg_engagement",    0) or 0))
    bm.avg_communication = _ema(bm.avg_communication, float(session.get("avg_communication", 0) or 0))
    bm.avg_stress        = _ema(bm.avg_stress,        float(session.get("avg_stress",        0) or 0))
    bm.avg_consistency   = _ema(bm.avg_consistency,   float(session.get("avg_consistency",   0) or 0))

    # ── Voice metrics (from avg_speaking_pace, total_filler_words, total_words) ──
    total_words  = max(1, int(session.get("total_words",       0) or 1))
    filler_count = int(session.get("total_filler_words", 0) or 0)
    vm = profile.voice
    vm.speech_rate   = _ema(vm.speech_rate,   float(session.get("avg_speaking_pace", 0) or 0))
    vm.filler_ratio  = _ema(vm.filler_ratio,  filler_count / total_words)

    # ── Face metrics ──────────────────────────────────────────────────────────
    fm = profile.face
    fm.eye_contact = _ema(fm.eye_contact, float(session.get("avg_eye_contact", 0) or 0))

    # ── Update metadata ───────────────────────────────────────────────────────
    profile.total_interviews += 1
    profile.updated_at = time.time()

    # ── Persist ───────────────────────────────────────────────────────────────
    upsert_profile(profile)

    # ── CBIP Layer 3: fire L1 observation + pattern observation ───────────────
    try:
        from backend.behavioral_knowledge.validation_engine import record_observation
        from backend.behavioral_knowledge.pattern_discovery import record_session_observation
        record_observation(
            session_id=str(session.get("id", session.get("session_id", ""))),
            candidate_id=candidate_id,
        )
        record_session_observation(session, candidate_id=candidate_id)
    except Exception as _cbip_err:
        logger.debug("CBIP observation skipped: %s", _cbip_err)

    # ── Append to history ─────────────────────────────────────────────────────
    conf  = float(session.get("avg_confidence",    0) or 0)
    stress = float(session.get("avg_stress",       0) or 0)
    eng   = float(session.get("avg_engagement",    0) or 0)
    comm  = float(session.get("avg_communication", 0) or 0)
    cons  = float(session.get("avg_consistency",   0) or 0)
    composure = 1 - stress
    overall = round((conf + eng + comm + cons + composure) / 5, 4)

    rec = (
        "Proceed"     if overall >= 0.75 and stress < 0.45 else
        "Review"      if overall >= 0.55 else
        "Hold"
    )

    entry = InterviewHistoryEntry(
        session_id=str(session.get("id", session.get("session_id", ""))),
        conducted_at=float(session.get("started_at", time.time()) or time.time()),
        duration=float(session.get("duration", 0) or 0),
        overall_score=overall,
        avg_confidence=conf,
        avg_stress=stress,
        avg_engagement=eng,
        avg_communication=comm,
        avg_consistency=cons,
        recommendation=rec,
    )
    append_history(candidate_id, entry)

    return profile


def _trend(history: List[Dict], key: str, lookback: int = 5) -> str:
    """Compare the most recent interview vs. the prior 'lookback' average."""
    vals = [h.get(key, 0) for h in history if h.get(key) is not None]
    if len(vals) < 2:
        return "stable"
    recent  = vals[0]
    prior   = sum(vals[1:lookback+1]) / max(1, len(vals[1:lookback+1]))
    delta   = recent - prior
    if delta > 0.03:   return "improving"
    if delta < -0.03:  return "declining"
    return "stable"


def build_growth_response(candidate_id: str) -> Optional[GrowthResponse]:
    profile = get_profile(candidate_id)
    if not profile:
        return None

    history = list_history(candidate_id)
    bm = profile.behavioral

    baseline = {
        "confidence":    bm.avg_confidence.value,
        "engagement":    bm.avg_engagement.value,
        "communication": bm.avg_communication.value,
        "composure":     round(1 - bm.avg_stress.value, 4),
        "consistency":   bm.avg_consistency.value,
    }

    confidence_levels = {
        "confidence":    bm.avg_confidence.confidence_label,
        "engagement":    bm.avg_engagement.confidence_label,
        "communication": bm.avg_communication.confidence_label,
        "composure":     bm.avg_stress.confidence_label,
        "consistency":   bm.avg_consistency.confidence_label,
    }

    trend_direction = {
        "confidence":    _trend(history, "avg_confidence"),
        "engagement":    _trend(history, "avg_engagement"),
        "communication": _trend(history, "avg_communication"),
        "composure":     _trend(history, "avg_stress"),
        "consistency":   _trend(history, "avg_consistency"),
    }

    # Coaching focus: the two weakest dimensions — ordered by CBIP effectiveness data when available
    ranked = sorted(baseline.items(), key=lambda kv: kv[1])
    weakest_dims = [k for k, _ in ranked[:2]]

    # Map composure back to its stress dimension for coaching lookup
    weakest_coaching_dims = [d if d != "composure" else "composure" for d in weakest_dims]

    try:
        from backend.behavioral_knowledge.coaching_intelligence import (
            get_evidence_ranked_coaching, record_coaching_delivery,
        )
        coaching_focus = get_evidence_ranked_coaching(candidate_id, weakest_coaching_dims)
        # Record that coaching was delivered for outcome tracking
        if history:
            latest_session_id = history[0].get("session_id", "") if isinstance(history[0], dict) else ""
            if latest_session_id:
                record_coaching_delivery(candidate_id, latest_session_id, weakest_coaching_dims)
    except Exception:
        focus_map = {
            "confidence":    "Practice deliberate vocal pacing and assertive language framing.",
            "engagement":    "Sustain active listening signals: eye contact cadence and response depth.",
            "communication": "Structure responses with clear opening, body, and summary.",
            "composure":     "Apply controlled breathing before high-stakes responses.",
            "consistency":   "Align facial expression with vocal tone for cross-modal coherence.",
        }
        coaching_focus = [focus_map[k] for k in weakest_coaching_dims if k in focus_map]

    history_summary = [
        {
            "session_id":    h["session_id"],
            "conducted_at":  h["conducted_at"],
            "overall_score": h["overall_score"],
            "recommendation": h["recommendation"],
        }
        for h in history[:10]
    ]

    return GrowthResponse(
        candidate_id=candidate_id,
        total_interviews=profile.total_interviews,
        baseline=baseline,
        confidence_levels=confidence_levels,
        trend_direction=trend_direction,
        coaching_focus=coaching_focus,
        overall_growth_score=profile.overall_growth_score(),
        history_summary=history_summary,
    )
