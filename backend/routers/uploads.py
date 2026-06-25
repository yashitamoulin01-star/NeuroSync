"""
Upload router — /api/v1/uploads/*

Asynchronous behavioral analysis of recorded interviews. Uploads are queued and
processed by a background worker; clients poll job status. Completed jobs link to
an ordinary session, so the report surface is identical to a live interview.

POST   /api/v1/uploads            — upload a recording (multipart) → queued job
GET    /api/v1/uploads            — list this tenant's jobs (processing queue)
GET    /api/v1/uploads/{id}       — job status / progress
POST   /api/v1/uploads/{id}/retry — requeue a failed job
DELETE /api/v1/uploads/{id}       — delete a job and its stored file
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.authentication.middleware import AuthContext, require_permission
from backend.core.config import settings
from backend.rbac.permissions import Permission
from backend.uploads.models import ALLOWED_EXTS
from backend.uploads.service import upload_service

logger = logging.getLogger("neurosync.routers.uploads")
router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])

_MAX_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024


@router.post("")
async def create_upload(
    file: UploadFile = File(...),
    mode: str = Form("interview"),
    candidate_name: str = Form(""),
    ctx: AuthContext = Depends(require_permission(Permission.SESSION_CREATE)),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTS)}")
    if mode not in ("interview", "coaching", "presentation"):
        raise HTTPException(400, "Invalid mode")

    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > _MAX_BYTES:
        raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_MB} MB limit")

    job = upload_service.create_job(
        filename=file.filename or f"upload{ext}", ext=ext, data=data,
        tenant_id=ctx.tenant_id, org_id=ctx.org_id, created_by=ctx.user_id,
        mode=mode, candidate_name=candidate_name,
    )
    return {"job": job.to_dict(), "message": "Upload queued for analysis."}


@router.get("")
async def list_uploads(ctx: AuthContext = Depends(require_permission(Permission.SESSION_READ))):
    jobs = upload_service.list_for_tenant(ctx.tenant_id)
    return {"jobs": [j.to_dict() for j in jobs], "count": len(jobs)}


@router.get("/{job_id}")
async def get_upload(job_id: str, ctx: AuthContext = Depends(require_permission(Permission.SESSION_READ))):
    job = upload_service.get(job_id, ctx.tenant_id)
    if not job:
        raise HTTPException(404, "Upload job not found")
    return job.to_dict()


@router.post("/{job_id}/retry")
async def retry_upload(job_id: str, ctx: AuthContext = Depends(require_permission(Permission.SESSION_CREATE))):
    if not upload_service.retry(job_id, ctx.tenant_id):
        raise HTTPException(409, "Job not found or not in a retryable state")
    return {"ok": True, "job_id": job_id, "status": "queued"}


@router.delete("/{job_id}")
async def delete_upload(job_id: str, ctx: AuthContext = Depends(require_permission(Permission.SESSION_DELETE))):
    if not upload_service.delete(job_id, ctx.tenant_id):
        raise HTTPException(404, "Upload job not found")
    return {"ok": True, "job_id": job_id}
