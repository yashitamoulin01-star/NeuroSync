"""
Immutable report versioning.

Every generated report is stored as an immutable version with:
  - Model version + reasoning version captured at generation time
  - SHA-256 hash of content for tamper detection
  - Approval workflow (pending → approved | rejected)
  - Evidence snapshot embedded at the point of generation
  - Configuration snapshot for full reproducibility

Reports NEVER change after generation. A correction creates a new version.
The immutable_hash allows any party to verify the report was not modified.

Usage:
    report = report_versioning.generate(
        session_id="ses_abc",
        tenant_id="ten_xyz",
        generated_by="usr_000",
        scores={...},
        evidence={...},
    )
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.reports")

_REASONING_VERSION = "3.0"   # Phase 7
_PIPELINE_HASH     = hashlib.sha256(b"neurosync-pipeline-v7").hexdigest()[:16]


def _content_hash(content: dict) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class ReportVersion:
    report_id:         str
    session_id:        str
    tenant_id:         str
    org_id:            Optional[str]
    version_num:       int
    model_version:     str
    reasoning_version: str
    pipeline_hash:     str
    scores:            Dict[str, Any]
    evidence:          Dict[str, Any]
    config:            Dict[str, Any]
    generated_by:      str
    generated_at:      float
    approved_by:       Optional[str]
    approved_at:       Optional[float]
    approval_status:   str    # pending | approved | rejected
    immutable_hash:    str

    def verify_integrity(self) -> bool:
        """Recompute content hash and compare against stored value."""
        content = {
            "session_id":        self.session_id,
            "scores":            self.scores,
            "evidence":          self.evidence,
            "model_version":     self.model_version,
            "reasoning_version": self.reasoning_version,
            "generated_at":      self.generated_at,
        }
        return _content_hash(content) == self.immutable_hash

    def to_dict(self, include_evidence: bool = True) -> Dict[str, Any]:
        d = {
            "report_id":         self.report_id,
            "session_id":        self.session_id,
            "tenant_id":         self.tenant_id,
            "org_id":            self.org_id,
            "version_num":       self.version_num,
            "model_version":     self.model_version,
            "reasoning_version": self.reasoning_version,
            "pipeline_hash":     self.pipeline_hash,
            "scores":            self.scores,
            "config":            self.config,
            "generated_by":      self.generated_by,
            "generated_at":      self.generated_at,
            "approved_by":       self.approved_by,
            "approved_at":       self.approved_at,
            "approval_status":   self.approval_status,
            "immutable_hash":    self.immutable_hash,
            "integrity_verified": self.verify_integrity(),
        }
        if include_evidence:
            d["evidence"] = self.evidence
        return d

    @classmethod
    def from_row(cls, row) -> "ReportVersion":
        return cls(
            report_id         = row["report_id"],
            session_id        = row["session_id"],
            tenant_id         = row["tenant_id"],
            org_id            = row["org_id"],
            version_num       = row["version_num"],
            model_version     = row["model_version"],
            reasoning_version = row["reasoning_version"],
            pipeline_hash     = row["pipeline_hash"],
            scores            = json.loads(row["scores_json"]),
            evidence          = json.loads(row["evidence_json"]),
            config            = json.loads(row["config_json"]),
            generated_by      = row["generated_by"],
            generated_at      = row["generated_at"],
            approved_by       = row["approved_by"],
            approved_at       = row["approved_at"],
            approval_status   = row["approval_status"],
            immutable_hash    = row["immutable_hash"],
        )


class ReportVersioningService:
    def generate(
        self,
        session_id:    str,
        tenant_id:     str,
        generated_by:  str,
        scores:        Dict[str, Any],
        evidence:      Dict[str, Any],
        org_id:        Optional[str] = None,
        model_version: str = "1.0",
        config:        Optional[Dict] = None,
    ) -> ReportVersion:
        report_id    = f"rpt_{uuid.uuid4().hex[:14]}"
        generated_at = time.time()
        cfg          = config or {}

        # Compute next version number for this session
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT MAX(version_num) as max_v FROM report_versions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            version_num = (row["max_v"] or 0) + 1

            content_for_hash = {
                "session_id":        session_id,
                "scores":            scores,
                "evidence":          evidence,
                "model_version":     model_version,
                "reasoning_version": _REASONING_VERSION,
                "generated_at":      generated_at,
            }
            immutable_hash = _content_hash(content_for_hash)

            con.execute(
                """
                INSERT INTO report_versions
                  (report_id, session_id, tenant_id, org_id, version_num, model_version,
                   reasoning_version, pipeline_hash, scores_json, evidence_json, config_json,
                   generated_by, generated_at, approval_status, immutable_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (report_id, session_id, tenant_id, org_id, version_num, model_version,
                 _REASONING_VERSION, _PIPELINE_HASH,
                 json.dumps(scores), json.dumps(evidence), json.dumps(cfg),
                 generated_by, generated_at, immutable_hash),
            )
            con.commit()
            logger.info("Report generated: %s v%d session=%s", report_id, version_num, session_id)
        finally:
            con.close()

        return ReportVersion(
            report_id=report_id, session_id=session_id, tenant_id=tenant_id,
            org_id=org_id, version_num=version_num, model_version=model_version,
            reasoning_version=_REASONING_VERSION, pipeline_hash=_PIPELINE_HASH,
            scores=scores, evidence=evidence, config=cfg,
            generated_by=generated_by, generated_at=generated_at,
            approved_by=None, approved_at=None, approval_status="pending",
            immutable_hash=immutable_hash,
        )

    def get_latest(self, session_id: str, tenant_id: str) -> Optional[ReportVersion]:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM report_versions WHERE session_id = ? AND tenant_id = ? ORDER BY version_num DESC LIMIT 1",
                (session_id, tenant_id),
            ).fetchone()
            return ReportVersion.from_row(row) if row else None
        finally:
            con.close()

    def get_version(self, report_id: str, tenant_id: str) -> Optional[ReportVersion]:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM report_versions WHERE report_id = ? AND tenant_id = ?",
                (report_id, tenant_id),
            ).fetchone()
            return ReportVersion.from_row(row) if row else None
        finally:
            con.close()

    def list_versions(self, session_id: str, tenant_id: str) -> List[ReportVersion]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM report_versions WHERE session_id = ? AND tenant_id = ? ORDER BY version_num DESC",
                (session_id, tenant_id),
            ).fetchall()
            return [ReportVersion.from_row(r) for r in rows]
        finally:
            con.close()

    def approve(self, report_id: str, tenant_id: str, approver_id: str) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE report_versions SET approval_status = 'approved', approved_by = ?, approved_at = ? WHERE report_id = ? AND tenant_id = ? AND approval_status = 'pending'",
                (approver_id, time.time(), report_id, tenant_id),
            )
            con.commit()
            if cur.rowcount:
                logger.info("Report %s approved by %s", report_id, approver_id)
            return cur.rowcount > 0
        finally:
            con.close()

    def reject(self, report_id: str, tenant_id: str, reviewer_id: str) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE report_versions SET approval_status = 'rejected', approved_by = ?, approved_at = ? WHERE report_id = ? AND tenant_id = ? AND approval_status = 'pending'",
                (reviewer_id, time.time(), report_id, tenant_id),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    def verify_report(self, report_id: str, tenant_id: str) -> Dict:
        """Verify the integrity of a stored report against its hash."""
        report = self.get_version(report_id, tenant_id)
        if report is None:
            return {"verified": False, "error": "not_found"}
        verified = report.verify_integrity()
        return {
            "report_id":      report_id,
            "verified":       verified,
            "immutable_hash": report.immutable_hash,
            "version_num":    report.version_num,
            "generated_at":   report.generated_at,
        }


report_versioning = ReportVersioningService()
