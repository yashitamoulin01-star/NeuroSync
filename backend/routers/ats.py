"""
ATS router — /api/v1/ats/*

Connect Applicant Tracking Systems, export behavioral reports back into them, and
sync candidate records. Connection management uses CONNECTOR_MANAGE; exporting
reuses SESSION_EXPORT (recruiters). Tokens never leave the service.

GET    /api/v1/ats/available             — adapter catalog
GET    /api/v1/ats                        — list tenant ATS connections
POST   /api/v1/ats/{provider}/connect     — begin OAuth (returns authorize_url)
GET    /api/v1/ats/oauth/callback         — OAuth redirect handler
POST   /api/v1/ats/{id}/refresh           — refresh tokens
POST   /api/v1/ats/{id}/test              — test connection
DELETE /api/v1/ats/{id}                   — disconnect
POST   /api/v1/ats/{id}/export            — push a session report to the ATS
POST   /api/v1/ats/{id}/sync              — sync candidate roster
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from backend.ats.service import ATSError, ats_service
from backend.authentication.middleware import AuthContext, require_permission
from backend.rbac.permissions import Permission

router = APIRouter(prefix="/api/v1/ats", tags=["ats"])


@router.get("/available")
async def available(ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_VIEW))):
    return {"providers": ats_service.list_available()}


@router.get("")
async def list_connections(ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_VIEW))):
    records = ats_service.list_for_org(ctx.tenant_id, ctx.org_id)
    return {"connections": [r.to_public_dict() for r in records], "count": len(records)}


@router.post("/{provider}/connect")
async def connect(
    provider: str,
    redirect_uri: str = Body(..., embed=True),
    name: str | None = Body(None, embed=True),
    ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_MANAGE)),
):
    try:
        return ats_service.begin_connect(provider, ctx.tenant_id, ctx.org_id, ctx.user_id, redirect_uri, name)
    except ATSError as exc:
        raise HTTPException(400, str(exc))


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_MANAGE)),
):
    connection_id = state.split(":", 1)[0]
    try:
        record = await ats_service.complete_connect(connection_id, ctx.tenant_id, code, "oauth/callback")
    except ATSError as exc:
        raise HTTPException(400, str(exc))
    return record.to_public_dict()


@router.post("/{connection_id}/refresh")
async def refresh(connection_id: str, ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_MANAGE))):
    try:
        return (await ats_service.refresh(connection_id, ctx.tenant_id)).to_public_dict()
    except ATSError as exc:
        raise HTTPException(400, str(exc))


@router.post("/{connection_id}/test")
async def test(connection_id: str, ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_MANAGE))):
    try:
        return await ats_service.test(connection_id, ctx.tenant_id)
    except ATSError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/{connection_id}")
async def disconnect(connection_id: str, ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_MANAGE))):
    if not ats_service.disconnect(connection_id, ctx.tenant_id):
        raise HTTPException(404, "ATS connection not found")
    return {"ok": True, "connection_id": connection_id, "status": "disconnected"}


@router.post("/{connection_id}/export")
async def export_report(
    connection_id: str,
    session_id: str = Body(..., embed=True),
    ctx: AuthContext = Depends(require_permission(Permission.SESSION_EXPORT)),
):
    try:
        return await ats_service.export_report(connection_id, ctx.tenant_id, session_id)
    except ATSError as exc:
        raise HTTPException(400, str(exc))


@router.post("/{connection_id}/sync")
async def sync_candidates(connection_id: str, ctx: AuthContext = Depends(require_permission(Permission.SESSION_EXPORT))):
    try:
        candidates = await ats_service.sync_candidates(connection_id, ctx.tenant_id)
    except ATSError as exc:
        raise HTTPException(400, str(exc))
    return {"candidates": candidates, "count": len(candidates)}
