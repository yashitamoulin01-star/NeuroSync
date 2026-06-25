"""
ISessionManager — contract for session lifecycle management.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from backend.models.schemas import SessionConfig, SessionSummary


class ISessionManager(ABC):

    @abstractmethod
    def create_session(self, config: SessionConfig) -> str:
        """Create a new session and return its ID."""
        ...

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Any]:
        """Return the live ActiveSession or None."""
        ...

    @abstractmethod
    def end_session(self, session_id: str) -> Optional[SessionSummary]:
        """Finalize a session, persist its summary, and remove from memory."""
        ...

    @abstractmethod
    def on_ws_connect(self, session_id: str) -> bool:
        """Handle a new WebSocket connection. Returns True on success."""
        ...

    @abstractmethod
    def on_ws_disconnect(self, session_id: str) -> None:
        """Handle a WebSocket disconnection — transitions session to PAUSED."""
        ...
