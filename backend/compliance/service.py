"""
Compliance service — retention policies, consent management, data requests.

Prepares the platform for GDPR, SOC2, and ISO27001 compliance.
Implements the architecture (not certifications) required by enterprise buyers.

Key capabilities:
  - Data retention policies per resource type
  - Consent tracking with expiry
  - Data subject access request (DSAR) management
  - Soft delete and hard delete workflows
  - Data export for portability requests
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Dict, List, Optional

from backend.compliance.models import ConsentRecord, DataRequest, RetentionPolicy
from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.compliance")

_VALID_PURPOSES      = {"analytics", "recording", "ai_processing", "profiling", "marketing"}
_VALID_REQUEST_TYPES = {"export", "erasure", "portability", "rectification"}


class ComplianceService:
    # ── Retention Policies ────────────────────────────────────────────────────

    def create_retention_policy(
        self,
        org_id:        str,
        tenant_id:     str,
        name:          str,
        resource_type: str,
        retain_days:   int,
        action_after:  str = "soft_delete",
    ) -> RetentionPolicy:
        if retain_days < 1:
            raise ValueError("retain_days must be >= 1")
        policy_id  = f"rp_{uuid.uuid4().hex[:10]}"
        created_at = time.time()
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT OR REPLACE INTO retention_policies
                  (policy_id, org_id, tenant_id, name, resource_type, retain_days, action_after, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (policy_id, org_id, tenant_id, name, resource_type,
                 retain_days, action_after, created_at),
            )
            con.commit()
            logger.info("Retention policy created: %s (%s) retain=%dd", name, resource_type, retain_days)
        finally:
            con.close()
        return RetentionPolicy(
            policy_id=policy_id, org_id=org_id, tenant_id=tenant_id, name=name,
            resource_type=resource_type, retain_days=retain_days,
            action_after=action_after, enabled=True, created_at=created_at,
        )

    def list_retention_policies(self, tenant_id: str, org_id: str) -> List[RetentionPolicy]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM retention_policies WHERE tenant_id = ? AND org_id = ? ORDER BY resource_type",
                (tenant_id, org_id),
            ).fetchall()
            return [RetentionPolicy.from_row(r) for r in rows]
        finally:
            con.close()

    def get_policy_for_resource(
        self, tenant_id: str, org_id: str, resource_type: str
    ) -> Optional[RetentionPolicy]:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM retention_policies WHERE tenant_id = ? AND org_id = ? AND resource_type = ? AND enabled = 1",
                (tenant_id, org_id, resource_type),
            ).fetchone()
            return RetentionPolicy.from_row(row) if row else None
        finally:
            con.close()

    # ── Consent Management ────────────────────────────────────────────────────

    def record_consent(
        self,
        tenant_id:  str,
        subject_id: str,
        purpose:    str,
        granted:    bool,
        ip_address: str = "",
        version:    str = "1.0",
        expires_at: Optional[float] = None,
    ) -> ConsentRecord:
        if purpose not in _VALID_PURPOSES:
            raise ValueError(f"Unknown purpose: {purpose}. Valid: {_VALID_PURPOSES}")
        consent_id = f"con_{uuid.uuid4().hex[:12]}"
        granted_at = time.time()
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO consent_records
                  (consent_id, tenant_id, subject_id, purpose, granted, granted_at, expires_at, ip_address, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (consent_id, tenant_id, subject_id, purpose, 1 if granted else 0,
                 granted_at, expires_at, ip_address, version),
            )
            con.commit()
        finally:
            con.close()
        action = "granted" if granted else "revoked"
        logger.info("Consent %s: subject=%s purpose=%s", action, subject_id, purpose)
        return ConsentRecord(
            consent_id=consent_id, tenant_id=tenant_id, subject_id=subject_id,
            purpose=purpose, granted=granted, granted_at=granted_at,
            expires_at=expires_at, ip_address=ip_address, version=version,
        )

    def get_active_consents(self, tenant_id: str, subject_id: str) -> List[ConsentRecord]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                """
                SELECT * FROM consent_records
                WHERE tenant_id = ? AND subject_id = ? AND granted = 1
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY granted_at DESC
                """,
                (tenant_id, subject_id, time.time()),
            ).fetchall()
            return [ConsentRecord.from_row(r) for r in rows]
        finally:
            con.close()

    def has_consent(self, tenant_id: str, subject_id: str, purpose: str) -> bool:
        consents = self.get_active_consents(tenant_id, subject_id)
        return any(c.purpose == purpose for c in consents)

    # ── Data Subject Requests (DSAR) ──────────────────────────────────────────

    def create_data_request(
        self,
        tenant_id:    str,
        subject_id:   str,
        request_type: str,
        notes:        Optional[str] = None,
    ) -> DataRequest:
        if request_type not in _VALID_REQUEST_TYPES:
            raise ValueError(f"Unknown request type: {request_type}")
        request_id   = f"dr_{uuid.uuid4().hex[:12]}"
        requested_at = time.time()
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO data_requests
                  (request_id, tenant_id, subject_id, request_type, status, requested_at, notes)
                VALUES (?, ?, ?, ?, 'pending', ?, ?)
                """,
                (request_id, tenant_id, subject_id, request_type, requested_at, notes),
            )
            con.commit()
            logger.info("Data request created: %s type=%s subject=%s",
                        request_id, request_type, subject_id)
        finally:
            con.close()
        return DataRequest(
            request_id=request_id, tenant_id=tenant_id, subject_id=subject_id,
            request_type=request_type, status="pending", requested_at=requested_at,
            completed_at=None, result_path=None, notes=notes,
        )

    def list_data_requests(
        self, tenant_id: str, status: Optional[str] = None
    ) -> List[DataRequest]:
        con = get_enterprise_conn()
        try:
            if status:
                rows = con.execute(
                    "SELECT * FROM data_requests WHERE tenant_id = ? AND status = ? ORDER BY requested_at DESC",
                    (tenant_id, status),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM data_requests WHERE tenant_id = ? ORDER BY requested_at DESC",
                    (tenant_id,),
                ).fetchall()
            return [DataRequest.from_row(r) for r in rows]
        finally:
            con.close()

    def complete_data_request(
        self, tenant_id: str, request_id: str, result_path: Optional[str] = None
    ) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                """
                UPDATE data_requests
                SET status = 'completed', completed_at = ?, result_path = ?
                WHERE request_id = ? AND tenant_id = ?
                """,
                (time.time(), result_path, request_id, tenant_id),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    def get_compliance_summary(self, tenant_id: str) -> Dict:
        con = get_enterprise_conn()
        try:
            pending = con.execute(
                "SELECT COUNT(*) FROM data_requests WHERE tenant_id = ? AND status = 'pending'",
                (tenant_id,),
            ).fetchone()[0]
            consent_count = con.execute(
                "SELECT COUNT(DISTINCT subject_id) FROM consent_records WHERE tenant_id = ? AND granted = 1",
                (tenant_id,),
            ).fetchone()[0]
            policies = con.execute(
                "SELECT COUNT(*) FROM retention_policies WHERE tenant_id = ? AND enabled = 1",
                (tenant_id,),
            ).fetchone()[0]
            return {
                "pending_data_requests": pending,
                "subjects_with_consent": consent_count,
                "active_retention_policies": policies,
            }
        finally:
            con.close()


compliance_service = ComplianceService()
