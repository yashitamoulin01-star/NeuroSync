"""
Tenant service — create, retrieve, update, suspend tenants.

Tenants are the outermost isolation boundary. No cross-tenant data access
is permitted at any layer. The service enforces slug uniqueness and status
transitions.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import List, Optional

from backend.services.enterprise_db import get_enterprise_conn
from backend.tenants.models import Tenant, TenantConfig

logger = logging.getLogger("neurosync.tenants")


class TenantService:
    # ── Queries ───────────────────────────────────────────────────────────────

    def get(self, tenant_id: str) -> Optional[Tenant]:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM tenants WHERE tenant_id = ?", (tenant_id,)
            ).fetchone()
            return Tenant.from_row(row) if row else None
        finally:
            con.close()

    def get_by_slug(self, slug: str) -> Optional[Tenant]:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM tenants WHERE slug = ?", (slug,)
            ).fetchone()
            return Tenant.from_row(row) if row else None
        finally:
            con.close()

    def list_all(self, status: Optional[str] = None) -> List[Tenant]:
        con = get_enterprise_conn()
        try:
            if status:
                rows = con.execute(
                    "SELECT * FROM tenants WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM tenants ORDER BY created_at DESC"
                ).fetchall()
            return [Tenant.from_row(r) for r in rows]
        finally:
            con.close()

    # ── Mutations ─────────────────────────────────────────────────────────────

    def create(
        self,
        name: str,
        slug: str,
        plan: str = "professional",
        config: Optional[TenantConfig] = None,
    ) -> Tenant:
        tenant_id  = f"ten_{uuid.uuid4().hex[:12]}"
        created_at = time.time()
        cfg        = config or TenantConfig()
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO tenants (tenant_id, name, slug, plan, created_at, config_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (tenant_id, name, slug, plan, created_at, json.dumps(cfg.to_dict())),
            )
            con.commit()
            logger.info("Tenant created: %s (%s) plan=%s", name, tenant_id, plan)
            return Tenant(
                tenant_id  = tenant_id,
                name       = name,
                slug       = slug,
                status     = "active",
                plan       = plan,
                created_at = created_at,
                config     = cfg,
            )
        finally:
            con.close()

    def update_status(self, tenant_id: str, status: str, actor_id: str = "system") -> bool:
        allowed = {"active", "suspended", "deleted"}
        if status not in allowed:
            raise ValueError(f"Invalid status: {status}. Must be one of {allowed}")
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE tenants SET status = ? WHERE tenant_id = ?",
                (status, tenant_id),
            )
            con.commit()
            changed = cur.rowcount > 0
            if changed:
                logger.warning("Tenant %s status → %s by %s", tenant_id, status, actor_id)
            return changed
        finally:
            con.close()

    def update_config(self, tenant_id: str, config: TenantConfig) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE tenants SET config_json = ? WHERE tenant_id = ?",
                (json.dumps(config.to_dict()), tenant_id),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    def update_plan(self, tenant_id: str, plan: str) -> bool:
        allowed = {"free", "professional", "enterprise"}
        if plan not in allowed:
            raise ValueError(f"Invalid plan: {plan}")
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE tenants SET plan = ? WHERE tenant_id = ?",
                (plan, tenant_id),
            )
            con.commit()
            if cur.rowcount:
                logger.info("Tenant %s plan → %s", tenant_id, plan)
            return cur.rowcount > 0
        finally:
            con.close()

    def assert_active(self, tenant_id: str) -> Tenant:
        """Load tenant and raise if not active. Use at every API boundary."""
        tenant = self.get(tenant_id)
        if tenant is None:
            raise LookupError(f"Tenant not found: {tenant_id}")
        if not tenant.is_active():
            raise PermissionError(f"Tenant {tenant_id} is {tenant.status}")
        return tenant

    # ── Statistics ────────────────────────────────────────────────────────────

    def stats(self, tenant_id: str) -> dict:
        con = get_enterprise_conn()
        try:
            orgs = con.execute(
                "SELECT COUNT(*) FROM organizations WHERE tenant_id = ?", (tenant_id,)
            ).fetchone()[0]
            users = con.execute(
                "SELECT COUNT(*) FROM users WHERE tenant_id = ? AND status = 'active'",
                (tenant_id,),
            ).fetchone()[0]
            return {"tenant_id": tenant_id, "organizations": orgs, "active_users": users}
        finally:
            con.close()


tenant_service = TenantService()
