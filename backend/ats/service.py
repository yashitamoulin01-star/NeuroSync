"""
ATSService — ATS connection management + report export + candidate sync.

Mirrors the meeting-connector service (encrypted tokens via the shared
TokenCipher) and adds export_report, which reads an already-computed session
record and hands a normalized report to the ATS adapter. No AI logic here.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import List, Optional

from backend.ats.models import ATSConnectionRecord, ATSStatus
from backend.ats.registry import ats_registry
from backend.connectors.crypto import token_cipher
from backend.connectors.models import TokenBundle
from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.ats.service")


class ATSError(Exception):
    """ATS operation error surfaced as a 4xx/5xx."""


class ATSService:

    def list_available(self) -> List[dict]:
        return ats_registry.list_available()

    def list_for_org(self, tenant_id: str, org_id: Optional[str]) -> List[ATSConnectionRecord]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM ats_connections WHERE tenant_id = ? ORDER BY provider", (tenant_id,)
            ).fetchall()
            return [ATSConnectionRecord.from_row(r) for r in rows]
        finally:
            con.close()

    def get(self, connection_id: str, tenant_id: str) -> Optional[ATSConnectionRecord]:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM ats_connections WHERE connection_id = ? AND tenant_id = ?",
                (connection_id, tenant_id),
            ).fetchone()
            return ATSConnectionRecord.from_row(row) if row else None
        finally:
            con.close()

    # ── OAuth lifecycle ───────────────────────────────────────────────────────

    def begin_connect(self, provider, tenant_id, org_id, created_by, redirect_uri, name=None) -> dict:
        if not ats_registry.has(provider):
            raise ATSError(f"Unknown ATS provider: {provider}")
        if not token_cipher.available:
            raise ATSError("Token encryption unavailable — cannot connect ATS.")
        adapter = ats_registry.get(provider)
        existing = self._find(tenant_id, org_id, provider)
        connection_id = existing.connection_id if existing else f"ats_{uuid.uuid4().hex[:8]}"
        now = time.time()
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO ats_connections
                  (connection_id, tenant_id, org_id, provider, name, status, capabilities_json, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'disconnected', ?, ?, ?, ?)
                ON CONFLICT(org_id, provider) DO UPDATE SET name=excluded.name, updated_at=excluded.updated_at
                """,
                (connection_id, tenant_id, org_id, provider, name or adapter.display_name,
                 json.dumps(adapter.capabilities.to_dict()), created_by, now, now),
            )
            con.commit()
        finally:
            con.close()
        state = f"{connection_id}:{uuid.uuid4().hex[:8]}"
        return {"connection_id": connection_id, "authorize_url": adapter.authorize_url(redirect_uri, state), "state": state}

    async def complete_connect(self, connection_id, tenant_id, code, redirect_uri) -> ATSConnectionRecord:
        record = self.get(connection_id, tenant_id)
        if not record:
            raise ATSError("ATS connection not found")
        adapter = ats_registry.get(record.provider)
        try:
            tokens = await adapter.exchange_code(code, redirect_uri)
            self._store_tokens(connection_id, tenant_id, tokens)
        except Exception as exc:
            self._mark_error(connection_id, tenant_id, str(exc))
            raise ATSError(f"OAuth exchange failed: {exc}")
        return self.get(connection_id, tenant_id)

    async def refresh(self, connection_id, tenant_id) -> ATSConnectionRecord:
        record, refresh_token = self._load_token(connection_id, tenant_id, "refresh_token_enc")
        adapter = ats_registry.get(record.provider)
        if not refresh_token:
            raise ATSError("No refresh token — reconnect required")
        try:
            tokens = await adapter.refresh(refresh_token)
            self._store_tokens(connection_id, tenant_id, tokens)
        except Exception as exc:
            self._mark_error(connection_id, tenant_id, str(exc))
            raise ATSError(f"Refresh failed: {exc}")
        return self.get(connection_id, tenant_id)

    async def test(self, connection_id, tenant_id) -> dict:
        record, access_token = self._load_token(connection_id, tenant_id, "access_token_enc")
        adapter = ats_registry.get(record.provider)
        result = await adapter.test(access_token or "")
        if result.ok:
            self._touch_sync(connection_id, tenant_id)
        else:
            self._mark_error(connection_id, tenant_id, result.message)
        return result.to_dict()

    def disconnect(self, connection_id, tenant_id) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "DELETE FROM ats_connections WHERE connection_id = ? AND tenant_id = ?",
                (connection_id, tenant_id),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    # ── Export direction ──────────────────────────────────────────────────────

    def _build_report(self, session_id: str) -> dict:
        """Read an already-computed session record into a normalized export payload."""
        from backend.services.db_service import get_session
        row = get_session(session_id)
        if not row:
            raise ATSError("Session not found")
        composure = 1.0 - float(row.get("avg_stress", 0) or 0)
        dims = {
            "confidence":    float(row.get("avg_confidence", 0) or 0),
            "communication": float(row.get("avg_communication", 0) or 0),
            "engagement":    float(row.get("avg_engagement", 0) or 0),
            "consistency":   float(row.get("avg_consistency", 0) or 0),
            "composure":     composure,
        }
        overall = round(sum(dims.values()) / len(dims) * 100)
        return {
            "session_id":   session_id,
            "candidate":    row.get("name", ""),
            "overall_score": overall,
            "dimensions":   {k: round(v * 100) for k, v in dims.items()},
            "duration_s":   round(float(row.get("duration", 0) or 0), 1),
            "transcript_excerpt": (row.get("transcript", "") or "")[:280],
            "source": "NeuroSync Behavioral Intelligence (decision support — human review required)",
        }

    async def export_report(self, connection_id, tenant_id, session_id) -> dict:
        record, access_token = self._load_token(connection_id, tenant_id, "access_token_enc")
        if record.status != ATSStatus.CONNECTED.value or record.is_expired():
            raise ATSError("ATS connection is not active")
        adapter = ats_registry.get(record.provider)
        report = self._build_report(session_id)
        result = await adapter.push_report(access_token or "", report)
        export_id = f"exp_{uuid.uuid4().hex[:10]}"
        con = get_enterprise_conn()
        try:
            con.execute(
                """INSERT INTO ats_exports (export_id, connection_id, tenant_id, session_id, provider, external_ref, ok, message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (export_id, connection_id, tenant_id, session_id, record.provider,
                 result.external_ref, int(result.ok), result.message),
            )
            con.commit()
        finally:
            con.close()
        if result.ok:
            self._touch_sync(connection_id, tenant_id)
        return {"export_id": export_id, **result.to_dict()}

    async def sync_candidates(self, connection_id, tenant_id) -> List[dict]:
        record, access_token = self._load_token(connection_id, tenant_id, "access_token_enc")
        adapter = ats_registry.get(record.provider)
        candidates = await adapter.sync_candidates(access_token or "")
        self._touch_sync(connection_id, tenant_id)
        return [c.to_dict() for c in candidates]

    # ── Internals ─────────────────────────────────────────────────────────────

    def _find(self, tenant_id, org_id, provider):
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM ats_connections WHERE tenant_id = ? AND IFNULL(org_id,'') = IFNULL(?,'') AND provider = ?",
                (tenant_id, org_id, provider),
            ).fetchone()
            return ATSConnectionRecord.from_row(row) if row else None
        finally:
            con.close()

    def _store_tokens(self, connection_id, tenant_id, tokens: TokenBundle):
        access_enc = token_cipher.encrypt(tokens.access_token)
        refresh_enc = token_cipher.encrypt(tokens.refresh_token) if tokens.refresh_token else None
        now = time.time()
        con = get_enterprise_conn()
        try:
            con.execute(
                """UPDATE ats_connections SET access_token_enc=?, refresh_token_enc=COALESCE(?, refresh_token_enc),
                   token_expires_at=?, status='connected', last_sync=?, last_error=NULL, updated_at=?
                   WHERE connection_id=? AND tenant_id=?""",
                (access_enc, refresh_enc, tokens.expires_at, now, now, connection_id, tenant_id),
            )
            con.commit()
        finally:
            con.close()

    def _load_token(self, connection_id, tenant_id, column):
        con = get_enterprise_conn()
        try:
            row = con.execute(
                f"SELECT *, {column} AS _tok FROM ats_connections WHERE connection_id=? AND tenant_id=?",
                (connection_id, tenant_id),
            ).fetchone()
        finally:
            con.close()
        if not row:
            raise ATSError("ATS connection not found")
        return ATSConnectionRecord.from_row(row), (token_cipher.decrypt(row["_tok"]) if row["_tok"] else None)

    def _mark_error(self, connection_id, tenant_id, message):
        con = get_enterprise_conn()
        try:
            con.execute(
                "UPDATE ats_connections SET status='error', last_error=?, updated_at=? WHERE connection_id=? AND tenant_id=?",
                (message[:500], time.time(), connection_id, tenant_id),
            )
            con.commit()
        finally:
            con.close()

    def _touch_sync(self, connection_id, tenant_id):
        con = get_enterprise_conn()
        try:
            con.execute(
                "UPDATE ats_connections SET last_sync=?, last_error=NULL, updated_at=? WHERE connection_id=? AND tenant_id=?",
                (time.time(), time.time(), connection_id, tenant_id),
            )
            con.commit()
        finally:
            con.close()


ats_service = ATSService()
