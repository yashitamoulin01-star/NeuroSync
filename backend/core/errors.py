"""
Centralized exception hierarchy for the NeuroSync backend.

Every component raises typed, structured exceptions rather than raw strings.
The FastAPI exception handler converts these into consistent JSON responses.
No component exposes raw stack traces to clients.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class NeuroSyncError(Exception):
    """Base exception. All backend errors inherit from this."""

    status_code: int = 500
    error_code:  str = "INTERNAL_ERROR"

    def __init__(
        self,
        message:  str,
        context:  Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.context = context or {}

    def to_dict(self) -> Dict:
        return {
            "error":   self.error_code,
            "message": str(self),
            "context": self.context,
        }


# ── Session errors ─────────────────────────────────────────────────────────────

class SessionNotFoundError(NeuroSyncError):
    status_code = 404
    error_code  = "SESSION_NOT_FOUND"
    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"Session '{session_id}' not found. POST /api/session to create one.",
            {"session_id": session_id},
        )


class SessionExpiredError(NeuroSyncError):
    status_code = 410
    error_code  = "SESSION_EXPIRED"
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session '{session_id}' has expired.", {"session_id": session_id})


class SessionStateError(NeuroSyncError):
    status_code = 409
    error_code  = "SESSION_STATE_ERROR"
    def __init__(self, session_id: str, current: str, attempted: str) -> None:
        super().__init__(
            f"Cannot transition session '{session_id}' from {current} → {attempted}.",
            {"session_id": session_id, "current_state": current, "attempted": attempted},
        )


# ── Inference errors ───────────────────────────────────────────────────────────

class InferenceTimeoutError(NeuroSyncError):
    status_code = 504
    error_code  = "INFERENCE_TIMEOUT"
    def __init__(self, model: str, timeout_s: float) -> None:
        super().__init__(
            f"Model '{model}' inference timed out after {timeout_s:.1f}s.",
            {"model": model, "timeout_seconds": timeout_s},
        )


class ModelUnavailableError(NeuroSyncError):
    status_code = 503
    error_code  = "MODEL_UNAVAILABLE"
    def __init__(self, model: str, reason: str = "") -> None:
        super().__init__(
            f"Model '{model}' is not available. {reason}".strip(),
            {"model": model},
        )


class InsufficientSignalError(NeuroSyncError):
    status_code = 422
    error_code  = "INSUFFICIENT_SIGNAL"
    def __init__(self, session_id: str, reason: str) -> None:
        super().__init__(
            f"Insufficient signal quality for session '{session_id}': {reason}",
            {"session_id": session_id, "reason": reason},
        )


class TranscriptUnavailableError(NeuroSyncError):
    status_code = 422
    error_code  = "TRANSCRIPT_UNAVAILABLE"
    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"No transcript available for session '{session_id}'. Ensure microphone is active.",
            {"session_id": session_id},
        )


# ── Storage errors ─────────────────────────────────────────────────────────────

class StorageError(NeuroSyncError):
    status_code = 500
    error_code  = "STORAGE_ERROR"
    def __init__(self, operation: str, detail: str) -> None:
        super().__init__(
            f"Storage error during '{operation}': {detail}",
            {"operation": operation},
        )


class RecordNotFoundError(NeuroSyncError):
    status_code = 404
    error_code  = "RECORD_NOT_FOUND"
    def __init__(self, resource: str, id: str) -> None:
        super().__init__(
            f"{resource} '{id}' not found in storage.",
            {"resource": resource, "id": id},
        )


# ── Configuration errors ───────────────────────────────────────────────────────

class ConfigurationError(NeuroSyncError):
    status_code = 500
    error_code  = "CONFIGURATION_ERROR"
    def __init__(self, setting: str, detail: str) -> None:
        super().__init__(
            f"Configuration error for '{setting}': {detail}",
            {"setting": setting},
        )
