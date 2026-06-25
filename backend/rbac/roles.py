"""
Role definitions — maps each role to its permission set.

Roles are additive: a user may hold multiple roles simultaneously.
Permission evaluation unions all role permissions then applies overrides.

Hierarchy (lowest → highest privilege):
  candidate → reviewer → interviewer → recruiter → hiring_manager
      → org_admin → platform_admin
"""

from __future__ import annotations

from typing import Dict, FrozenSet

from backend.rbac.permissions import Permission

P = Permission

# ── Role permission sets ──────────────────────────────────────────────────────

_CANDIDATE: FrozenSet[str] = frozenset({
    P.SESSION_READ,
    P.CANDIDATE_PORTAL,
    P.REPORT_VIEW,
    P.EVIDENCE_VIEW,
})

_AUDITOR: FrozenSet[str] = frozenset({
    P.SESSION_READ,
    P.SESSION_READ_ALL,
    P.REPORT_VIEW,
    P.EVIDENCE_VIEW,
    P.AUDIT_READ,
    P.AUDIT_EXPORT,
    P.ANALYTICS_VIEW,
    P.ORG_VIEW,
})

_REVIEWER: FrozenSet[str] = frozenset({
    P.SESSION_READ,
    P.SESSION_READ_ALL,
    P.REPORT_VIEW,
    P.EVIDENCE_VIEW,
    P.COLLAB_COMMENT,
    P.CANDIDATE_VIEW,
    P.ANALYTICS_VIEW,
})

_INTERVIEWER: FrozenSet[str] = frozenset({
    P.SESSION_CREATE,
    P.SESSION_READ,
    P.TEMPLATE_VIEW,
    P.EVIDENCE_VIEW,
    P.COLLAB_COMMENT,
    P.CANDIDATE_VIEW,
    P.RECRUITER_NOTES,
})

_RECRUITER: FrozenSet[str] = frozenset({
    P.SESSION_CREATE,
    P.SESSION_READ,
    P.SESSION_READ_ALL,
    P.SESSION_EXPORT,
    P.REPORT_VIEW,
    P.REPORT_GENERATE,
    P.REPORT_EXPORT,
    P.CANDIDATE_VIEW,
    P.CANDIDATE_MANAGE,
    P.RECRUITER_WORKSPACE,
    P.RECRUITER_ASSIGN,
    P.RECRUITER_NOTES,
    P.TEMPLATE_VIEW,
    P.EVIDENCE_VIEW,
    P.EVIDENCE_EXPORT,
    P.COLLAB_COMMENT,
    P.COLLAB_MANAGE_THREADS,
    P.ANALYTICS_VIEW,
    P.EXPORT_CREATE,
    P.EXPORT_DOWNLOAD,
    P.CONNECTOR_VIEW,
})

_HIRING_MANAGER: FrozenSet[str] = frozenset({
    *_RECRUITER,
    P.REPORT_APPROVE,
    P.TEMPLATE_MANAGE,
    P.ANALYTICS_EXPORT,
    P.AUDIT_READ,
    P.ORG_VIEW,
    P.USER_INVITE,
})

_ORG_ADMIN: FrozenSet[str] = frozenset({
    *_HIRING_MANAGER,
    P.ORG_MANAGE,
    P.USER_MANAGE,
    P.USER_ROLES,
    P.AUDIT_READ,
    P.AUDIT_EXPORT,
    P.COMPLIANCE_VIEW,
    P.COMPLIANCE_MANAGE,
    P.DATA_REQUEST_MANAGE,
    P.API_KEY_VIEW,
    P.API_KEY_MANAGE,
    P.FLAG_VIEW,
    P.SESSION_DELETE,
    P.ORG_BILLING,
    P.CONNECTOR_VIEW,
    P.CONNECTOR_MANAGE,
})

_PLATFORM_ADMIN: FrozenSet[str] = frozenset({
    *_ORG_ADMIN,
    P.PLATFORM_ADMIN,
    P.TENANT_MANAGE,
    P.SYSTEM_CONFIG,
    P.FLAG_MANAGE,
})

# ── Registry ──────────────────────────────────────────────────────────────────

ROLE_PERMISSIONS: Dict[str, FrozenSet[str]] = {
    "candidate":       _CANDIDATE,
    "auditor":         _AUDITOR,
    "reviewer":        _REVIEWER,
    "interviewer":     _INTERVIEWER,
    "recruiter":       _RECRUITER,
    "hiring_manager":  _HIRING_MANAGER,
    "org_admin":       _ORG_ADMIN,
    "platform_admin":  _PLATFORM_ADMIN,
}

ALL_ROLES = list(ROLE_PERMISSIONS.keys())


def permissions_for_role(role: str) -> FrozenSet[str]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def roles_with_permission(permission: str) -> list:
    return [role for role, perms in ROLE_PERMISSIONS.items() if permission in perms]
