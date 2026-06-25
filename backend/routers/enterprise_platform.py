"""
Enterprise Platform Router — tenants, organizations, templates, flags, API keys,
billing, admin console, analytics, exports, collaboration, recruiter, candidate.

GET  /api/v1/tenants               — list tenants (platform_admin)
POST /api/v1/tenants               — create tenant
GET  /api/v1/tenants/{id}/stats    — tenant statistics

GET  /api/v1/organizations         — list orgs in tenant
POST /api/v1/organizations         — create org
GET  /api/v1/organizations/{id}    — org detail
POST /api/v1/organizations/{id}/departments — create department
GET  /api/v1/organizations/{id}/departments — list departments
POST /api/v1/organizations/{id}/teams — create team

GET  /api/v1/templates             — list templates
POST /api/v1/templates             — create template
GET  /api/v1/templates/{id}/versions — template version history
POST /api/v1/templates/{id}/versions — publish new version

GET  /api/v1/flags                 — list feature flags
POST /api/v1/flags                 — create flag
POST /api/v1/flags/{name}/toggle   — enable/disable flag
POST /api/v1/flags/{name}/rollout  — set rollout percentage
GET  /api/v1/flags/{name}/evaluate — evaluate flag for current user

GET  /api/v1/api-keys              — list API keys
POST /api/v1/api-keys              — create API key (returns raw key once)
DELETE /api/v1/api-keys/{id}       — revoke API key

GET  /api/v1/billing/summary       — usage + quota summary
POST /api/v1/billing/plan          — update subscription plan

GET  /api/v1/admin/metrics         — platform metrics
GET  /api/v1/admin/tenants         — all tenants with stats
POST /api/v1/admin/tenants/{id}/suspend — suspend tenant
GET  /api/v1/admin/users/search    — search users across tenants
GET  /api/v1/admin/system/config   — system configuration
GET  /api/v1/admin/deployment      — deployment status

GET  /api/v1/analytics/dashboard   — org analytics dashboard
GET  /api/v1/analytics/sessions    — session volume trend
GET  /api/v1/analytics/scores      — score distribution
GET  /api/v1/analytics/recruiters  — recruiter activity

POST /api/v1/exports/session/json  — export session as JSON
POST /api/v1/exports/session/csv   — export sessions as CSV
POST /api/v1/exports/evidence      — export evidence package
POST /api/v1/exports/summary       — executive summary
GET  /api/v1/exports/jobs          — list export jobs

GET  /api/v1/recruiter/pipeline    — candidate pipeline
GET  /api/v1/recruiter/queue       — interview queue
POST /api/v1/recruiter/compare     — compare candidates
GET  /api/v1/recruiter/search      — search sessions

GET  /api/v1/candidate/sessions    — candidate's own sessions
GET  /api/v1/candidate/coaching/{session_id} — coaching report
GET  /api/v1/candidate/privacy     — privacy settings
POST /api/v1/candidate/data-export — request data export
POST /api/v1/candidate/erasure     — request data erasure

GET  /api/v1/collab/{session_id}/threads — list threads
POST /api/v1/collab/{session_id}/threads — create thread
GET  /api/v1/collab/threads/{id}/comments — list comments
POST /api/v1/collab/threads/{id}/comments — add comment
POST /api/v1/collab/threads/{id}/resolve  — resolve thread
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from backend.authentication.middleware import AuthContext, require_auth, require_permission
from backend.rbac.permissions import Permission

router = APIRouter(prefix="/api/v1", tags=["Enterprise Platform"])


# ── Tenants ───────────────────────────────────────────────────────────────────

@router.get("/tenants", summary="List all tenants (platform admin only)")
async def list_tenants(ctx: AuthContext = Depends(require_permission(Permission.TENANT_MANAGE))):
    from backend.administration.console import admin_console
    return {"tenants": admin_console.list_tenants()}


@router.post("/tenants", summary="Create a new tenant")
async def create_tenant(
    request: Request,
    ctx:     AuthContext = Depends(require_permission(Permission.TENANT_MANAGE)),
    payload: Dict = Body(...),
):
    from backend.administration.console import admin_console
    name = payload.get("name", "").strip()
    slug = payload.get("slug", "").strip()
    plan = payload.get("plan", "professional")
    if not name or not slug:
        raise HTTPException(400, "name and slug are required")
    return admin_console.create_tenant(name=name, slug=slug, plan=plan, admin_id=ctx.user_id)


@router.get("/tenants/{tenant_id}/stats", summary="Tenant usage statistics")
async def tenant_stats(
    tenant_id: str,
    ctx:       AuthContext = Depends(require_permission(Permission.TENANT_MANAGE)),
):
    from backend.tenants.service import tenant_service
    from backend.billing.service import billing_service
    tenant = tenant_service.get(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    stats = tenant_service.stats(tenant_id)
    usage = billing_service.usage_summary(tenant_id)
    return {"tenant": tenant.to_dict(), "stats": stats, "billing": usage}


# ── Organizations ─────────────────────────────────────────────────────────────

@router.get("/organizations", summary="List organizations in current tenant")
async def list_orgs(ctx: AuthContext = Depends(require_permission(Permission.ORG_VIEW))):
    from backend.organizations.service import org_service
    orgs = org_service.list_for_tenant(ctx.tenant_id)
    return {"organizations": [o.to_dict() for o in orgs]}


@router.post("/organizations", summary="Create an organization")
async def create_org(
    request: Request,
    ctx:     AuthContext = Depends(require_permission(Permission.ORG_MANAGE)),
    payload: Dict = Body(...),
):
    from backend.organizations.service import org_service
    from backend.audit_center.service import audit_service
    name = payload.get("name", "").strip()
    slug = payload.get("slug", "").strip()
    if not name or not slug:
        raise HTTPException(400, "name and slug are required")
    org = org_service.create(ctx.tenant_id, name, slug)
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id, action="org.created",
        resource_type="organization", resource_id=org.org_id, ctx=request,
    )
    return org.to_dict()


@router.get("/organizations/{org_id}", summary="Organization detail with summary")
async def get_org(
    org_id: str,
    ctx:    AuthContext = Depends(require_permission(Permission.ORG_VIEW)),
):
    from backend.organizations.service import org_service
    org = org_service.get(ctx.tenant_id, org_id)
    if org is None:
        raise HTTPException(404, f"Organization {org_id} not found")
    summary = org_service.summary(ctx.tenant_id, org_id)
    d = org.to_dict()
    d["summary"] = summary
    return d


@router.post("/organizations/{org_id}/departments", summary="Create a department")
async def create_department(
    org_id:  str,
    ctx:     AuthContext = Depends(require_permission(Permission.ORG_MANAGE)),
    payload: Dict = Body(...),
):
    from backend.organizations.service import org_service
    org_service.assert_exists(ctx.tenant_id, org_id)
    dept = org_service.create_department(ctx.tenant_id, org_id, payload.get("name", ""))
    return dept.to_dict()


@router.get("/organizations/{org_id}/departments", summary="List departments")
async def list_departments(
    org_id: str,
    ctx:    AuthContext = Depends(require_permission(Permission.ORG_VIEW)),
):
    from backend.organizations.service import org_service
    return {"departments": [d.to_dict() for d in org_service.list_departments(ctx.tenant_id, org_id)]}


@router.post("/organizations/{org_id}/teams", summary="Create a team")
async def create_team(
    org_id:  str,
    ctx:     AuthContext = Depends(require_permission(Permission.ORG_MANAGE)),
    payload: Dict = Body(...),
):
    from backend.organizations.service import org_service
    team = org_service.create_team(ctx.tenant_id, org_id, payload.get("name", ""), payload.get("dept_id"))
    return team.to_dict()


# ── Interview Templates ───────────────────────────────────────────────────────

@router.get("/templates", summary="List interview templates for the organization")
async def list_templates(ctx: AuthContext = Depends(require_permission(Permission.TEMPLATE_VIEW))):
    from backend.organizations.templates import template_service
    if not ctx.org_id:
        raise HTTPException(400, "Organization context required")
    templates = template_service.list_for_org(ctx.tenant_id, ctx.org_id)
    return {"templates": [t.to_dict() for t in templates]}


@router.post("/templates", summary="Create an interview template")
async def create_template(
    ctx:     AuthContext = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
    payload: Dict = Body(...),
):
    from backend.organizations.templates import template_service, TemplateConfig
    if not ctx.org_id:
        raise HTTPException(400, "Organization context required")
    name          = payload.get("name", "").strip()
    description   = payload.get("description", "")
    interview_type = payload.get("interview_type", "behavioral")
    config_data   = payload.get("config", {})
    if not name:
        raise HTTPException(400, "name is required")
    cfg = TemplateConfig.from_dict(config_data) if config_data else None
    tpl = template_service.create(
        tenant_id=ctx.tenant_id, org_id=ctx.org_id, name=name,
        created_by=ctx.user_id, config=cfg, description=description,
        interview_type=interview_type,
    )
    return tpl.to_dict()


@router.get("/templates/{template_id}/versions", summary="Template version history")
async def list_template_versions(
    template_id: str,
    ctx:         AuthContext = Depends(require_permission(Permission.TEMPLATE_VIEW)),
):
    from backend.organizations.templates import template_service
    return {"template_id": template_id, "versions": template_service.list_versions(template_id)}


@router.post("/templates/{template_id}/versions", summary="Publish a new template version")
async def publish_template_version(
    template_id: str,
    ctx:         AuthContext = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
    payload:     Dict = Body(...),
):
    from backend.organizations.templates import template_service, TemplateConfig
    config = TemplateConfig.from_dict(payload.get("config", {}))
    version = template_service.publish_new_version(
        ctx.tenant_id, template_id, config, updated_by=ctx.user_id
    )
    return version.to_dict()


# ── Feature Flags ─────────────────────────────────────────────────────────────

@router.get("/flags", summary="List all feature flags")
async def list_flags(ctx: AuthContext = Depends(require_permission(Permission.FLAG_VIEW))):
    from backend.feature_flags.service import feature_flag_service
    return {"flags": [f.to_dict() for f in feature_flag_service.list_all()]}


@router.post("/flags", summary="Create a feature flag")
async def create_flag(
    ctx:     AuthContext = Depends(require_permission(Permission.FLAG_MANAGE)),
    payload: Dict = Body(...),
):
    from backend.feature_flags.service import feature_flag_service
    name = payload.get("name", "").strip()
    if not name:
        raise HTTPException(400, "name is required")
    flag = feature_flag_service.create(
        name        = name,
        description = payload.get("description", ""),
        created_by  = ctx.user_id,
        enabled     = bool(payload.get("enabled", False)),
        rollout_pct = int(payload.get("rollout_pct", 0)),
    )
    return flag.to_dict()


@router.post("/flags/{name}/toggle", summary="Toggle a feature flag on or off")
async def toggle_flag(
    name:    str,
    ctx:     AuthContext = Depends(require_permission(Permission.FLAG_MANAGE)),
    payload: Dict = Body(...),
):
    from backend.administration.console import admin_console
    enabled = bool(payload.get("enabled", False))
    ok = admin_console.toggle_flag(name, enabled, ctx.user_id)
    if not ok:
        raise HTTPException(404, f"Flag '{name}' not found")
    return {"ok": True, "flag": name, "enabled": enabled}


@router.post("/flags/{name}/rollout", summary="Set rollout percentage")
async def set_rollout(
    name:    str,
    ctx:     AuthContext = Depends(require_permission(Permission.FLAG_MANAGE)),
    payload: Dict = Body(...),
):
    from backend.feature_flags.service import feature_flag_service
    pct = int(payload.get("rollout_pct", 0))
    ok = feature_flag_service.set_rollout(name, pct, ctx.user_id)
    if not ok:
        raise HTTPException(404, f"Flag '{name}' not found")
    return {"ok": True, "flag": name, "rollout_pct": pct}


@router.get("/flags/{name}/evaluate", summary="Evaluate a flag for the current user")
async def evaluate_flag(
    name: str,
    ctx:  AuthContext = Depends(require_auth),
):
    from backend.feature_flags.service import feature_flag_service
    result = feature_flag_service.is_enabled(
        name, user_id=ctx.user_id, tenant_id=ctx.tenant_id, org_id=ctx.org_id
    )
    return {"flag": name, "enabled": result, "user_id": ctx.user_id}


# ── API Keys ──────────────────────────────────────────────────────────────────

@router.get("/api-keys", summary="List API keys for this tenant/org")
async def list_api_keys(ctx: AuthContext = Depends(require_permission(Permission.API_KEY_VIEW))):
    from backend.api_keys.service import api_key_service
    keys = api_key_service.list_for_tenant(ctx.tenant_id, ctx.org_id)
    return {"api_keys": [k.to_dict() for k in keys]}


@router.post("/api-keys", summary="Create a new API key (raw key returned once only)")
async def create_api_key(
    request: Request,
    ctx:     AuthContext = Depends(require_permission(Permission.API_KEY_MANAGE)),
    payload: Dict = Body(...),
):
    from backend.api_keys.service import api_key_service
    from backend.audit_center.service import audit_service
    key_obj, raw_key = api_key_service.create(
        tenant_id  = ctx.tenant_id,
        created_by = ctx.user_id,
        name       = payload.get("name", ""),
        scopes     = payload.get("scopes"),
        org_id     = ctx.org_id,
        rate_limit = int(payload.get("rate_limit", 1000)),
    )
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id, action="api_key.created",
        resource_type="api_key", resource_id=key_obj.key_id, ctx=request,
    )
    d = key_obj.to_dict()
    d["raw_key"] = raw_key    # only returned at creation
    d["warning"] = "Store this key securely — it cannot be retrieved again."
    return d


@router.delete("/api-keys/{key_id}", summary="Revoke an API key")
async def revoke_api_key(
    key_id:  str,
    request: Request,
    ctx:     AuthContext = Depends(require_permission(Permission.API_KEY_MANAGE)),
):
    from backend.api_keys.service import api_key_service
    from backend.audit_center.service import audit_service
    ok = api_key_service.revoke(key_id, ctx.tenant_id, ctx.user_id)
    if not ok:
        raise HTTPException(404, f"API key {key_id} not found")
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id, action="api_key.revoked",
        resource_type="api_key", resource_id=key_id, ctx=request,
    )
    return {"ok": True, "key_id": key_id, "status": "revoked"}


# ── Billing ───────────────────────────────────────────────────────────────────

@router.get("/billing/summary", summary="Current usage and quota summary")
async def billing_summary(ctx: AuthContext = Depends(require_permission(Permission.ORG_BILLING))):
    from backend.billing.service import billing_service
    return billing_service.usage_summary(ctx.tenant_id)


@router.post("/billing/plan", summary="Update subscription plan (admin only)")
async def update_plan(
    ctx:     AuthContext = Depends(require_permission(Permission.TENANT_MANAGE)),
    payload: Dict = Body(...),
):
    from backend.billing.service import billing_service
    tenant_id = payload.get("tenant_id", ctx.tenant_id)
    plan_name = payload.get("plan", "professional")
    plan = billing_service.upsert_plan(tenant_id, plan_name)
    return {"ok": True, "plan": plan.to_dict()}


# ── Admin Console ─────────────────────────────────────────────────────────────

@router.get("/admin/metrics", summary="Platform-wide metrics")
async def admin_metrics(ctx: AuthContext = Depends(require_permission(Permission.PLATFORM_ADMIN))):
    from backend.administration.console import admin_console
    return admin_console.platform_metrics()


@router.post("/admin/tenants/{tenant_id}/suspend", summary="Suspend a tenant")
async def admin_suspend_tenant(
    tenant_id: str,
    request:   Request,
    ctx:       AuthContext = Depends(require_permission(Permission.PLATFORM_ADMIN)),
    payload:   Dict = Body(default={}),
):
    from backend.administration.console import admin_console
    reason = payload.get("reason", "")
    ok = admin_console.suspend_tenant(tenant_id, ctx.user_id, reason)
    if not ok:
        raise HTTPException(404, f"Tenant {tenant_id} not found")
    return {"ok": True, "tenant_id": tenant_id, "status": "suspended"}


@router.get("/admin/users/search", summary="Search users across tenants")
async def admin_search_users(
    ctx:       AuthContext = Depends(require_permission(Permission.PLATFORM_ADMIN)),
    q:         str = Query(..., min_length=2),
    tenant_id: Optional[str] = None,
):
    from backend.administration.console import admin_console
    return {"users": admin_console.search_users(q, tenant_id)}


@router.get("/admin/system/config", summary="Platform system configuration")
async def admin_system_config(ctx: AuthContext = Depends(require_permission(Permission.SYSTEM_CONFIG))):
    from backend.administration.console import admin_console
    return admin_console.get_system_config()


@router.get("/admin/deployment", summary="Deployment status and alert summary")
async def admin_deployment(ctx: AuthContext = Depends(require_permission(Permission.PLATFORM_ADMIN))):
    from backend.administration.console import admin_console
    return admin_console.deployment_status()


# ── Enterprise Analytics ──────────────────────────────────────────────────────

@router.get("/analytics/dashboard", summary="Organization analytics dashboard")
async def analytics_dashboard(
    ctx: AuthContext = Depends(require_permission(Permission.ANALYTICS_VIEW)),
):
    from backend.analytics.service import analytics_service
    if not ctx.org_id:
        raise HTTPException(400, "Organization context required")
    return analytics_service.org_dashboard(ctx.tenant_id, ctx.org_id)


@router.get("/analytics/sessions", summary="Session volume over time")
async def analytics_sessions(
    ctx:         AuthContext = Depends(require_permission(Permission.ANALYTICS_VIEW)),
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    since:       Optional[float] = None,
):
    from backend.analytics.service import analytics_service
    return {
        "granularity": granularity,
        "data": analytics_service.session_volume(ctx.tenant_id, ctx.org_id, since=since, granularity=granularity),
    }


@router.get("/analytics/scores", summary="Score distribution by dimension")
async def analytics_scores(
    ctx:       AuthContext = Depends(require_permission(Permission.ANALYTICS_VIEW)),
    dimension: str = Query("avg_confidence"),
):
    from backend.analytics.service import analytics_service
    try:
        data = analytics_service.score_distribution(ctx.tenant_id, ctx.org_id, dimension)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"dimension": dimension, "distribution": data}


@router.get("/analytics/recruiters", summary="Recruiter activity in the last N days")
async def analytics_recruiters(
    ctx:  AuthContext = Depends(require_permission(Permission.ANALYTICS_VIEW)),
    days: int = Query(30, le=365),
):
    from backend.analytics.service import analytics_service
    return {
        "days": days,
        "activity": analytics_service.recruiter_activity(ctx.tenant_id, days),
    }


# ── Exports ───────────────────────────────────────────────────────────────────

@router.post("/exports/session/json", summary="Export a session as JSON")
async def export_json(
    ctx:     AuthContext = Depends(require_permission(Permission.EXPORT_CREATE)),
    payload: Dict = Body(...),
):
    from backend.exports.service import export_service
    session_id = payload.get("session_id", "")
    if not session_id:
        raise HTTPException(400, "session_id required")
    try:
        return export_service.export_session_json(session_id, ctx.tenant_id, ctx.user_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.post("/exports/session/csv", summary="Export multiple sessions as CSV")
async def export_csv(
    ctx:     AuthContext = Depends(require_permission(Permission.EXPORT_CREATE)),
    payload: Dict = Body(...),
):
    from fastapi.responses import PlainTextResponse
    from backend.exports.service import export_service
    session_ids = payload.get("session_ids", [])
    if not session_ids:
        raise HTTPException(400, "session_ids required")
    csv_content = export_service.export_session_csv(session_ids, ctx.tenant_id, ctx.user_id)
    return PlainTextResponse(content=csv_content, media_type="text/csv")


@router.post("/exports/evidence", summary="Export full evidence package")
async def export_evidence(
    ctx:     AuthContext = Depends(require_permission(Permission.EVIDENCE_EXPORT)),
    payload: Dict = Body(...),
):
    from backend.exports.service import export_service
    session_id = payload.get("session_id", "")
    if not session_id:
        raise HTTPException(400, "session_id required")
    try:
        return export_service.export_evidence_package(session_id, ctx.tenant_id, ctx.user_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.post("/exports/summary", summary="Export executive summary")
async def export_summary(
    ctx:     AuthContext = Depends(require_permission(Permission.REPORT_EXPORT)),
    payload: Dict = Body(...),
):
    from backend.exports.service import export_service
    session_id = payload.get("session_id", "")
    if not session_id:
        raise HTTPException(400, "session_id required")
    try:
        return export_service.executive_summary(session_id, ctx.tenant_id, ctx.user_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.get("/exports/jobs", summary="List export jobs")
async def list_export_jobs(
    ctx:   AuthContext = Depends(require_permission(Permission.EXPORT_DOWNLOAD)),
    limit: int = Query(25, le=100),
):
    from backend.exports.service import export_service
    return {"jobs": export_service.list_jobs(ctx.tenant_id, limit)}


# ── Recruiter Workspace ───────────────────────────────────────────────────────

@router.get("/recruiter/pipeline", summary="Candidate pipeline view")
async def recruiter_pipeline(
    ctx:   AuthContext = Depends(require_permission(Permission.RECRUITER_WORKSPACE)),
    stage: Optional[str] = None,
    limit: int = Query(50, le=200),
):
    from backend.recruiter_workspace.service import recruiter_service
    return recruiter_service.get_pipeline(ctx.tenant_id, ctx.org_id, ctx.user_id, stage, limit)


@router.get("/recruiter/queue", summary="Interview queue — sessions needing review")
async def recruiter_queue(
    ctx:   AuthContext = Depends(require_permission(Permission.RECRUITER_WORKSPACE)),
    limit: int = Query(25, le=100),
):
    from backend.recruiter_workspace.service import recruiter_service
    return {"queue": recruiter_service.get_interview_queue(ctx.tenant_id, ctx.user_id, limit)}


@router.post("/recruiter/compare", summary="Side-by-side candidate comparison")
async def recruiter_compare(
    ctx:     AuthContext = Depends(require_permission(Permission.RECRUITER_WORKSPACE)),
    payload: Dict = Body(...),
):
    from backend.recruiter_workspace.service import recruiter_service
    session_ids = payload.get("session_ids", [])
    if len(session_ids) < 2:
        raise HTTPException(400, "At least 2 session_ids required for comparison")
    return recruiter_service.compare_candidates(session_ids, ctx.tenant_id)


@router.get("/recruiter/search", summary="Search sessions by name")
async def recruiter_search(
    ctx:   AuthContext = Depends(require_permission(Permission.SESSION_READ_ALL)),
    q:     str = Query(..., min_length=1),
    limit: int = Query(25, le=100),
):
    from backend.recruiter_workspace.service import recruiter_service
    return {"results": recruiter_service.search_sessions(ctx.tenant_id, q, limit)}


# ── Candidate Portal ──────────────────────────────────────────────────────────

@router.get("/candidate/sessions", summary="Candidate's own interview history")
async def candidate_sessions(ctx: AuthContext = Depends(require_permission(Permission.CANDIDATE_PORTAL))):
    from backend.candidate_portal.service import candidate_portal_service
    sessions = candidate_portal_service.get_sessions(ctx.user_id, ctx.tenant_id)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/candidate/coaching/{session_id}", summary="Coaching report for a session")
async def candidate_coaching(
    session_id: str,
    ctx:        AuthContext = Depends(require_permission(Permission.CANDIDATE_PORTAL)),
):
    from backend.candidate_portal.service import candidate_portal_service
    try:
        return candidate_portal_service.get_coaching_report(session_id, ctx.user_id)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))


@router.get("/candidate/privacy", summary="Candidate privacy settings and consent status")
async def candidate_privacy(ctx: AuthContext = Depends(require_permission(Permission.CANDIDATE_PORTAL))):
    from backend.candidate_portal.service import candidate_portal_service
    return candidate_portal_service.get_privacy_settings(ctx.user_id, ctx.tenant_id)


@router.post("/candidate/data-export", summary="Request data portability export")
async def candidate_data_export(ctx: AuthContext = Depends(require_permission(Permission.CANDIDATE_PORTAL))):
    from backend.candidate_portal.service import candidate_portal_service
    request_id = candidate_portal_service.request_data_export(ctx.user_id, ctx.tenant_id)
    return {"ok": True, "request_id": request_id, "type": "export", "status": "pending"}


@router.post("/candidate/erasure", summary="Request data erasure")
async def candidate_erasure(ctx: AuthContext = Depends(require_permission(Permission.CANDIDATE_PORTAL))):
    from backend.candidate_portal.service import candidate_portal_service
    request_id = candidate_portal_service.request_erasure(ctx.user_id, ctx.tenant_id)
    return {"ok": True, "request_id": request_id, "type": "erasure", "status": "pending"}


# ── Collaboration ─────────────────────────────────────────────────────────────

@router.get("/collab/{session_id}/threads", summary="List collaboration threads for a session")
async def list_threads(
    session_id: str,
    ctx:        AuthContext = Depends(require_permission(Permission.COLLAB_COMMENT)),
):
    from backend.collaboration.service import collab_service
    threads = collab_service.list_threads(ctx.tenant_id, session_id)
    return {"session_id": session_id, "threads": [t.to_dict() for t in threads]}


@router.post("/collab/{session_id}/threads", summary="Create a collaboration thread")
async def create_thread(
    session_id: str,
    ctx:        AuthContext = Depends(require_permission(Permission.COLLAB_COMMENT)),
    payload:    Dict = Body(...),
):
    from backend.collaboration.service import collab_service
    thread = collab_service.create_thread(
        session_id = session_id,
        tenant_id  = ctx.tenant_id,
        created_by = ctx.user_id,
        title      = payload.get("title", ""),
        org_id     = ctx.org_id,
    )
    return thread.to_dict()


@router.get("/collab/threads/{thread_id}/comments", summary="List comments in a thread")
async def list_comments(
    thread_id: str,
    ctx:       AuthContext = Depends(require_permission(Permission.COLLAB_COMMENT)),
):
    from backend.collaboration.service import collab_service
    comments = collab_service.list_comments(ctx.tenant_id, thread_id)
    return {"thread_id": thread_id, "comments": [c.to_dict() for c in comments]}


@router.post("/collab/threads/{thread_id}/comments", summary="Add a comment to a thread")
async def add_comment(
    thread_id: str,
    ctx:       AuthContext = Depends(require_permission(Permission.COLLAB_COMMENT)),
    payload:   Dict = Body(...),
):
    from backend.collaboration.service import collab_service
    body = payload.get("body", "").strip()
    if not body:
        raise HTTPException(400, "body is required")
    comment = collab_service.add_comment(
        thread_id  = thread_id,
        session_id = payload.get("session_id", ""),
        tenant_id  = ctx.tenant_id,
        author_id  = ctx.user_id,
        body       = body,
        mentions   = payload.get("mentions", []),
    )
    return comment.to_dict()


@router.post("/collab/threads/{thread_id}/resolve", summary="Resolve a thread")
async def resolve_thread(
    thread_id: str,
    ctx:       AuthContext = Depends(require_permission(Permission.COLLAB_MANAGE_THREADS)),
):
    from backend.collaboration.service import collab_service
    ok = collab_service.resolve_thread(ctx.tenant_id, thread_id, ctx.user_id)
    if not ok:
        raise HTTPException(404, f"Thread {thread_id} not found")
    return {"ok": True, "thread_id": thread_id, "status": "resolved"}
