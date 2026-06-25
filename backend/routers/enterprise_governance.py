"""
Enterprise Governance Router.

Covers audit, compliance, data requests, report versioning, and policy management.

GET  /api/v1/audit/events            — query audit log
GET  /api/v1/audit/summary           — audit action summary
POST /api/v1/audit/export            — export audit bundle

GET  /api/v1/compliance/summary      — compliance posture
POST /api/v1/compliance/retention    — create retention policy
GET  /api/v1/compliance/retention    — list retention policies
POST /api/v1/compliance/consent      — record consent
GET  /api/v1/compliance/consent/{id} — get active consents for subject
POST /api/v1/compliance/requests     — create data subject request
GET  /api/v1/compliance/requests     — list data requests

POST /api/v1/reports/{session_id}    — generate immutable report
GET  /api/v1/reports/{session_id}    — latest report for session
GET  /api/v1/reports/{session_id}/versions — all versions
GET  /api/v1/reports/{report_id}/verify    — verify integrity
POST /api/v1/reports/{report_id}/approve   — approve report
POST /api/v1/reports/{report_id}/reject    — reject report
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from backend.authentication.middleware import AuthContext, require_auth, require_permission
from backend.rbac.permissions import Permission

router = APIRouter(prefix="/api/v1", tags=["Enterprise Governance"])


# ── Audit ─────────────────────────────────────────────────────────────────────

@router.get("/audit/events", summary="Query the audit event log")
async def get_audit_events(
    ctx:           AuthContext = Depends(require_permission(Permission.AUDIT_READ)),
    actor_id:      Optional[str] = None,
    action:        Optional[str] = None,
    resource_type: Optional[str] = None,
    severity:      Optional[str] = None,
    since:         Optional[float] = Query(None, description="Unix timestamp (from)"),
    until:         Optional[float] = Query(None, description="Unix timestamp (to)"),
    limit:         int = Query(50, le=500),
    offset:        int = 0,
):
    from backend.audit_center.service import audit_service
    events = audit_service.query(
        tenant_id=ctx.tenant_id, actor_id=actor_id, action=action,
        resource_type=resource_type, severity=severity,
        since=since, until=until, limit=limit, offset=offset,
    )
    total = audit_service.count(ctx.tenant_id)
    return {
        "events": [e.to_dict() for e in events],
        "count":  len(events),
        "total":  total,
    }


@router.get("/audit/summary", summary="Audit action summary for the last 30 days")
async def audit_summary(
    ctx:  AuthContext = Depends(require_permission(Permission.AUDIT_READ)),
    days: int = Query(30, le=365),
):
    from backend.audit_center.service import audit_service
    since = time.time() - (days * 86400)
    return {
        "tenant_id": ctx.tenant_id,
        "period_days": days,
        "actions":   audit_service.summary_by_action(ctx.tenant_id, since),
    }


@router.post("/audit/export", summary="Export audit bundle for a time range")
async def export_audit(
    request: Request,
    ctx:     AuthContext = Depends(require_permission(Permission.AUDIT_EXPORT)),
    payload: Dict = Body(...),
):
    from backend.exports.service import export_service
    since = payload.get("since", time.time() - 86400 * 30)
    until = payload.get("until", time.time())
    bundle = export_service.export_audit_bundle(
        tenant_id=ctx.tenant_id, requested_by=ctx.user_id, since=since, until=until
    )
    return bundle


# ── Compliance ────────────────────────────────────────────────────────────────

@router.get("/compliance/summary", summary="Compliance posture overview")
async def compliance_summary(
    ctx: AuthContext = Depends(require_permission(Permission.COMPLIANCE_VIEW)),
):
    from backend.compliance.service import compliance_service
    return compliance_service.get_compliance_summary(ctx.tenant_id)


@router.post("/compliance/retention", summary="Create or update a data retention policy")
async def create_retention_policy(
    request: Request,
    ctx:     AuthContext = Depends(require_permission(Permission.COMPLIANCE_MANAGE)),
    payload: Dict = Body(...),
):
    from backend.compliance.service import compliance_service
    from backend.audit_center.service import audit_service

    if not ctx.org_id:
        raise HTTPException(400, "Organization context required")
    try:
        policy = compliance_service.create_retention_policy(
            org_id        = ctx.org_id,
            tenant_id     = ctx.tenant_id,
            name          = payload.get("name", ""),
            resource_type = payload.get("resource_type", "sessions"),
            retain_days   = int(payload.get("retain_days", 365)),
            action_after  = payload.get("action_after", "soft_delete"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id, action="config.changed",
        resource_type="retention_policy", resource_id=policy.policy_id, ctx=request,
    )
    return policy.to_dict()


@router.get("/compliance/retention", summary="List data retention policies")
async def list_retention_policies(
    ctx: AuthContext = Depends(require_permission(Permission.COMPLIANCE_VIEW)),
):
    from backend.compliance.service import compliance_service
    if not ctx.org_id:
        raise HTTPException(400, "Organization context required")
    policies = compliance_service.list_retention_policies(ctx.tenant_id, ctx.org_id)
    return {"policies": [p.to_dict() for p in policies]}


@router.post("/compliance/consent", summary="Record consent for a subject")
async def record_consent(
    request: Request,
    ctx:     AuthContext = Depends(require_auth),
    payload: Dict = Body(...),
):
    from backend.compliance.service import compliance_service
    ip = request.client.host if request.client else ""
    try:
        record = compliance_service.record_consent(
            tenant_id  = ctx.tenant_id,
            subject_id = payload.get("subject_id", ctx.user_id),
            purpose    = payload.get("purpose", ""),
            granted    = bool(payload.get("granted", True)),
            ip_address = ip,
            version    = payload.get("version", "1.0"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return record.to_dict()


@router.get("/compliance/consent/{subject_id}", summary="Get active consents for a subject")
async def get_consents(
    subject_id: str,
    ctx:        AuthContext = Depends(require_permission(Permission.COMPLIANCE_VIEW)),
):
    from backend.compliance.service import compliance_service
    consents = compliance_service.get_active_consents(ctx.tenant_id, subject_id)
    return {"subject_id": subject_id, "active_consents": [c.to_dict() for c in consents]}


@router.post("/compliance/requests", summary="Submit a data subject access request")
async def create_data_request(
    request: Request,
    ctx:     AuthContext = Depends(require_auth),
    payload: Dict = Body(...),
):
    from backend.compliance.service import compliance_service
    from backend.audit_center.service import audit_service
    try:
        req = compliance_service.create_data_request(
            tenant_id    = ctx.tenant_id,
            subject_id   = payload.get("subject_id", ctx.user_id),
            request_type = payload.get("request_type", "export"),
            notes        = payload.get("notes"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id,
        action="compliance.data_export_requested" if req.request_type == "export"
               else "compliance.data_erasure_requested",
        resource_type="data_request", resource_id=req.request_id, ctx=request,
    )
    return req.to_dict()


@router.get("/compliance/requests", summary="List data subject access requests")
async def list_data_requests(
    ctx:    AuthContext = Depends(require_permission(Permission.DATA_REQUEST_MANAGE)),
    status: Optional[str] = None,
):
    from backend.compliance.service import compliance_service
    requests = compliance_service.list_data_requests(ctx.tenant_id, status=status)
    return {"requests": [r.to_dict() for r in requests], "count": len(requests)}


# ── Report Versioning ─────────────────────────────────────────────────────────

@router.post("/reports/{session_id}", summary="Generate an immutable report version")
async def generate_report(
    session_id: str,
    request:    Request,
    ctx:        AuthContext = Depends(require_permission(Permission.REPORT_GENERATE)),
    payload:    Dict = Body(default={}),
):
    from backend.reports.versioning import report_versioning
    from backend.audit_center.service import audit_service

    scores   = payload.get("scores",   {})
    evidence = payload.get("evidence", {})
    config   = payload.get("config",   {})

    if not scores:
        # Auto-pull from DB if scores not provided
        from backend.services.db_service import _DB_PATH
        import sqlite3
        con = sqlite3.connect(str(_DB_PATH))
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        con.close()
        if row:
            scores = {
                "confidence":    row["avg_confidence"],
                "stress":        row["avg_stress"],
                "engagement":    row["avg_engagement"],
                "communication": row["avg_communication"],
                "consistency":   row["avg_consistency"],
            }

    report = report_versioning.generate(
        session_id   = session_id,
        tenant_id    = ctx.tenant_id,
        generated_by = ctx.user_id,
        scores       = scores,
        evidence     = evidence,
        org_id       = ctx.org_id,
        config       = config,
    )
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id, action="report.generated",
        resource_type="report", resource_id=report.report_id, ctx=request,
    )
    return report.to_dict(include_evidence=False)


@router.get("/reports/{session_id}/latest", summary="Latest report version for a session")
async def get_latest_report(
    session_id: str,
    ctx:        AuthContext = Depends(require_permission(Permission.REPORT_VIEW)),
):
    from backend.reports.versioning import report_versioning
    report = report_versioning.get_latest(session_id, ctx.tenant_id)
    if report is None:
        raise HTTPException(404, f"No report found for session {session_id}")
    return report.to_dict()


@router.get("/reports/{session_id}/versions", summary="All report versions for a session")
async def list_report_versions(
    session_id: str,
    ctx:        AuthContext = Depends(require_permission(Permission.REPORT_VIEW)),
):
    from backend.reports.versioning import report_versioning
    versions = report_versioning.list_versions(session_id, ctx.tenant_id)
    return {
        "session_id": session_id,
        "count":      len(versions),
        "versions":   [v.to_dict(include_evidence=False) for v in versions],
    }


@router.get("/reports/verify/{report_id}", summary="Verify report integrity")
async def verify_report(
    report_id: str,
    ctx:       AuthContext = Depends(require_permission(Permission.REPORT_VIEW)),
):
    from backend.reports.versioning import report_versioning
    return report_versioning.verify_report(report_id, ctx.tenant_id)


@router.post("/reports/approve/{report_id}", summary="Approve a pending report")
async def approve_report(
    report_id: str,
    request:   Request,
    ctx:       AuthContext = Depends(require_permission(Permission.REPORT_APPROVE)),
):
    from backend.reports.versioning import report_versioning
    from backend.audit_center.service import audit_service
    ok = report_versioning.approve(report_id, ctx.tenant_id, ctx.user_id)
    if not ok:
        raise HTTPException(404, f"Report {report_id} not found or not pending approval")
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id, action="report.approved",
        resource_type="report", resource_id=report_id, ctx=request,
    )
    return {"ok": True, "report_id": report_id, "approved_by": ctx.user_id}


@router.post("/reports/reject/{report_id}", summary="Reject a pending report")
async def reject_report(
    report_id: str,
    request:   Request,
    ctx:       AuthContext = Depends(require_permission(Permission.REPORT_APPROVE)),
):
    from backend.reports.versioning import report_versioning
    from backend.audit_center.service import audit_service
    ok = report_versioning.reject(report_id, ctx.tenant_id, ctx.user_id)
    if not ok:
        raise HTTPException(404, f"Report {report_id} not found or not pending")
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id, action="report.rejected",
        resource_type="report", resource_id=report_id, ctx=request,
    )
    return {"ok": True, "report_id": report_id, "rejected_by": ctx.user_id}
