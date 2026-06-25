"""
ConnectorService — the only code that touches plaintext OAuth tokens.

Responsibilities: per-org connector CRUD, OAuth connect/callback, disconnect,
refresh, test, and meeting sync. All token material is encrypted via TokenCipher
before it touches the DB and is never returned to callers.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import List, Optional

from backend.connectors.crypto import token_cipher
from backend.connectors.models import (
    ConnectorRecord, ConnectorStatus, MeetingRef, TokenBundle,
)
from backend.connectors.registry import registry
from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.connectors.service")


class ConnectorError(Exception):
    """Raised for connector operations that should surface as a 4xx/5xx."""


class ConnectorService:

    # ── Catalog ───────────────────────────────────────────────────────────────

    def list_available(self) -> List[dict]:
        return registry.list_available()

    # ── Read ──────────────────────────────────────────────────────────────────

    def list_for_org(self, tenant_id: str, org_id: Optional[str]) -> List[ConnectorRecord]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM connectors WHERE tenant_id = ? ORDER BY provider",
                (tenant_id,),
            ).fetchall()
            return [ConnectorRecord.from_row(r) for r in rows]
        finally:
            con.close()

    def get(self, connector_id: str, tenant_id: str) -> Optional[ConnectorRecord]:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM connectors WHERE connector_id = ? AND tenant_id = ?",
                (connector_id, tenant_id),
            ).fetchone()
            return ConnectorRecord.from_row(row) if row else None
        finally:
            con.close()

    # ── OAuth lifecycle ───────────────────────────────────────────────────────

    def begin_connect(
        self, provider: str, tenant_id: str, org_id: Optional[str],
        created_by: str, redirect_uri: str, name: Optional[str] = None,
    ) -> dict:
        """
        Create (or reuse) a connector row in 'disconnected' state and return the
        provider authorize URL. `state` binds the callback to this connector.
        """
        if not registry.has(provider):
            raise ConnectorError(f"Unknown provider: {provider}")
        if not token_cipher.available:
            raise ConnectorError(
                "Token encryption unavailable — cannot connect. Install `cryptography` "
                "and set CONNECTOR_ENCRYPTION_KEY."
            )

        connector = registry.get(provider)
        existing = self._find_by_org_provider(tenant_id, org_id, provider)
        connector_id = existing.connector_id if existing else f"conn_{uuid.uuid4().hex[:8]}"
        display_name = name or connector.display_name
        now = time.time()

        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO connectors
                    (connector_id, tenant_id, org_id, provider, name, status,
                     scopes_json, capabilities_json, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'disconnected', ?, ?, ?, ?, ?)
                ON CONFLICT(org_id, provider) DO UPDATE SET
                    name = excluded.name, updated_at = excluded.updated_at
                """,
                (
                    connector_id, tenant_id, org_id, provider, display_name,
                    json.dumps(connector.oauth.scopes),
                    json.dumps(connector.capabilities.to_dict()),
                    created_by, now, now,
                ),
            )
            con.commit()
        finally:
            con.close()

        state = f"{connector_id}:{uuid.uuid4().hex[:8]}"
        authorize_url = connector.authorize_url(redirect_uri, state)
        logger.info("Connector connect initiated: %s provider=%s org=%s", connector_id, provider, org_id)
        return {"connector_id": connector_id, "authorize_url": authorize_url, "state": state}

    async def complete_connect(
        self, connector_id: str, tenant_id: str, code: str, redirect_uri: str,
    ) -> ConnectorRecord:
        """OAuth callback handler: exchange code, encrypt + store tokens."""
        record = self.get(connector_id, tenant_id)
        if not record:
            raise ConnectorError("Connector not found")
        connector = registry.get(record.provider)
        try:
            tokens = await connector.exchange_code(code, redirect_uri)
            self._store_tokens(connector_id, tenant_id, tokens, status=ConnectorStatus.CONNECTED)
        except Exception as exc:
            self._mark_error(connector_id, tenant_id, str(exc))
            raise ConnectorError(f"OAuth exchange failed: {exc}")
        return self.get(connector_id, tenant_id)

    async def refresh(self, connector_id: str, tenant_id: str) -> ConnectorRecord:
        record, refresh_token = self._load_with_token(connector_id, tenant_id, "refresh_token_enc")
        connector = registry.get(record.provider)
        if not refresh_token:
            raise ConnectorError("No refresh token stored — reconnect required")
        try:
            tokens = await connector.refresh(refresh_token)
            self._store_tokens(connector_id, tenant_id, tokens, status=ConnectorStatus.CONNECTED)
        except Exception as exc:
            self._mark_error(connector_id, tenant_id, str(exc))
            raise ConnectorError(f"Token refresh failed: {exc}")
        return self.get(connector_id, tenant_id)

    async def test(self, connector_id: str, tenant_id: str) -> dict:
        record, access_token = self._load_with_token(connector_id, tenant_id, "access_token_enc")
        connector = registry.get(record.provider)
        result = await connector.test(access_token or "")
        if result.ok:
            self._touch_sync(connector_id, tenant_id)
        else:
            self._mark_error(connector_id, tenant_id, result.message)
        return result.to_dict()

    async def list_upcoming_meetings(self, connector_id: str, tenant_id: str) -> List[MeetingRef]:
        record, access_token = self._load_with_token(connector_id, tenant_id, "access_token_enc")
        connector = registry.get(record.provider)
        return await connector.list_upcoming_meetings(access_token or "")

    async def list_all_upcoming(self, tenant_id: str, org_id: Optional[str]) -> List[dict]:
        """
        Aggregate upcoming meetings across every connected connector for the tenant,
        tagged with provider + connector_id, sorted by start time. Drives the
        'Upcoming Interviews' dashboard surface.
        """
        out: List[dict] = []
        for record in self.list_for_org(tenant_id, org_id):
            if record.status != ConnectorStatus.CONNECTED.value or record.is_expired():
                continue
            try:
                meetings = await self.list_upcoming_meetings(record.connector_id, tenant_id)
            except Exception as exc:
                logger.debug("Upcoming fetch failed for %s: %s", record.connector_id, exc)
                continue
            for m in meetings:
                out.append({
                    **m.to_dict(),
                    "provider":     record.provider,
                    "connector_id": record.connector_id,
                })
        out.sort(key=lambda m: m["start_time"])
        return out

    def disconnect(self, connector_id: str, tenant_id: str) -> bool:
        """Delete tokens and the connection row. Tokens are wiped from disk."""
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "DELETE FROM connectors WHERE connector_id = ? AND tenant_id = ?",
                (connector_id, tenant_id),
            )
            con.commit()
            if cur.rowcount:
                logger.info("Connector disconnected + tokens wiped: %s", connector_id)
            return cur.rowcount > 0
        finally:
            con.close()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _find_by_org_provider(self, tenant_id, org_id, provider) -> Optional[ConnectorRecord]:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM connectors WHERE tenant_id = ? AND IFNULL(org_id,'') = IFNULL(?,'') AND provider = ?",
                (tenant_id, org_id, provider),
            ).fetchone()
            return ConnectorRecord.from_row(row) if row else None
        finally:
            con.close()

    def _store_tokens(self, connector_id, tenant_id, tokens: TokenBundle, status: ConnectorStatus) -> None:
        access_enc  = token_cipher.encrypt(tokens.access_token)
        refresh_enc = token_cipher.encrypt(tokens.refresh_token) if tokens.refresh_token else None
        now = time.time()
        con = get_enterprise_conn()
        try:
            # Preserve an existing refresh token if the provider didn't return a new one.
            con.execute(
                """
                UPDATE connectors SET
                    access_token_enc = ?,
                    refresh_token_enc = COALESCE(?, refresh_token_enc),
                    token_expires_at = ?, scopes_json = ?, status = ?,
                    last_sync = ?, last_error = NULL, updated_at = ?
                WHERE connector_id = ? AND tenant_id = ?
                """,
                (
                    access_enc, refresh_enc, tokens.expires_at,
                    json.dumps(tokens.scopes), status.value, now, now,
                    connector_id, tenant_id,
                ),
            )
            con.commit()
        finally:
            con.close()

    def _load_with_token(self, connector_id, tenant_id, column: str):
        con = get_enterprise_conn()
        try:
            row = con.execute(
                f"SELECT *, {column} AS _tok FROM connectors WHERE connector_id = ? AND tenant_id = ?",
                (connector_id, tenant_id),
            ).fetchone()
        finally:
            con.close()
        if not row:
            raise ConnectorError("Connector not found")
        record = ConnectorRecord.from_row(row)
        token = token_cipher.decrypt(row["_tok"]) if row["_tok"] else None
        return record, token

    def _mark_error(self, connector_id, tenant_id, message: str) -> None:
        con = get_enterprise_conn()
        try:
            con.execute(
                "UPDATE connectors SET status = 'error', last_error = ?, updated_at = ? WHERE connector_id = ? AND tenant_id = ?",
                (message[:500], time.time(), connector_id, tenant_id),
            )
            con.commit()
        finally:
            con.close()

    def _touch_sync(self, connector_id, tenant_id) -> None:
        con = get_enterprise_conn()
        try:
            con.execute(
                "UPDATE connectors SET last_sync = ?, last_error = NULL, updated_at = ? WHERE connector_id = ? AND tenant_id = ?",
                (time.time(), time.time(), connector_id, tenant_id),
            )
            con.commit()
        finally:
            con.close()


connector_service = ConnectorService()
