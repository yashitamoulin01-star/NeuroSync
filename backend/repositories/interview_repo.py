"""
Interview Repository — single access point for interview persistence.

Business logic never touches the database directly.
SQLite is an implementation detail. Swapping to PostgreSQL requires
only replacing this class — zero business logic changes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import backend.services.db_service as db
from backend.core.interfaces.storage import IInterviewRepository
from backend.core.errors import StorageError, RecordNotFoundError

logger = logging.getLogger(__name__)


class SQLiteInterviewRepository(IInterviewRepository):
    """SQLite-backed interview repository."""

    def get_by_id(self, session_id: str) -> Optional[Dict]:
        try:
            return db.get_session(session_id)
        except Exception as e:
            raise StorageError("get_by_id", str(e)) from e

    def list_recent(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        try:
            return db.list_sessions(limit=limit, offset=offset)
        except Exception as e:
            raise StorageError("list_recent", str(e)) from e

    def record_frame(self, session_id: str, frame_data: Dict) -> None:
        try:
            db.record_frame(
                session_id  = session_id,
                ts          = frame_data.get("ts", 0.0),
                confidence  = frame_data.get("confidence", 0.0),
                stress      = frame_data.get("stress", 0.0),
                engagement  = frame_data.get("engagement", 0.0),
                communication = frame_data.get("communication", 0.0),
                consistency = frame_data.get("consistency", 0.0),
                eye_contact = frame_data.get("eye_contact", 0.0),
                is_speaking = frame_data.get("is_speaking", False),
            )
        except Exception as e:
            logger.debug("Frame write failed for %s: %s", session_id, e)

    def finalize(self, session_id: str, summary: Dict) -> None:
        try:
            db.finalize_session(
                session_id         = session_id,
                ended_at           = summary.get("ended_at", 0.0),
                duration           = summary.get("duration", 0.0),
                avg_confidence     = summary.get("avg_confidence", 0.0),
                avg_stress         = summary.get("avg_stress", 0.0),
                avg_engagement     = summary.get("avg_engagement", 0.0),
                avg_communication  = summary.get("avg_communication", 0.0),
                avg_consistency    = summary.get("avg_consistency", 0.0),
                avg_eye_contact    = summary.get("avg_eye_contact", 0.0),
                avg_speaking_pace  = summary.get("avg_speaking_pace", 0.0),
                total_filler_words = summary.get("total_filler_words", 0),
                total_words        = summary.get("total_words", 0),
                transcript         = summary.get("transcript", ""),
                insights           = summary.get("insights", []),
            )
        except Exception as e:
            raise StorageError("finalize", str(e)) from e

    def delete(self, session_id: str) -> None:
        try:
            db.delete_session(session_id)
        except Exception as e:
            logger.warning("Delete failed for %s: %s", session_id, e)


# Module-level singleton — replace with PostgreSQLInterviewRepository to migrate
interview_repository: IInterviewRepository = SQLiteInterviewRepository()
