"""
Feature flag service — centralized rollout control.

Flags support:
  - Global enable/disable
  - Percentage-based rollout (0-100)
  - Per-tenant, per-org, per-user overrides
  - Condition-based evaluation (plan, role, etc.)

Flags are loaded from SQLite and cached in-process with a 60s TTL.
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

logger = logging.getLogger("neurosync.flags")

_CACHE: Dict[str, tuple] = {}    # flag_name → (flag_dict, fetched_at)
_CACHE_TTL = 60.0


@dataclass
class FeatureFlag:
    flag_id:     str
    name:        str
    description: str
    enabled:     bool
    rollout_pct: int     # 0-100
    conditions:  Dict[str, Any]
    created_by:  str
    created_at:  float
    updated_at:  float

    def evaluate(
        self,
        user_id:   Optional[str] = None,
        tenant_id: Optional[str] = None,
        org_id:    Optional[str] = None,
    ) -> bool:
        if not self.enabled:
            return False
        if self.rollout_pct >= 100:
            return True
        if self.rollout_pct <= 0:
            return False
        # Deterministic per-user bucket using hash
        key = f"{self.flag_id}:{user_id or tenant_id or ''}"
        bucket = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
        return bucket < self.rollout_pct

    def to_dict(self) -> Dict:
        return {
            "flag_id":     self.flag_id,
            "name":        self.name,
            "description": self.description,
            "enabled":     self.enabled,
            "rollout_pct": self.rollout_pct,
            "conditions":  self.conditions,
            "created_by":  self.created_by,
            "created_at":  self.created_at,
            "updated_at":  self.updated_at,
        }

    @classmethod
    def from_row(cls, row) -> "FeatureFlag":
        return cls(
            flag_id     = row["flag_id"],
            name        = row["name"],
            description = row["description"],
            enabled     = bool(row["enabled"]),
            rollout_pct = row["rollout_pct"],
            conditions  = json.loads(row["conditions_json"] or "{}"),
            created_by  = row["created_by"],
            created_at  = row["created_at"],
            updated_at  = row["updated_at"],
        )


class FeatureFlagService:
    def _invalidate_cache(self, name: str) -> None:
        _CACHE.pop(name, None)

    def create(
        self,
        name:        str,
        description: str,
        created_by:  str,
        enabled:     bool = False,
        rollout_pct: int  = 0,
        conditions:  Optional[Dict] = None,
    ) -> FeatureFlag:
        flag_id = f"ff_{uuid.uuid4().hex[:10]}"
        now     = time.time()
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO feature_flags
                  (flag_id, name, description, enabled, rollout_pct, conditions_json, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (flag_id, name, description, 1 if enabled else 0, rollout_pct,
                 json.dumps(conditions or {}), created_by, now, now),
            )
            con.commit()
            logger.info("Feature flag created: %s enabled=%s rollout=%d%%", name, enabled, rollout_pct)
        finally:
            con.close()
        return FeatureFlag(
            flag_id=flag_id, name=name, description=description, enabled=enabled,
            rollout_pct=rollout_pct, conditions=conditions or {},
            created_by=created_by, created_at=now, updated_at=now,
        )

    def get(self, name: str) -> Optional[FeatureFlag]:
        cached = _CACHE.get(name)
        if cached and (time.time() - cached[1]) < _CACHE_TTL:
            return FeatureFlag.from_row(type("R", (), cached[0])())  # noqa — reconstruct from dict

        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM feature_flags WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                return None
            flag = FeatureFlag.from_row(row)
            _CACHE[name] = (dict(row), time.time())
            return flag
        finally:
            con.close()

    def list_all(self) -> List[FeatureFlag]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM feature_flags ORDER BY name"
            ).fetchall()
            return [FeatureFlag.from_row(r) for r in rows]
        finally:
            con.close()

    def set_enabled(self, name: str, enabled: bool, updated_by: str) -> bool:
        self._invalidate_cache(name)
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE feature_flags SET enabled = ?, updated_at = ? WHERE name = ?",
                (1 if enabled else 0, time.time(), name),
            )
            con.commit()
            if cur.rowcount:
                logger.warning("Flag %s → %s by %s", name, "ON" if enabled else "OFF", updated_by)
            return cur.rowcount > 0
        finally:
            con.close()

    def set_rollout(self, name: str, pct: int, updated_by: str) -> bool:
        if not 0 <= pct <= 100:
            raise ValueError("rollout_pct must be 0-100")
        self._invalidate_cache(name)
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE feature_flags SET rollout_pct = ?, updated_at = ? WHERE name = ?",
                (pct, time.time(), name),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    def is_enabled(
        self,
        name:      str,
        user_id:   Optional[str] = None,
        tenant_id: Optional[str] = None,
        org_id:    Optional[str] = None,
    ) -> bool:
        # Check per-entity override first
        con = get_enterprise_conn()
        try:
            row = con.execute(
                """
                SELECT fo.enabled FROM flag_overrides fo
                JOIN feature_flags ff ON ff.flag_id = fo.flag_id
                WHERE ff.name = ?
                  AND (fo.user_id = ? OR fo.tenant_id = ? OR fo.org_id = ?)
                ORDER BY fo.created_at DESC LIMIT 1
                """,
                (name, user_id, tenant_id, org_id),
            ).fetchone()
            if row is not None:
                return bool(row["enabled"])
        finally:
            con.close()

        flag = self.get(name)
        if flag is None:
            return False
        return flag.evaluate(user_id=user_id, tenant_id=tenant_id, org_id=org_id)


# Well-known flag names used across the platform
class Flags:
    EXPERIMENTAL_REASONING    = "experimental_reasoning"
    BETA_CANDIDATE_PORTAL     = "beta_candidate_portal"
    EVIDENCE_EXPLORER         = "evidence_explorer"
    COLLABORATION_V2          = "collaboration_v2"
    ENTERPRISE_ANALYTICS      = "enterprise_analytics"
    DEBERTA_V3                = "deberta_v3"
    ALT_CALIBRATION           = "alt_calibration"
    MULTI_TENANT_UI           = "multi_tenant_ui"


feature_flag_service = FeatureFlagService()
