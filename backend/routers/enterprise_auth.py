"""
Enterprise Authentication Router — /api/v1/auth/* and /api/v1/users/*

POST /api/v1/auth/register        — create user account
POST /api/v1/auth/login           — email + password → token pair
POST /api/v1/auth/logout          — revoke current session token
GET  /api/v1/auth/me              — current user profile
POST /api/v1/auth/password        — change own password
GET  /api/v1/users                — list org users (org_admin+)
POST /api/v1/users/{id}/roles     — assign role (org_admin+)
DELETE /api/v1/users/{id}/roles/{role} — revoke role
POST /api/v1/users/{id}/suspend   — suspend user
GET  /api/v1/rbac/matrix          — permission matrix for current user
GET  /api/v1/rbac/roles           — list all available roles
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request

from backend.authentication.middleware import AuthContext, require_auth, require_permission
from backend.rbac.permissions import Permission

router = APIRouter(prefix="/api/v1", tags=["Enterprise Auth"])


# ── Registration + Login ──────────────────────────────────────────────────────

@router.post("/auth/register", summary="Register a new user account")
async def register(
    request: Request,
    payload: Dict = Body(...),
):
    from backend.authentication.service import auth_service
    from backend.audit_center.service import audit_service

    email        = payload.get("email", "").strip()
    password     = payload.get("password", "")
    display_name = payload.get("display_name", "")
    tenant_id    = payload.get("tenant_id", "")
    org_id       = payload.get("org_id")

    if not email or not password or not tenant_id:
        raise HTTPException(400, "email, password, and tenant_id are required")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    try:
        user = auth_service.register(
            tenant_id=tenant_id, email=email, password=password,
            display_name=display_name, org_id=org_id,
        )
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise HTTPException(409, f"Email already registered in this tenant")
        raise HTTPException(400, str(exc))

    audit_service.log(
        tenant_id=tenant_id, actor_id=user.user_id, action="auth.login",
        resource_type="user", resource_id=user.user_id, ctx=request,
    )
    return {"user_id": user.user_id, "email": user.email, "status": "active"}


@router.post("/auth/login", summary="Authenticate with email and password")
async def login(
    request: Request,
    payload: Dict = Body(...),
):
    from backend.authentication.service import auth_service
    from backend.audit_center.service import audit_service

    tenant_id = payload.get("tenant_id", "")
    email     = payload.get("email", "")
    password  = payload.get("password", "")

    if not all([tenant_id, email, password]):
        raise HTTPException(400, "tenant_id, email, and password are required")

    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    tokens = auth_service.login(tenant_id, email, password, ip, ua)

    if tokens is None:
        audit_service.log(
            tenant_id=tenant_id, actor_id="anonymous", action="auth.login_failed",
            resource_type="auth", resource_id=email, ctx=request, severity="warning",
        )
        raise HTTPException(401, "Invalid credentials")

    user = auth_service.get_by_email(tenant_id, email)
    audit_service.log(
        tenant_id=tenant_id, actor_id=user.user_id, action="auth.login",
        resource_type="auth", resource_id=user.user_id, ctx=request,
    )
    return tokens.to_dict()


@router.post("/auth/logout", summary="Revoke current session token")
async def logout(
    request: Request,
    ctx: AuthContext = Depends(require_auth),
    authorization: Optional[str] = Header(None),
):
    from backend.authentication.service import auth_service
    from backend.audit_center.service import audit_service

    token = (authorization or "").replace("Bearer ", "").strip()
    auth_service.revoke_token(token)
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id, action="auth.logout",
        resource_type="auth", resource_id=ctx.user_id, ctx=request,
    )
    return {"ok": True}


@router.get("/auth/me", summary="Current user profile and roles")
async def me(ctx: AuthContext = Depends(require_auth)):
    from backend.authentication.service import auth_service
    from backend.rbac.evaluator import permission_evaluator
    user = auth_service.get_by_id(ctx.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    roles = permission_evaluator.get_user_roles(ctx.user_id, ctx.tenant_id)
    d = user.to_dict()
    d["roles"] = roles
    return d


@router.post("/auth/password", summary="Change own password")
async def change_password(
    request: Request,
    ctx:     AuthContext = Depends(require_auth),
    payload: Dict = Body(...),
):
    from backend.authentication.service import auth_service
    new_password = payload.get("new_password", "")
    if len(new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")
    auth_service.update_password(ctx.user_id, new_password)
    return {"ok": True, "message": "Password updated"}


# ── User Management ───────────────────────────────────────────────────────────

@router.get("/users", summary="List users in the current organization")
async def list_users(ctx: AuthContext = Depends(require_permission(Permission.USER_MANAGE))):
    from backend.authentication.service import auth_service
    if ctx.org_id is None:
        raise HTTPException(400, "No organization context")
    users = auth_service.list_for_org(ctx.tenant_id, ctx.org_id)
    return {"users": [u.to_dict() for u in users], "count": len(users)}


@router.post("/users/{user_id}/suspend", summary="Suspend a user account")
async def suspend_user(
    user_id: str,
    request: Request,
    ctx:     AuthContext = Depends(require_permission(Permission.USER_MANAGE)),
):
    from backend.authentication.service import auth_service
    from backend.audit_center.service import audit_service
    ok = auth_service.update_status(user_id, "suspended", actor_id=ctx.user_id)
    if not ok:
        raise HTTPException(404, f"User {user_id} not found")
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id, action="user.suspended",
        resource_type="user", resource_id=user_id, ctx=request,
        actor_role=",".join(ctx.roles),
    )
    return {"ok": True, "user_id": user_id, "status": "suspended"}


# ── RBAC ──────────────────────────────────────────────────────────────────────

@router.get("/rbac/matrix", summary="Permission matrix for the current user")
async def permission_matrix(ctx: AuthContext = Depends(require_auth)):
    from backend.rbac.evaluator import permission_evaluator
    return permission_evaluator.get_permission_matrix(ctx.user_id, ctx.tenant_id)


@router.get("/rbac/roles", summary="All available roles and their permission sets")
async def list_roles():
    from backend.rbac.roles import ROLE_PERMISSIONS
    return {
        "roles": [
            {"role": role, "permissions": sorted(perms)}
            for role, perms in ROLE_PERMISSIONS.items()
        ]
    }


@router.post("/users/{user_id}/roles", summary="Assign a role to a user")
async def assign_role(
    user_id: str,
    request: Request,
    ctx:     AuthContext = Depends(require_permission(Permission.USER_ROLES)),
    payload: Dict = Body(...),
):
    from backend.rbac.evaluator import permission_evaluator
    from backend.audit_center.service import audit_service
    role = payload.get("role", "")
    if not role:
        raise HTTPException(400, "role is required")
    try:
        assignment_id = permission_evaluator.assign_role(
            user_id   = user_id,
            tenant_id = ctx.tenant_id,
            role      = role,
            granted_by = ctx.user_id,
            org_id    = ctx.org_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id, action="role.assigned",
        resource_type="user", resource_id=user_id, ctx=request,
        changes={"role": role},
    )
    return {"ok": True, "assignment_id": assignment_id, "user_id": user_id, "role": role}


@router.delete("/users/{user_id}/roles/{role}", summary="Revoke a role from a user")
async def revoke_role(
    user_id: str,
    role:    str,
    request: Request,
    ctx:     AuthContext = Depends(require_permission(Permission.USER_ROLES)),
):
    from backend.rbac.evaluator import permission_evaluator
    from backend.audit_center.service import audit_service
    ok = permission_evaluator.revoke_role(user_id, ctx.tenant_id, role)
    if not ok:
        raise HTTPException(404, f"Role {role} not assigned to user {user_id}")
    audit_service.log(
        tenant_id=ctx.tenant_id, actor_id=ctx.user_id, action="role.revoked",
        resource_type="user", resource_id=user_id, ctx=request,
        changes={"role": role},
    )
    return {"ok": True, "user_id": user_id, "role_revoked": role}
