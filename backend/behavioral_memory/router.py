"""
Adaptive Behavioral Memory Engine — REST API router.

Prefix: /behavior

GET  /behavior/profile/{candidate_id}          — full profile
GET  /behavior/profile/{candidate_id}/growth   — growth metrics + coaching
GET  /behavior/profile/{candidate_id}/history  — interview history list
POST /behavior/update                          — update from completed session
POST /behavior/profile/{candidate_id}/pause    — pause learning
POST /behavior/profile/{candidate_id}/resume   — resume learning
DELETE /behavior/profile/{candidate_id}        — delete profile (privacy)
"""

import logging
from fastapi import APIRouter, HTTPException

from backend.behavioral_memory.models import ProfileUpdateRequest
from backend.behavioral_memory.repository import (
    get_profile, delete_profile, set_learning_paused, list_history,
)
from backend.behavioral_memory.engine import update_profile_from_session, build_growth_response
from backend.services.db_service import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/behavior", tags=["behavioral-memory"])


@router.get("/profile/{candidate_id}")
def get_candidate_profile(candidate_id: str):
    profile = get_profile(candidate_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile.model_dump()


@router.get("/profile/{candidate_id}/growth")
def get_growth(candidate_id: str):
    result = build_growth_response(candidate_id)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found — complete at least one interview first")
    return result.model_dump()


@router.get("/profile/{candidate_id}/history")
def get_history(candidate_id: str):
    profile = get_profile(candidate_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"candidate_id": candidate_id, "history": list_history(candidate_id)}


@router.post("/update")
def update_from_session(req: ProfileUpdateRequest):
    """Trigger a behavioral profile update from a completed session."""
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {req.session_id} not found")
    profile = update_profile_from_session(req.candidate_id, dict(session))
    return {
        "candidate_id":    req.candidate_id,
        "total_interviews": profile.total_interviews,
        "updated_at":      profile.updated_at,
        "overall_growth_score": profile.overall_growth_score(),
    }


@router.post("/profile/{candidate_id}/pause")
def pause_learning(candidate_id: str):
    profile = get_profile(candidate_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    set_learning_paused(candidate_id, True)
    return {"candidate_id": candidate_id, "learning_paused": True}


@router.post("/profile/{candidate_id}/resume")
def resume_learning(candidate_id: str):
    profile = get_profile(candidate_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    set_learning_paused(candidate_id, False)
    return {"candidate_id": candidate_id, "learning_paused": False}


@router.delete("/profile/{candidate_id}")
def delete_candidate_profile(candidate_id: str):
    deleted = delete_profile(candidate_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"candidate_id": candidate_id, "deleted": True}
