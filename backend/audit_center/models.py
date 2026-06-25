"""Audit event domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import unique
from typing import Any, Dict, List, Optional


@unique
class AuditAction(str):
    # Auth
    LOGIN              = "auth.login"
    LOGOUT             = "auth.logout"
    LOGIN_FAILED       = "auth.login_failed"
    PASSWORD_CHANGED   = "auth.password_changed"
    MFA_ENABLED        = "auth.mfa_enabled"
    TOKEN_REVOKED      = "auth.token_revoked"

    # Sessions
    SESSION_CREATED    = "session.created"
    SESSION_ACCESSED   = "session.accessed"
    SESSION_DELETED    = "session.deleted"
    SESSION_EXPORTED   = "session.exported"

    # Reports
    REPORT_GENERATED   = "report.generated"
    REPORT_VIEWED      = "report.viewed"
    REPORT_APPROVED    = "report.approved"
    REPORT_REJECTED    = "report.rejected"
    REPORT_EXPORTED    = "report.exported"

    # Evidence
    EVIDENCE_ACCESSED  = "evidence.accessed"

    # Users
    USER_INVITED       = "user.invited"
    USER_CREATED       = "user.created"
    USER_UPDATED       = "user.updated"
    USER_SUSPENDED     = "user.suspended"
    USER_DELETED       = "user.deleted"
    USER_ROLE_CHANGED  = "user.role_changed"

    # Organization
    ORG_CREATED        = "org.created"
    ORG_UPDATED        = "org.updated"
    ORG_CONFIG_CHANGED = "org.config_changed"

    # Permissions
    PERMISSION_GRANTED  = "permission.granted"
    PERMISSION_REVOKED  = "permission.revoked"
    ROLE_ASSIGNED       = "role.assigned"
    ROLE_REVOKED        = "role.revoked"

    # Compliance
    DATA_EXPORT_REQUESTED = "compliance.data_export_requested"
    DATA_ERASURE_REQUESTED = "compliance.data_erasure_requested"
    CONSENT_GRANTED     = "consent.granted"
    CONSENT_REVOKED     = "consent.revoked"

    # AI Platform
    MODEL_DEPLOYED      = "model.deployed"
    MODEL_ROLLED_BACK   = "model.rolled_back"

    # Config
    CONFIG_CHANGED      = "config.changed"
    FLAG_TOGGLED        = "flag.toggled"
    API_KEY_CREATED     = "api_key.created"
    API_KEY_REVOKED     = "api_key.revoked"


@dataclass
class AuditEvent:
    event_id:      str
    tenant_id:     str
    org_id:        Optional[str]
    actor_id:      str
    actor_role:    str
    action:        str
    resource_type: str
    resource_id:   str
    changes:       Optional[Dict[str, Any]]
    ip_address:    str
    user_agent:    str
    session_token: Optional[str]
    severity:      str    # info | warning | critical
    timestamp:     float
    metadata:      Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id":      self.event_id,
            "tenant_id":     self.tenant_id,
            "org_id":        self.org_id,
            "actor_id":      self.actor_id,
            "actor_role":    self.actor_role,
            "action":        self.action,
            "resource_type": self.resource_type,
            "resource_id":   self.resource_id,
            "changes":       self.changes,
            "ip_address":    self.ip_address,
            "severity":      self.severity,
            "timestamp":     self.timestamp,
            "metadata":      self.metadata,
        }

    @classmethod
    def from_row(cls, row) -> "AuditEvent":
        import json
        return cls(
            event_id      = row["event_id"],
            tenant_id     = row["tenant_id"],
            org_id        = row["org_id"],
            actor_id      = row["actor_id"],
            actor_role    = row["actor_role"],
            action        = row["action"],
            resource_type = row["resource_type"],
            resource_id   = row["resource_id"],
            changes       = json.loads(row["changes_json"]) if row["changes_json"] else None,
            ip_address    = row["ip_address"],
            user_agent    = row["user_agent"],
            session_token = row["session_token"],
            severity      = row["severity"],
            timestamp     = row["timestamp"],
            metadata      = json.loads(row["metadata_json"] or "{}"),
        )
