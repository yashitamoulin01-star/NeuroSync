"""
Internal behavioral labeling API.
Powers the labeling dashboard — queue, session data, label CRUD.
"""

from fastapi import APIRouter, HTTPException

from backend.models.label_schemas import LabelSubmitRequest, SessionLabel
from backend.services.label_service import label_service

router = APIRouter(prefix="/api/label", tags=["labeling"])


@router.get("/stats")
async def label_stats():
    from backend.services.dataset_service import dataset_service
    stats = dataset_service.get_stats()
    return stats


@router.get("/queue")
async def get_queue():
    """Unlabeled sessions waiting for annotation."""
    return {"sessions": label_service.list_unlabeled()}


@router.get("/in-progress")
async def get_in_progress():
    return {"sessions": label_service.list_in_progress()}


@router.get("/completed")
async def get_completed():
    return {"sessions": label_service.list_labeled()}


@router.get("/session/{session_id}")
async def get_session_for_labeling(session_id: str):
    data = label_service.get_session_for_labeling(session_id)
    if not data:
        raise HTTPException(404, "Session not found")
    return data


@router.get("/session/{session_id}/label")
async def get_label(session_id: str):
    label = label_service.get(session_id)
    if not label:
        raise HTTPException(404, "No label found for this session")
    return label


@router.post("/session/{session_id}/label")
async def submit_label(session_id: str, req: LabelSubmitRequest):
    label = label_service.submit(session_id, req)
    return {"status": "saved", "label": label}


@router.delete("/session/{session_id}/label")
async def delete_label(session_id: str):
    label_service.delete(session_id)
    return {"status": "deleted"}
