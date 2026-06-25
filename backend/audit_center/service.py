"""
Audit service — append-only event log.

Every critical platform action is recorded here. The audit log is:
  - Append-only (no UPDATE or DELETE permitted on audit_events)
  - Tenant-scoped (every query includes tenant_id)
  - Immutable (events are never modified)
  - Queryable by actor, action, resource, time range

Usage:
    audit_service.log(
        tenant_id="ten_abc",
        actor_id="usr_xyz",
        action=AuditAction.SESSION_CREATED,
        resource_type="session",
        resource_id=session_id,
        ctx=request,
    )
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import Request

from backend.audit_center.models import AuditAction, AuditEvent
from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.audit")

_CRITICAL_ACTIONS = {
    AuditAction.USER_DELETED,
    AuditAction.USER_SUSPENDED,
    AuditAction.USER_ROLE_CHANGED,
    AuditAction.PERMISSION_GRANTED,
    AuditAction.PERMISSION_REVOKED,
    AuditAction.MODEL_DEPLOYED,
    AuditAction.MODEL_ROLLED_BACK,
    AuditAction.DATA_ERASURE_REQUESTED,
    AuditAction.API_KEY_CREATED,
    AuditAction.API_KEY_REVOKED,
    AuditAction.CONFIG_CHANGED,
}

_WARNING_ACTIONS = {
    AuditAction.LOGIN_FAILED,
    AuditAction.TOKEN_REVOKED,
    AuditAction.SESSION_DELETED,
    AuditAction.REPORT_REJECTED,
    AuditAction.FLAG_TOGGLED,
}


def _severity(action: str) -> str:
    if action in _CRITICAL_ACTIONS:
        return "critical"
    if action in _WARNING_ACTIONS:
        return "warning"
    return "info"


def _extract_request_meta(request: Optional[Request]) -> tuple:
    if request is None:
        return "", ""
    ip = (request.client.host if request.client else "") or ""
    ua = request.headers.get("user-agent", "")
    return ip, ua


class AuditService:
    def log(
        self,
        tenant_id:     str,
        actor_id:      str,
        action:        str,
        resource_type: str,
        resource_id:   str = "",
        org_id:        Optional[str] = None,
        actor_role:    str = "",
        changes:       Optional[Dict[str, Any]] = None,
        metadata:      Optional[Dict[str, Any]] = None,
        ctx:           Optional[Request] = None,
        session_token: Optional[str] = None,
    ) -> str:
        event_id  = f"evt_{uuid.uuid4().hex[:14]}"
        ip, ua    = _extract_request_meta(ctx)
        severity  = _severity(action)
        timestamp = time.time()

        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO audit_events
                  (event_id, tenant_id, org_id, actor_id, actor_role, action,
                   resource_type, resource_id, changes_json, ip_address, user_agent,
                   session_token, severity, timestamp, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id, tenant_id, org_id, actor_id, actor_role, action,
                    resource_type, resource_id,
                    json.dumps(changes) if changes else None,
                    ip, ua, session_token, severity, timestamp,
                    json.dumps(metadata or {}),
                ),
            )
            con.commit()
        except Exception as exc:
            logger.error("Audit write failed: %s — event=%s action=%s", exc, event_id, action)
        finally:
            con.close()

        if severity == "critical":
            logger.warning("AUDIT[critical] %s by %s resource=%s/%s",
                           action, actor_id, resource_type, resource_id)
        return event_id

    def query(
        self,
        tenant_id:     str,
        actor_id:      Optional[str] = None,
        action:        Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id:   Optional[str] = None,
        severity:      Optional[str] = None,
        since:         Optional[float] = None,
        until:         Optional[float] = None,
        limit:         int = 100,
        offset:        int = 0,
    ) -> List[AuditEvent]:
        clauses = ["tenant_id = ?"]
        params: list = [tenant_id]

        if actor_id:
            clauses.append("actor_id = ?")
            params.append(actor_id)
        if action:
            clauses.append("action = ?")
            params.append(action)
        if resource_type:
            clauses.append("resource_type = ?")
            params.append(resource_type)
        if resource_id:
            clauses.append("resource_id = ?")
            params.append(resource_id)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until:
            clauses.append("timestamp <= ?")
            params.append(until)

        sql = (
            f"SELECT * FROM audit_events WHERE {' AND '.join(clauses)}"
            f" ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        )
        params += [limit, offset]

        con = get_enterprise_conn()
        try:
            rows = con.execute(sql, params).fetchall()
            return [AuditEvent.from_row(r) for r in rows]
        finally:
            con.close()

    def count(self, tenant_id: str, since: Optional[float] = None) -> int:
        con = get_enterprise_conn()
        try:
            if since:
                return con.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE tenant_id = ? AND timestamp >= ?",
                    (tenant_id, since),
                ).fetchone()[0]
            return con.execute(
                "SELECT COUNT(*) FROM audit_events WHERE tenant_id = ?", (tenant_id,)
            ).fetchone()[0]
        finally:
            con.close()

    def summary_by_action(self, tenant_id: str, since: float) -> List[Dict]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                """
                SELECT action, severity, COUNT(*) as count
                FROM audit_events
                WHERE tenant_id = ? AND timestamp >= ?
                GROUP BY action, severity
                ORDER BY count DESC
                """,
                (tenant_id, since),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def export_bundle(self, tenant_id: str, since: float, until: float) -> List[Dict]:
        """Return full audit bundle for a time range — used for compliance exports."""
        events = self.query(
            tenant_id=tenant_id, since=since, until=until, limit=10000
        )
        return [e.to_dict() for e in events]


audit_service = AuditService()
