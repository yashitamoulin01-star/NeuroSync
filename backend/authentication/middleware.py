"""
Bearer token authentication middleware and dependency.

Usage (FastAPI):
    @router.get("/protected")
    async def endpoint(ctx: AuthContext = Depends(require_auth)):
        ...

    @router.get("/admin-only")
    async def admin_endpoint(ctx: AuthContext = Depends(require_permission(Permission.ORG_MANAGE))):
        ...
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user_id:   str
    tenant_id: str
    org_id:    Optional[str]
    email:     str
    roles:     list


async def _extract_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[str]:
    # Prefer Authorization header, fall back to X-API-Key
    if credentials:
        return credentials.credentials
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key
    return None


async def require_auth(
    request: Request,
    token: Optional[str] = Depends(_extract_token),
) -> AuthContext:
    if not token:
        raise HTTPException(401, "Authentication required")

    # Try API key first
    from backend.api_keys.service import api_key_service
    key_obj = api_key_service.validate(token)
    if key_obj:
        return AuthContext(
            user_id   = key_obj.created_by,
            tenant_id = key_obj.tenant_id,
            org_id    = key_obj.org_id,
            email     = "",
            roles     = ["api_client"],
        )

    # Try session token
    from backend.authentication.service import auth_service
    from backend.rbac.evaluator import permission_evaluator
    session = auth_service.validate_token(token)
    if not session:
        raise HTTPException(401, "Invalid or expired token")

    user = auth_service.get_by_id(session.user_id)
    if user is None or not user.is_active():
        raise HTTPException(401, "User account inactive")

    roles = permission_evaluator.get_user_roles(user.user_id, user.tenant_id)
    return AuthContext(
        user_id   = user.user_id,
        tenant_id = user.tenant_id,
        org_id    = user.org_id,
        email     = user.email,
        roles     = roles,
    )


def require_permission(permission: str) -> Callable:
    """Factory that returns a FastAPI dependency enforcing a specific permission."""
    async def _dependency(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        from backend.rbac.evaluator import permission_evaluator
        if not permission_evaluator.has_permission(ctx.user_id, ctx.tenant_id, permission):
            raise HTTPException(403, f"Permission denied: {permission}")
        return ctx
    return _dependency


def require_role(*roles: str) -> Callable:
    """Factory that returns a dependency enforcing that the user has at least one of the given roles."""
    async def _dependency(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        if not any(r in ctx.roles for r in roles):
            raise HTTPException(403, f"Required role: one of {list(roles)}")
        return ctx
    return _dependency
