"""
Analytics REST endpoints for fetching session analytics snapshots.
"""

from fastapi import APIRouter, HTTPException
from backend.services.session_manager import session_manager
from backend.models.schemas import FusedAnalytics

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/{session_id}", response_model=FusedAnalytics)
async def get_analytics(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    fused = session.fusion_bridge.get_fused()
    session.last_analytics = fused
    return fused


@router.get("/analytics/{session_id}/transcript")
async def get_transcript(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    return {
        "session_id": session_id,
        "transcript": session.audio_service.get_full_transcript(),
        "total_filler_words": session.nlp_service.session_filler_total,
    }
