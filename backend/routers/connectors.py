"""
Connector router — /api/v1/connectors/*

Secure, RBAC-guarded management of external meeting-provider connections.
Token material is never exposed; only status + metadata are returned.

GET    /api/v1/connectors/available           — provider catalog
GET    /api/v1/connectors                      — list this tenant's connectors
GET    /api/v1/connectors/{id}                 — connector detail (status/metadata)
GET    /api/v1/connectors/{id}/permissions     — granted OAuth scopes
GET    /api/v1/connectors/{id}/meetings        — upcoming meetings
POST   /api/v1/connectors/{provider}/connect   — begin OAuth (returns authorize_url)
GET    /api/v1/connectors/oauth/callback       — OAuth redirect handler
POST   /api/v1/connectors/{id}/refresh         — refresh tokens
POST   /api/v1/connectors/{id}/test            — test connection
DELETE /api/v1/connectors/{id}                 — disconnect (wipes tokens)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from backend.authentication.middleware import AuthContext, require_permission
from backend.connectors.service import ConnectorError, connector_service
from backend.rbac.permissions import Permission

logger = logging.getLogger("neurosync.routers.connectors")
router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])


@router.get("/available")
async def available_connectors(ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_VIEW))):
    return {"providers": connector_service.list_available()}


@router.get("")
async def list_connectors(ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_VIEW))):
    records = connector_service.list_for_org(ctx.tenant_id, ctx.org_id)
    return {"connectors": [r.to_public_dict() for r in records], "count": len(records)}


@router.get("/{connector_id}")
async def get_connector(connector_id: str, ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_VIEW))):
    record = connector_service.get(connector_id, ctx.tenant_id)
    if not record:
        raise HTTPException(404, "Connector not found")
    return record.to_public_dict()


@router.get("/{connector_id}/permissions")
async def connector_permissions(connector_id: str, ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_VIEW))):
    record = connector_service.get(connector_id, ctx.tenant_id)
    if not record:
        raise HTTPException(404, "Connector not found")
    return {
        "connector_id": connector_id,
        "scopes":       record.scopes,
        "capabilities": record.capabilities.to_dict(),
    }


@router.get("/meetings/upcoming")
async def upcoming_meetings(ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_VIEW))):
    """Aggregated upcoming interviews across all connected providers."""
    meetings = await connector_service.list_all_upcoming(ctx.tenant_id, ctx.org_id)
    return {"meetings": meetings, "count": len(meetings)}


@router.get("/{connector_id}/meetings")
async def connector_meetings(connector_id: str, ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_VIEW))):
    try:
        meetings = await connector_service.list_upcoming_meetings(connector_id, ctx.tenant_id)
    except ConnectorError as exc:
        raise HTTPException(400, str(exc))
    return {"meetings": [m.to_dict() for m in meetings], "count": len(meetings)}


@router.post("/{provider}/connect")
async def connect(
    provider: str,
    redirect_uri: str = Body(..., embed=True),
    name: str | None = Body(None, embed=True),
    ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_MANAGE)),
):
    try:
        return connector_service.begin_connect(
            provider=provider, tenant_id=ctx.tenant_id, org_id=ctx.org_id,
            created_by=ctx.user_id, redirect_uri=redirect_uri, name=name,
        )
    except ConnectorError as exc:
        raise HTTPException(400, str(exc))


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_MANAGE)),
):
    # state = "<connector_id>:<nonce>" — bind the callback to the initiating connector.
    connector_id = state.split(":", 1)[0]
    redirect_uri = "oauth/callback"
    try:
        record = await connector_service.complete_connect(connector_id, ctx.tenant_id, code, redirect_uri)
    except ConnectorError as exc:
        raise HTTPException(400, str(exc))
    return record.to_public_dict()


@router.post("/{connector_id}/refresh")
async def refresh_connector(connector_id: str, ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_MANAGE))):
    try:
        record = await connector_service.refresh(connector_id, ctx.tenant_id)
    except ConnectorError as exc:
        raise HTTPException(400, str(exc))
    return record.to_public_dict()


@router.post("/{connector_id}/test")
async def test_connector(connector_id: str, ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_MANAGE))):
    try:
        return await connector_service.test(connector_id, ctx.tenant_id)
    except ConnectorError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/{connector_id}")
async def disconnect_connector(connector_id: str, ctx: AuthContext = Depends(require_permission(Permission.CONNECTOR_MANAGE))):
    ok = connector_service.disconnect(connector_id, ctx.tenant_id)
    if not ok:
        raise HTTPException(404, "Connector not found")
    return {"ok": True, "connector_id": connector_id, "status": "disconnected"}
