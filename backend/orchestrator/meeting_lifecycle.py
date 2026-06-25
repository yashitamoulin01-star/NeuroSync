"""
Meeting lifecycle — the full, explicit-state machine spanning a meeting from
scheduling through archival (Volume 2B §Meeting Lifecycle).

This is the *outer* lifecycle that capture sources and the dashboard drive. It
wraps but does not replace the in-memory streaming lifecycle in lifecycle.py
(SessionStatus): the RECORDING/LIVE_ANALYSIS/PAUSED phases here correspond to
SessionStatus.STREAMING/PAUSED. Pre-join and post-process phases have no
SessionStatus equivalent — they exist only at the meeting level.

    SCHEDULED → WAITING → JOINING → PERMISSION_CHECK → MEDIA_VALIDATION
      → WARM_UP → READY → RECORDING → LIVE_ANALYSIS
      → (PAUSED ↔ RESUMING) → (RECONNECTING → RECORDING)
      → MEETING_END → PROCESSING → REPORT_GENERATION
      → MEMORY_UPDATE → CBIP_UPDATE → ARCHIVED
    Any non-terminal → FAILED | CANCELED (terminal)

No boolean flags — only explicit states (Volume 2B).
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger("neurosync.orchestrator.meeting")


class MeetingPhase(str, Enum):
    SCHEDULED         = "scheduled"
    WAITING           = "waiting"
    JOINING           = "joining"
    PERMISSION_CHECK  = "permission_check"
    MEDIA_VALIDATION  = "media_validation"
    WARM_UP           = "warm_up"
    READY             = "ready"
    RECORDING         = "recording"
    LIVE_ANALYSIS     = "live_analysis"
    PAUSED            = "paused"
    RESUMING          = "resuming"
    RECONNECTING      = "reconnecting"
    MEETING_END       = "meeting_end"
    PROCESSING        = "processing"
    REPORT_GENERATION = "report_generation"
    MEMORY_UPDATE     = "memory_update"
    CBIP_UPDATE       = "cbip_update"
    ARCHIVED          = "archived"
    FAILED            = "failed"
    CANCELED          = "canceled"


_TERMINAL = {MeetingPhase.ARCHIVED, MeetingPhase.FAILED, MeetingPhase.CANCELED}

_LIVE = {MeetingPhase.RECORDING, MeetingPhase.LIVE_ANALYSIS, MeetingPhase.PAUSED,
         MeetingPhase.RESUMING, MeetingPhase.RECONNECTING}

# Linear "happy path" successors; failure recovery + termination handled separately.
_TRANSITIONS: Dict[MeetingPhase, Set[MeetingPhase]] = {
    MeetingPhase.SCHEDULED:         {MeetingPhase.WAITING, MeetingPhase.JOINING},
    MeetingPhase.WAITING:           {MeetingPhase.JOINING},
    MeetingPhase.JOINING:           {MeetingPhase.PERMISSION_CHECK},
    MeetingPhase.PERMISSION_CHECK:  {MeetingPhase.MEDIA_VALIDATION},
    MeetingPhase.MEDIA_VALIDATION:  {MeetingPhase.WARM_UP},
    MeetingPhase.WARM_UP:           {MeetingPhase.READY},
    MeetingPhase.READY:             {MeetingPhase.RECORDING},
    MeetingPhase.RECORDING:         {MeetingPhase.LIVE_ANALYSIS, MeetingPhase.PAUSED, MeetingPhase.MEETING_END},
    MeetingPhase.LIVE_ANALYSIS:     {MeetingPhase.PAUSED, MeetingPhase.MEETING_END},
    MeetingPhase.PAUSED:            {MeetingPhase.RESUMING, MeetingPhase.MEETING_END},
    MeetingPhase.RESUMING:          {MeetingPhase.LIVE_ANALYSIS, MeetingPhase.RECONNECTING},
    MeetingPhase.RECONNECTING:      {MeetingPhase.RECORDING, MeetingPhase.LIVE_ANALYSIS},
    MeetingPhase.MEETING_END:       {MeetingPhase.PROCESSING},
    MeetingPhase.PROCESSING:        {MeetingPhase.REPORT_GENERATION},
    MeetingPhase.REPORT_GENERATION: {MeetingPhase.MEMORY_UPDATE},
    MeetingPhase.MEMORY_UPDATE:     {MeetingPhase.CBIP_UPDATE},
    MeetingPhase.CBIP_UPDATE:       {MeetingPhase.ARCHIVED},
    MeetingPhase.ARCHIVED:          set(),
    MeetingPhase.FAILED:            set(),
    MeetingPhase.CANCELED:          set(),
}


def is_terminal(phase: MeetingPhase) -> bool:
    return phase in _TERMINAL


def is_live(phase: MeetingPhase) -> bool:
    return phase in _LIVE


def can_transition(current: MeetingPhase, target: MeetingPhase) -> bool:
    if current in _TERMINAL:
        return False
    # Any non-terminal phase may fail or be canceled.
    if target in (MeetingPhase.FAILED, MeetingPhase.CANCELED):
        return True
    return target in _TRANSITIONS.get(current, set())


def session_status_for(phase: MeetingPhase) -> Optional[str]:
    """Map a meeting phase onto the in-memory SessionStatus, where one applies."""
    if phase in (MeetingPhase.RECORDING, MeetingPhase.LIVE_ANALYSIS, MeetingPhase.RECONNECTING, MeetingPhase.RESUMING):
        return "streaming"
    if phase == MeetingPhase.PAUSED:
        return "paused"
    if phase in (MeetingPhase.MEETING_END, MeetingPhase.PROCESSING):
        return "finishing"
    if phase in (MeetingPhase.MEMORY_UPDATE, MeetingPhase.CBIP_UPDATE, MeetingPhase.ARCHIVED, MeetingPhase.REPORT_GENERATION):
        return "completed"
    if phase == MeetingPhase.FAILED:
        return "failed"
    return None  # pre-join phases have no streaming-lifecycle equivalent


class MeetingLifecycle:
    """Tracks a single meeting's phase with enforced transitions and a history log."""

    def __init__(self, meeting_id: str, phase: MeetingPhase = MeetingPhase.SCHEDULED) -> None:
        self.meeting_id = meeting_id
        self.phase = phase
        self.history: List[dict] = [{"phase": phase.value, "at": time.time()}]

    def transition(self, target: MeetingPhase) -> None:
        if not can_transition(self.phase, target):
            raise ValueError(
                f"Invalid meeting transition for {self.meeting_id}: {self.phase.value} → {target.value}"
            )
        logger.info("Meeting %s: %s → %s", self.meeting_id, self.phase.value, target.value)
        self.phase = target
        self.history.append({"phase": target.value, "at": time.time()})

    def to_dict(self) -> dict:
        return {
            "meeting_id":     self.meeting_id,
            "phase":          self.phase.value,
            "session_status": session_status_for(self.phase),
            "is_live":        is_live(self.phase),
            "is_terminal":    is_terminal(self.phase),
            "history":        self.history,
        }
