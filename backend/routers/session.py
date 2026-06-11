"""
HTTP endpoints for session lifecycle management.
"""

from fastapi import APIRouter, HTTPException
from backend.models.schemas import SessionConfig, SessionSummary
from backend.services.session_manager import session_manager

router = APIRouter(prefix="/api", tags=["session"])


@router.post("/session", response_model=dict)
async def create_session(config: SessionConfig):
    session_id = session_manager.create_session(config)
    return {
        "session_id": session_id,
        "status": "created",
        "message": f"Session created. Connect via WebSocket at /ws/session/{session_id}",
    }


@router.delete("/session/{session_id}", response_model=SessionSummary)
async def end_session(session_id: str):
    summary = session_manager.end_session(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found or already ended.")
    return summary


@router.get("/session/{session_id}/status")
async def session_status(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    import time
    return {
        "session_id": session_id,
        "duration": round(time.time() - session.started_at, 1),
        "mode": session.config.mode,
        "active": True,
    }
