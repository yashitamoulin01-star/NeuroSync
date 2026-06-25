"""
Behavioral State Machine — tracks the candidate's behavioral trajectory.

Instead of treating every second independently, the backend understands transitions.
This produces more realistic reasoning: a single stressed window doesn't suddenly
label a candidate as stressed if they've been consistently confident.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BehavioralState(str, Enum):
    WARMING_UP  = "warming_up"   # first ~45s, baseline building
    SETTLING    = "settling"     # candidate adjusting to environment
    CONFIDENT   = "confident"    # sustained high confidence + low stress
    HESITATING  = "hesitating"   # confidence dropped, not yet stressed
    RECOVERING  = "recovering"   # rebounding after stress or hesitation
    STRESSED    = "stressed"     # elevated stress with low confidence
    STABLE      = "stable"       # sustained normal performance
    FATIGUED    = "fatigued"     # late-session engagement collapse


@dataclass
class StateTransitionResult:
    previous: BehavioralState
    current:  BehavioralState
    changed:  bool
    reason:   str


def next_state(
    current:         BehavioralState,
    elapsed_seconds: float,
    confidence:      float,
    stress:          float,
    communication:   float,
    engagement:      float,
    pattern:         str,
) -> StateTransitionResult:
    """Compute the next behavioral state from current metrics and pattern."""
    new    = current
    reason = "no_change"

    if current == BehavioralState.WARMING_UP:
        if elapsed_seconds > 45:
            new    = BehavioralState.SETTLING
            reason = "initial_period_complete"

    elif current == BehavioralState.SETTLING:
        if confidence > 0.68 and stress < 0.32:
            new, reason = BehavioralState.CONFIDENT, "high_confidence_low_stress"
        elif stress > 0.62 and confidence < 0.45:
            new, reason = BehavioralState.STRESSED,  "stress_spike_detected"
        elif confidence > 0.55 and stress < 0.45:
            new, reason = BehavioralState.STABLE,    "stable_metrics"
        elif elapsed_seconds > 120:
            new, reason = BehavioralState.STABLE,    "settling_timeout"

    elif current == BehavioralState.CONFIDENT:
        if stress > 0.60:
            new, reason = BehavioralState.STRESSED,   "stress_exceeded_threshold"
        elif confidence < 0.50:
            new, reason = BehavioralState.HESITATING, "confidence_dropped"
        elif engagement < 0.35:
            new, reason = BehavioralState.FATIGUED,   "engagement_collapsed"

    elif current == BehavioralState.STRESSED:
        if confidence > 0.60 and stress < 0.40:
            new, reason = BehavioralState.RECOVERING, "confidence_returning"

    elif current == BehavioralState.HESITATING:
        if confidence > 0.62 and communication > 0.55:
            new, reason = BehavioralState.RECOVERING, "communication_improving"
        elif stress > 0.60:
            new, reason = BehavioralState.STRESSED,   "hesitation_escalated"

    elif current == BehavioralState.RECOVERING:
        if confidence > 0.68 and stress < 0.35:
            new, reason = BehavioralState.STABLE,     "fully_recovered"
        elif confidence < 0.40:
            new, reason = BehavioralState.HESITATING, "recovery_failed"

    elif current == BehavioralState.STABLE:
        if confidence > 0.75 and stress < 0.25:
            new, reason = BehavioralState.CONFIDENT,  "consistently_strong"
        elif stress > 0.60:
            new, reason = BehavioralState.STRESSED,   "late_stress_spike"
        elif engagement < 0.35 and elapsed_seconds > 600:
            new, reason = BehavioralState.FATIGUED,   "late_session_fatigue"

    elif current == BehavioralState.FATIGUED:
        if confidence > 0.60 and engagement > 0.50:
            new, reason = BehavioralState.RECOVERING, "re_engaged"

    return StateTransitionResult(
        previous = current,
        current  = new,
        changed  = (new != current),
        reason   = reason,
    )
