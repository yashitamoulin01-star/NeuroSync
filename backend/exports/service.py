"""
Export service — multi-format export with metadata inclusion.

Formats:
  json             — Machine-readable full export
  csv              — Tabular scores (spreadsheet compatible)
  evidence_package — JSON with embedded evidence timeline
  audit_bundle     — Audit events for a time range
  executive_summary — High-level scores and behavioral narrative

All exports include version metadata for traceability.
Export jobs are queued and tracked in the export_jobs table.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.exports")

_EXPORT_VERSION = "1.0"


def _get_session(session_id: str) -> Optional[Dict]:
    con = get_enterprise_conn()
    try:
        row = con.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def _get_frames(session_id: str) -> List[Dict]:
    con = get_enterprise_conn()
    try:
        rows = con.execute(
            "SELECT ts, confidence, stress, engagement, communication, consistency, is_speaking FROM session_frames WHERE session_id = ? ORDER BY ts",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


class ExportService:
    def _create_job(
        self,
        tenant_id:     str,
        requested_by:  str,
        export_type:   str,
        resource_type: str,
        resource_ids:  List[str],
        org_id:        Optional[str] = None,
    ) -> str:
        job_id = f"exp_{uuid.uuid4().hex[:12]}"
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO export_jobs
                  (job_id, tenant_id, org_id, requested_by, export_type, resource_type,
                   resource_ids, status, requested_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'processing', ?, ?)
                """,
                (job_id, tenant_id, org_id, requested_by, export_type, resource_type,
                 json.dumps(resource_ids), time.time(), time.time() + 86400),
            )
            con.commit()
        finally:
            con.close()
        return job_id

    def _complete_job(self, job_id: str, result_path: Optional[str] = None) -> None:
        con = get_enterprise_conn()
        try:
            con.execute(
                "UPDATE export_jobs SET status = 'completed', completed_at = ?, result_path = ? WHERE job_id = ?",
                (time.time(), result_path, job_id),
            )
            con.commit()
        finally:
            con.close()

    def _fail_job(self, job_id: str, error: str) -> None:
        con = get_enterprise_conn()
        try:
            con.execute(
                "UPDATE export_jobs SET status = 'failed', error_msg = ?, completed_at = ? WHERE job_id = ?",
                (error, time.time(), job_id),
            )
            con.commit()
        finally:
            con.close()

    def export_session_json(
        self, session_id: str, tenant_id: str, requested_by: str
    ) -> Dict[str, Any]:
        job_id  = self._create_job(tenant_id, requested_by, "json", "session", [session_id])
        session = _get_session(session_id)
        if session is None:
            self._fail_job(job_id, "session_not_found")
            raise LookupError(f"Session {session_id} not found")

        frames = _get_frames(session_id)
        payload = {
            "export_format":  "json",
            "export_version": _EXPORT_VERSION,
            "exported_at":    time.time(),
            "exported_by":    requested_by,
            "tenant_id":      tenant_id,
            "session":        session,
            "frames":         frames,
        }
        self._complete_job(job_id)
        return payload

    def export_session_csv(
        self, session_ids: List[str], tenant_id: str, requested_by: str
    ) -> str:
        """Return CSV string of session scores."""
        job_id = self._create_job(tenant_id, requested_by, "csv", "session", session_ids)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "session_id", "name", "mode", "started_at", "duration",
            "avg_confidence", "avg_stress", "avg_engagement",
            "avg_communication", "avg_consistency", "total_words",
        ])
        writer.writeheader()
        for sid in session_ids:
            s = _get_session(sid)
            if s:
                writer.writerow({
                    "session_id":      s["id"],
                    "name":            s.get("name", ""),
                    "mode":            s.get("mode", ""),
                    "started_at":      s.get("started_at", ""),
                    "duration":        s.get("duration", ""),
                    "avg_confidence":  s.get("avg_confidence", ""),
                    "avg_stress":      s.get("avg_stress", ""),
                    "avg_engagement":  s.get("avg_engagement", ""),
                    "avg_communication": s.get("avg_communication", ""),
                    "avg_consistency": s.get("avg_consistency", ""),
                    "total_words":     s.get("total_words", ""),
                })
        self._complete_job(job_id)
        return output.getvalue()

    def export_evidence_package(
        self, session_id: str, tenant_id: str, requested_by: str
    ) -> Dict[str, Any]:
        """Full evidence package including frame timeline and report versions."""
        job_id  = self._create_job(tenant_id, requested_by, "evidence_package", "session", [session_id])
        session = _get_session(session_id)
        if session is None:
            self._fail_job(job_id, "session_not_found")
            raise LookupError(f"Session {session_id} not found")

        frames  = _get_frames(session_id)
        con = get_enterprise_conn()
        try:
            reports = con.execute(
                "SELECT report_id, version_num, model_version, approval_status, generated_at, immutable_hash FROM report_versions WHERE session_id = ? AND tenant_id = ? ORDER BY version_num",
                (session_id, tenant_id),
            ).fetchall()
            report_list = [dict(r) for r in reports]
        finally:
            con.close()

        payload = {
            "export_format":  "evidence_package",
            "export_version": _EXPORT_VERSION,
            "exported_at":    time.time(),
            "exported_by":    requested_by,
            "tenant_id":      tenant_id,
            "session":        session,
            "behavioral_timeline": frames,
            "report_versions":     report_list,
            "frame_count":         len(frames),
        }
        self._complete_job(job_id)
        return payload

    def export_audit_bundle(
        self,
        tenant_id:    str,
        requested_by: str,
        since:        float,
        until:        Optional[float] = None,
    ) -> Dict[str, Any]:
        """Compliance-grade audit bundle for external review."""
        until = until or time.time()
        job_id = self._create_job(tenant_id, requested_by, "audit_bundle", "audit_events", [])
        from backend.audit_center.service import audit_service
        events = audit_service.export_bundle(tenant_id, since, until)
        payload = {
            "export_format":  "audit_bundle",
            "export_version": _EXPORT_VERSION,
            "exported_at":    time.time(),
            "exported_by":    requested_by,
            "tenant_id":      tenant_id,
            "period_start":   since,
            "period_end":     until,
            "event_count":    len(events),
            "events":         events,
        }
        self._complete_job(job_id)
        return payload

    def executive_summary(
        self, session_id: str, tenant_id: str, requested_by: str
    ) -> Dict[str, Any]:
        """Executive summary: high-level narrative without raw data."""
        session = _get_session(session_id)
        if session is None:
            raise LookupError(f"Session {session_id} not found")

        def _label(score: Optional[float], low: float, high: float) -> str:
            if score is None:
                return "N/A"
            if score >= high:
                return "High"
            if score >= low:
                return "Moderate"
            return "Low"

        return {
            "export_format":  "executive_summary",
            "session_id":     session_id,
            "session_name":   session.get("name"),
            "completed_at":   session.get("ended_at"),
            "duration_min":   round((session.get("duration") or 0) / 60, 1),
            "generated_at":   time.time(),
            "generated_by":   requested_by,
            "behavioral_summary": {
                "confidence":    _label(session.get("avg_confidence"),    0.5, 0.72),
                "stress":        _label(session.get("avg_stress"),         0.35, 0.6),
                "engagement":    _label(session.get("avg_engagement"),     0.5, 0.72),
                "communication": _label(session.get("avg_communication"),  0.5, 0.72),
                "consistency":   _label(session.get("avg_consistency"),    0.5, 0.72),
            },
            "word_count":     session.get("total_words"),
            "note": "This summary reflects behavioral signal patterns detected by the NeuroSync AI system. Human review is required before any employment decision.",
        }

    def list_jobs(self, tenant_id: str, limit: int = 25) -> List[Dict]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM export_jobs WHERE tenant_id = ? ORDER BY requested_at DESC LIMIT ?",
                (tenant_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


export_service = ExportService()
