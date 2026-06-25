"""
Permission constants — the single source of truth for every permission in the platform.

Permissions follow the pattern: "<resource>:<action>"
This makes permission checks self-documenting in code and easy to audit.

All permission checks MUST use these constants; no string literals elsewhere.
"""

from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    """String enum of all platform permissions."""

    # Sessions / Interviews
    SESSION_CREATE        = "session:create"
    SESSION_READ          = "session:read"
    SESSION_READ_ALL      = "session:read_all"     # see all org sessions
    SESSION_DELETE        = "session:delete"
    SESSION_EXPORT        = "session:export"

    # Reports
    REPORT_VIEW           = "report:view"
    REPORT_GENERATE       = "report:generate"
    REPORT_APPROVE        = "report:approve"
    REPORT_EXPORT         = "report:export"

    # Candidates
    CANDIDATE_VIEW        = "candidate:view"
    CANDIDATE_MANAGE      = "candidate:manage"
    CANDIDATE_PORTAL      = "candidate:portal"     # own data only

    # Recruiter workspace
    RECRUITER_WORKSPACE   = "recruiter:workspace"
    RECRUITER_ASSIGN      = "recruiter:assign"
    RECRUITER_NOTES       = "recruiter:notes"

    # Templates
    TEMPLATE_VIEW         = "template:view"
    TEMPLATE_MANAGE       = "template:manage"

    # Analytics
    ANALYTICS_VIEW        = "analytics:view"
    ANALYTICS_EXPORT      = "analytics:export"

    # Collaboration
    COLLAB_COMMENT        = "collab:comment"
    COLLAB_MANAGE_THREADS = "collab:manage_threads"

    # Evidence
    EVIDENCE_VIEW         = "evidence:view"
    EVIDENCE_EXPORT       = "evidence:export"

    # Organization management
    ORG_VIEW              = "org:view"
    ORG_MANAGE            = "org:manage"
    ORG_BILLING           = "org:billing"

    # User management
    USER_INVITE           = "user:invite"
    USER_MANAGE           = "user:manage"
    USER_ROLES            = "user:roles"

    # Audit
    AUDIT_READ            = "audit:read"
    AUDIT_EXPORT          = "audit:export"

    # Compliance
    COMPLIANCE_VIEW       = "compliance:view"
    COMPLIANCE_MANAGE     = "compliance:manage"
    DATA_REQUEST_MANAGE   = "data_request:manage"

    # API Keys
    API_KEY_VIEW          = "api_key:view"
    API_KEY_MANAGE        = "api_key:manage"

    # Feature flags
    FLAG_VIEW             = "flag:view"
    FLAG_MANAGE           = "flag:manage"

    # Connectors (external meeting providers)
    CONNECTOR_VIEW        = "connector:view"
    CONNECTOR_MANAGE      = "connector:manage"

    # Platform admin
    PLATFORM_ADMIN        = "platform:admin"
    TENANT_MANAGE         = "tenant:manage"
    SYSTEM_CONFIG         = "system:config"

    # Exports
    EXPORT_CREATE         = "export:create"
    EXPORT_DOWNLOAD       = "export:download"


# Convenience sets for readability
_SESSION_PERMS   = {Permission.SESSION_CREATE, Permission.SESSION_READ, Permission.SESSION_DELETE, Permission.SESSION_EXPORT}
_REPORT_PERMS    = {Permission.REPORT_VIEW, Permission.REPORT_GENERATE, Permission.REPORT_EXPORT}
_RECRUITER_PERMS = {Permission.RECRUITER_WORKSPACE, Permission.RECRUITER_ASSIGN, Permission.RECRUITER_NOTES}
_TEMPLATE_PERMS  = {Permission.TEMPLATE_VIEW, Permission.TEMPLATE_MANAGE}
_COLLAB_PERMS    = {Permission.COLLAB_COMMENT, Permission.COLLAB_MANAGE_THREADS}
_ORG_PERMS       = {Permission.ORG_VIEW, Permission.ORG_MANAGE, Permission.USER_INVITE, Permission.USER_MANAGE, Permission.USER_ROLES}
