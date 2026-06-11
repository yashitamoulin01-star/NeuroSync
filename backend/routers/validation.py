"""
Dataset validation API.
GET /api/validation/summary                — overall dataset health (fast estimate)
GET /api/validation/sessions?limit&offset  — paginated per-session health
GET /api/validation/session/{id}           — single session health
"""

from fastapi import APIRouter
from backend.services.validation_service import validation_service

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.get("/summary")
async def get_validation_summary():
    return validation_service.summary()


@router.get("/sessions")
async def get_all_session_health(limit: int = 200, offset: int = 0):
    return validation_service.validate_all(limit=limit, offset=offset)


@router.get("/session/{session_id}")
async def get_session_health(session_id: str):
    return validation_service.validate_session(session_id).to_dict()
