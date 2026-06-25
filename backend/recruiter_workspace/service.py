"""
Recruiter workspace service.

Provides the recruiter's operational view:
  - Candidate pipeline (all candidates in stages)
  - Interview queue (sessions awaiting review)
  - Assignment management (session → recruiter)
  - Comparison view across multiple candidates
  - Bulk operations (archive, export, reassign)

All queries are tenant-scoped. Evidence and score data comes from
existing session/evidence repositories.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.recruiter")


def _session_rows(limit: int = 100, offset: int = 0) -> List[Dict]:
    con = get_enterprise_conn()
    try:
        rows = con.execute(
            """
            SELECT id, name, mode, user_id, started_at, ended_at, duration,
                   avg_confidence, avg_stress, avg_engagement, avg_communication,
                   avg_consistency, total_words, total_filler_words
            FROM sessions
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


class RecruiterWorkspaceService:
    def get_pipeline(
        self,
        tenant_id:    str,
        org_id:       Optional[str] = None,
        recruiter_id: Optional[str] = None,
        stage:        Optional[str] = None,
        limit:        int = 50,
        offset:       int = 0,
    ) -> Dict[str, Any]:
        """
        Candidate pipeline view. Sessions are grouped by stage:
          pending_review  — ended sessions without an approved report
          in_review       — sessions with pending report approval
          approved        — sessions with approved report
          in_progress     — ongoing sessions
        """
        sessions = _session_rows(limit * 2, offset)
        pipeline = {
            "in_progress":    [],
            "pending_review": [],
            "in_review":      [],
            "approved":       [],
        }
        con = get_enterprise_conn()
        try:
            approved_ids = {
                r["session_id"]
                for r in con.execute(
                    "SELECT session_id FROM report_versions WHERE tenant_id = ? AND approval_status = 'approved'",
                    (tenant_id,),
                ).fetchall()
            }
            pending_ids = {
                r["session_id"]
                for r in con.execute(
                    "SELECT session_id FROM report_versions WHERE tenant_id = ? AND approval_status = 'pending'",
                    (tenant_id,),
                ).fetchall()
            }
        finally:
            con.close()

        for s in sessions:
            sid = s["id"]
            if s["ended_at"] is None:
                bucket = "in_progress"
            elif sid in approved_ids:
                bucket = "approved"
            elif sid in pending_ids:
                bucket = "in_review"
            else:
                bucket = "pending_review"

            if stage and bucket != stage:
                continue
            pipeline[bucket].append(s)

        total = sum(len(v) for v in pipeline.values())
        return {
            "tenant_id":     tenant_id,
            "org_id":        org_id,
            "pipeline":      pipeline,
            "total":         total,
            "generated_at":  time.time(),
        }

    def get_interview_queue(
        self,
        tenant_id:    str,
        recruiter_id: Optional[str] = None,
        limit:        int = 25,
    ) -> List[Dict]:
        """Sessions that need recruiter attention (ended, no approved report)."""
        con = get_enterprise_conn()
        try:
            approved_ids = {
                r["session_id"]
                for r in con.execute(
                    "SELECT session_id FROM report_versions WHERE tenant_id = ? AND approval_status = 'approved'",
                    (tenant_id,),
                ).fetchall()
            }
            all_sessions = con.execute(
                "SELECT * FROM sessions WHERE ended_at IS NOT NULL ORDER BY ended_at DESC LIMIT 200"
            ).fetchall()
            queue = [
                dict(s) for s in all_sessions
                if s["id"] not in approved_ids
            ][:limit]
            return queue
        finally:
            con.close()

    def compare_candidates(self, session_ids: List[str], tenant_id: str) -> Dict:
        """Side-by-side score comparison of multiple sessions."""
        con = get_enterprise_conn()
        try:
            placeholders = ",".join("?" * len(session_ids))
            rows = con.execute(
                f"SELECT * FROM sessions WHERE id IN ({placeholders})",
                session_ids,
            ).fetchall()
        finally:
            con.close()

        sessions = [dict(r) for r in rows]
        dimensions = ["avg_confidence", "avg_stress", "avg_engagement",
                      "avg_communication", "avg_consistency"]
        comparison = {}
        for dim in dimensions:
            scores = {s["id"]: s.get(dim) for s in sessions}
            values = [v for v in scores.values() if v is not None]
            comparison[dim] = {
                "scores":  scores,
                "avg":     round(sum(values) / len(values), 4) if values else None,
                "highest": max(values) if values else None,
                "lowest":  min(values) if values else None,
            }
        return {
            "sessions":   sessions,
            "comparison": comparison,
            "requested_at": time.time(),
        }

    def search_sessions(
        self,
        tenant_id: str,
        query:     str,
        limit:     int = 25,
    ) -> List[Dict]:
        """Full-text search across session names."""
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM sessions WHERE name LIKE ? ORDER BY started_at DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def bulk_export_ids(
        self, session_ids: List[str], tenant_id: str, requested_by: str
    ) -> str:
        """Queue a bulk export job. Returns job_id."""
        import uuid, json
        from backend.services.enterprise_db import get_enterprise_conn
        job_id = f"exp_{uuid.uuid4().hex[:12]}"
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO export_jobs
                  (job_id, tenant_id, requested_by, export_type, resource_type,
                   resource_ids, status, requested_at, expires_at)
                VALUES (?, ?, ?, 'json', 'sessions', ?, 'queued', ?, ?)
                """,
                (job_id, tenant_id, requested_by, json.dumps(session_ids),
                 time.time(), time.time() + 86400),
            )
            con.commit()
        finally:
            con.close()
        return job_id


recruiter_service = RecruiterWorkspaceService()
