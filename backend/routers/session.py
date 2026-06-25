"""
HTTP endpoints for session lifecycle management.
"""

import asyncio
import time
import logging
from fastapi import APIRouter, HTTPException
from backend.models.schemas import SessionConfig, SessionSummary
from backend.services.session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["session"])


async def _create_session_impl(config: SessionConfig) -> dict:
    try:
        # create_session does synchronous per-modality init (MediaPipe FaceMesh,
        # media recorder, DB insert). Run it off the event loop so a slow session
        # start never stalls concurrent requests or live WebSocket traffic.
        session_id = await asyncio.to_thread(session_manager.create_session, config)
    except Exception as exc:
        logger.error("Failed to create session: %s", exc)
        raise HTTPException(status_code=503, detail="Session initialization failed. Ensure all services are running.")
    return {
        "session_id": session_id,
        "status": "created",
        "message": f"Session ready. Connect via WebSocket at /ws/session/{session_id}",
    }


@router.post("/session", response_model=dict)
async def create_session(config: SessionConfig):
    return await _create_session_impl(config)


@router.post("/sessions", response_model=dict)
async def create_session_plural(config: SessionConfig):
    """Alias for POST /api/session — accepts plural form used by contract tests."""
    return await _create_session_impl(config)


@router.delete("/session/{session_id}")
async def end_session(session_id: str):
    summary = session_manager.end_session(session_id)
    if summary:
        return summary.model_dump()

    # Session not in memory — it may have already been ended via the WebSocket
    # "end" message. Check the DB so the client gets a proper response.
    try:
        from backend.services.db_service import get_session
        row = get_session(session_id)
        if row and row.get("ended_at"):
            return {
                "session_id": session_id,
                "status": "already_ended",
                "duration": row.get("duration", 0),
                "avg_confidence": row.get("avg_confidence", 0),
                "avg_eye_contact": row.get("avg_eye_contact", 0),
                "avg_stress": row.get("avg_stress", 0),
                "total_filler_words": row.get("total_filler_words", 0),
                "avg_speaking_pace": row.get("avg_speaking_pace", 0),
                "avg_communication_quality": row.get("avg_communication", 0),
                "top_insights": [],
                "transcript": row.get("transcript", ""),
            }
    except Exception as exc:
        logger.debug("DB lookup for ended session %s failed: %s", session_id, exc)

    raise HTTPException(status_code=404, detail="Session not found.")


@router.get("/session/{session_id}/status")
async def session_status(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        # Check DB — session may have ended
        try:
            from backend.services.db_service import get_session
            row = get_session(session_id)
            if row:
                return {
                    "session_id": session_id,
                    "duration": row.get("duration", 0),
                    "mode": row.get("mode", "interview"),
                    "active": False,
                    "ended": True,
                }
        except Exception:
            pass
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "session_id": session_id,
        "duration": round(time.time() - session.started_at, 1),
        "mode": session.config.mode,
        "active": True,
        "ended": False,
    }
