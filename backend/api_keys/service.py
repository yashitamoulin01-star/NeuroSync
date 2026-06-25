"""
API key service — enterprise API authentication.

Keys are one-way hashed (SHA-256) before storage.
The raw key is only returned once at creation time.

Key format: "nsk_<prefix8>_<random48>"
  prefix8 — used for display and quick lookup
  random48 — cryptographically random, never stored in cleartext

Scopes control what API surface a key can access.
Rate limits are per-key and enforced by the API middleware.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import List, Optional

from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.api_keys")

_ALL_SCOPES = {
    "sessions:read", "sessions:write",
    "reports:read",
    "analytics:read",
    "admin:read",
    "audit:read",
}


@dataclass
class ApiKey:
    key_id:     str
    tenant_id:  str
    org_id:     Optional[str]
    created_by: str
    name:       str
    key_prefix: str
    scopes:     List[str]
    status:     str
    expires_at: Optional[float]
    last_used:  Optional[float]
    rate_limit: int
    created_at: float

    def is_active(self) -> bool:
        if self.status != "active":
            return False
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "key_id":     self.key_id,
            "tenant_id":  self.tenant_id,
            "org_id":     self.org_id,
            "created_by": self.created_by,
            "name":       self.name,
            "key_prefix": self.key_prefix,
            "scopes":     self.scopes,
            "status":     self.status,
            "expires_at": self.expires_at,
            "last_used":  self.last_used,
            "rate_limit": self.rate_limit,
            "created_at": self.created_at,
        }

    @classmethod
    def from_row(cls, row) -> "ApiKey":
        return cls(
            key_id     = row["key_id"],
            tenant_id  = row["tenant_id"],
            org_id     = row["org_id"],
            created_by = row["created_by"],
            name       = row["name"],
            key_prefix = row["key_prefix"],
            scopes     = json.loads(row["scopes_json"] or "[]"),
            status     = row["status"],
            expires_at = row["expires_at"],
            last_used  = row["last_used"],
            rate_limit = row["rate_limit"],
            created_at = row["created_at"],
        )


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class ApiKeyService:
    def create(
        self,
        tenant_id:  str,
        created_by: str,
        name:       str,
        scopes:     Optional[List[str]] = None,
        org_id:     Optional[str] = None,
        expires_at: Optional[float] = None,
        rate_limit: int = 1000,
    ) -> tuple:    # (ApiKey, raw_key)
        raw_key    = f"nsk_{secrets.token_hex(4)}_{secrets.token_hex(24)}"
        key_prefix = raw_key[:12]
        key_hash   = _hash_key(raw_key)
        key_id     = f"ak_{uuid.uuid4().hex[:10]}"
        created_at = time.time()
        effective_scopes = scopes or ["sessions:read"]

        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO api_keys
                  (key_id, tenant_id, org_id, created_by, name, key_hash, key_prefix,
                   scopes_json, status, expires_at, rate_limit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (key_id, tenant_id, org_id, created_by, name, key_hash, key_prefix,
                 json.dumps(effective_scopes), expires_at, rate_limit, created_at),
            )
            con.commit()
            logger.info("API key created: %s (%s) by %s scopes=%s",
                        name, key_prefix, created_by, effective_scopes)
        finally:
            con.close()

        key_obj = ApiKey(
            key_id=key_id, tenant_id=tenant_id, org_id=org_id, created_by=created_by,
            name=name, key_prefix=key_prefix, scopes=effective_scopes, status="active",
            expires_at=expires_at, last_used=None, rate_limit=rate_limit, created_at=created_at,
        )
        return key_obj, raw_key

    def validate(self, raw_key: str) -> Optional[ApiKey]:
        if not raw_key.startswith("nsk_"):
            return None
        key_hash = _hash_key(raw_key)
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM api_keys WHERE key_hash = ? AND status = 'active'",
                (key_hash,),
            ).fetchone()
            if row is None:
                return None
            key = ApiKey.from_row(row)
            if not key.is_active():
                return None
            con.execute(
                "UPDATE api_keys SET last_used = ? WHERE key_id = ?",
                (time.time(), key.key_id),
            )
            con.commit()
            return key
        finally:
            con.close()

    def revoke(self, key_id: str, tenant_id: str, revoked_by: str) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE api_keys SET status = 'revoked' WHERE key_id = ? AND tenant_id = ?",
                (key_id, tenant_id),
            )
            con.commit()
            if cur.rowcount:
                logger.warning("API key %s revoked by %s", key_id, revoked_by)
            return cur.rowcount > 0
        finally:
            con.close()

    def list_for_tenant(self, tenant_id: str, org_id: Optional[str] = None) -> List[ApiKey]:
        con = get_enterprise_conn()
        try:
            if org_id:
                rows = con.execute(
                    "SELECT * FROM api_keys WHERE tenant_id = ? AND org_id = ? ORDER BY created_at DESC",
                    (tenant_id, org_id),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM api_keys WHERE tenant_id = ? ORDER BY created_at DESC",
                    (tenant_id,),
                ).fetchall()
            return [ApiKey.from_row(r) for r in rows]
        finally:
            con.close()

    def record_usage(self, key_id: str, endpoint: str, method: str, status_code: int) -> None:
        con = get_enterprise_conn()
        try:
            con.execute(
                "INSERT INTO api_key_usage (key_id, endpoint, method, status_code) VALUES (?, ?, ?, ?)",
                (key_id, endpoint, method, status_code),
            )
            con.commit()
        except Exception:
            pass
        finally:
            con.close()


api_key_service = ApiKeyService()
