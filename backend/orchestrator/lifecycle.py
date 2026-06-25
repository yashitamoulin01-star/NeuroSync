"""
Interview session lifecycle — formal state machine.

Every interview session moves through a defined set of states.
Only valid transitions are permitted; invalid transitions raise ValueError.

State diagram:
    CREATED → STREAMING → PAUSED ↔ STREAMING
                        → FINISHING → COMPLETED
    Any state → FAILED (terminal on unrecoverable error)
    COMPLETED, FAILED are terminal (no further transitions)

This module is intentionally kept small — it defines the contract,
not the business logic.  The SessionManager enforces transitions.
"""

from enum import Enum
from typing import Set


class SessionStatus(str, Enum):
    CREATED    = "created"     # session record exists; no WebSocket yet
    STREAMING  = "streaming"   # WebSocket connected; data actively flowing
    PAUSED     = "paused"      # WebSocket disconnected; session preserved in memory
    FINISHING  = "finishing"   # end_session requested; generating final report
    COMPLETED  = "completed"   # session fully written to DB (terminal)
    FAILED     = "failed"      # unrecoverable error (terminal)


# Valid next states for each current state
_TRANSITIONS: dict[SessionStatus, Set[SessionStatus]] = {
    SessionStatus.CREATED:   {SessionStatus.STREAMING, SessionStatus.FAILED},
    SessionStatus.STREAMING: {SessionStatus.PAUSED, SessionStatus.FINISHING, SessionStatus.FAILED},
    SessionStatus.PAUSED:    {SessionStatus.STREAMING, SessionStatus.FINISHING, SessionStatus.FAILED},
    SessionStatus.FINISHING: {SessionStatus.COMPLETED, SessionStatus.FAILED},
    SessionStatus.COMPLETED: set(),
    SessionStatus.FAILED:    set(),
}


def can_transition(current: SessionStatus, target: SessionStatus) -> bool:
    return target in _TRANSITIONS.get(current, set())


def assert_transition(current: SessionStatus, target: SessionStatus) -> None:
    if not can_transition(current, target):
        raise ValueError(
            f"Invalid session lifecycle transition: {current.value} → {target.value}"
        )


def is_terminal(status: SessionStatus) -> bool:
    return status in (SessionStatus.COMPLETED, SessionStatus.FAILED)


def is_active(status: SessionStatus) -> bool:
    """Session is in memory and can receive WebSocket messages."""
    return status in (SessionStatus.CREATED, SessionStatus.STREAMING, SessionStatus.PAUSED)
