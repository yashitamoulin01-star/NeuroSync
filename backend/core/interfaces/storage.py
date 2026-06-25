"""
IInterviewRepository — contract for interview data persistence.

Business logic never touches SQLite directly. All storage goes through
a repository that implements this interface. Swapping SQLite → PostgreSQL
requires only a new implementation — no business logic changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IInterviewRepository(ABC):

    @abstractmethod
    def get_by_id(self, session_id: str) -> Optional[Dict]: ...

    @abstractmethod
    def list_recent(self, limit: int = 50, offset: int = 0) -> List[Dict]: ...

    @abstractmethod
    def record_frame(self, session_id: str, frame_data: Dict) -> None: ...

    @abstractmethod
    def finalize(self, session_id: str, summary: Dict) -> None: ...

    @abstractmethod
    def delete(self, session_id: str) -> None: ...


class IEvidenceRepository(ABC):

    @abstractmethod
    def save_traces(self, session_id: str, traces: List[Dict]) -> None: ...

    @abstractmethod
    def get_traces(self, session_id: str) -> List[Dict]: ...
