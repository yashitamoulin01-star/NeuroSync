"""
Organization service — multi-tenant organization management.

Each organization belongs to exactly one tenant.
Tenant boundary is enforced on every query via tenant_id scoping.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import List, Optional

from backend.services.enterprise_db import get_enterprise_conn
from backend.organizations.models import Department, OrgBranding, OrgConfig, Organization, Team

logger = logging.getLogger("neurosync.organizations")


class OrganizationService:
    # ── Organizations ─────────────────────────────────────────────────────────

    def get(self, tenant_id: str, org_id: str) -> Optional[Organization]:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM organizations WHERE org_id = ? AND tenant_id = ?",
                (org_id, tenant_id),
            ).fetchone()
            return Organization.from_row(row) if row else None
        finally:
            con.close()

    def list_for_tenant(self, tenant_id: str) -> List[Organization]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM organizations WHERE tenant_id = ? ORDER BY name",
                (tenant_id,),
            ).fetchall()
            return [Organization.from_row(r) for r in rows]
        finally:
            con.close()

    def create(
        self,
        tenant_id: str,
        name: str,
        slug: str,
        branding: Optional[OrgBranding] = None,
        config: Optional[OrgConfig] = None,
        retention_days: int = 365,
    ) -> Organization:
        org_id     = f"org_{uuid.uuid4().hex[:12]}"
        created_at = time.time()
        br         = branding or OrgBranding(company_name=name)
        cfg        = config or OrgConfig()
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO organizations
                  (org_id, tenant_id, name, slug, branding_json, config_json, retention_days, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (org_id, tenant_id, name, slug,
                 json.dumps(br.to_dict()), json.dumps(cfg.to_dict()),
                 retention_days, created_at),
            )
            con.commit()
            logger.info("Organization created: %s (%s) tenant=%s", name, org_id, tenant_id)
            return Organization(
                org_id=org_id, tenant_id=tenant_id, name=name, slug=slug,
                branding=br, config=cfg, retention_days=retention_days, created_at=created_at,
            )
        finally:
            con.close()

    def update_config(self, tenant_id: str, org_id: str, config: OrgConfig) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE organizations SET config_json = ? WHERE org_id = ? AND tenant_id = ?",
                (json.dumps(config.to_dict()), org_id, tenant_id),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    def update_branding(self, tenant_id: str, org_id: str, branding: OrgBranding) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE organizations SET branding_json = ? WHERE org_id = ? AND tenant_id = ?",
                (json.dumps(branding.to_dict()), org_id, tenant_id),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    def assert_exists(self, tenant_id: str, org_id: str) -> Organization:
        org = self.get(tenant_id, org_id)
        if org is None:
            raise LookupError(f"Organization {org_id} not found in tenant {tenant_id}")
        return org

    # ── Departments ───────────────────────────────────────────────────────────

    def create_department(self, tenant_id: str, org_id: str, name: str) -> Department:
        dept_id    = f"dept_{uuid.uuid4().hex[:10]}"
        created_at = time.time()
        con = get_enterprise_conn()
        try:
            con.execute(
                "INSERT INTO departments (dept_id, org_id, tenant_id, name, created_at) VALUES (?, ?, ?, ?, ?)",
                (dept_id, org_id, tenant_id, name, created_at),
            )
            con.commit()
            return Department(dept_id=dept_id, org_id=org_id, tenant_id=tenant_id,
                              name=name, created_at=created_at)
        finally:
            con.close()

    def list_departments(self, tenant_id: str, org_id: str) -> List[Department]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM departments WHERE org_id = ? AND tenant_id = ? ORDER BY name",
                (org_id, tenant_id),
            ).fetchall()
            return [
                Department(dept_id=r["dept_id"], org_id=r["org_id"], tenant_id=r["tenant_id"],
                           name=r["name"], created_at=r["created_at"])
                for r in rows
            ]
        finally:
            con.close()

    # ── Teams ─────────────────────────────────────────────────────────────────

    def create_team(
        self, tenant_id: str, org_id: str, name: str, dept_id: Optional[str] = None
    ) -> Team:
        team_id    = f"team_{uuid.uuid4().hex[:10]}"
        created_at = time.time()
        con = get_enterprise_conn()
        try:
            con.execute(
                "INSERT INTO teams (team_id, dept_id, org_id, tenant_id, name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (team_id, dept_id, org_id, tenant_id, name, created_at),
            )
            con.commit()
            return Team(team_id=team_id, dept_id=dept_id, org_id=org_id, tenant_id=tenant_id,
                        name=name, created_at=created_at)
        finally:
            con.close()

    def list_teams(self, tenant_id: str, org_id: str) -> List[Team]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM teams WHERE org_id = ? AND tenant_id = ? ORDER BY name",
                (org_id, tenant_id),
            ).fetchall()
            return [
                Team(team_id=r["team_id"], dept_id=r["dept_id"], org_id=r["org_id"],
                     tenant_id=r["tenant_id"], name=r["name"], created_at=r["created_at"])
                for r in rows
            ]
        finally:
            con.close()

    # ── Summary ───────────────────────────────────────────────────────────────

    def summary(self, tenant_id: str, org_id: str) -> dict:
        con = get_enterprise_conn()
        try:
            users = con.execute(
                "SELECT COUNT(*) FROM users WHERE org_id = ? AND tenant_id = ? AND status = 'active'",
                (org_id, tenant_id),
            ).fetchone()[0]
            depts = con.execute(
                "SELECT COUNT(*) FROM departments WHERE org_id = ? AND tenant_id = ?",
                (org_id, tenant_id),
            ).fetchone()[0]
            teams = con.execute(
                "SELECT COUNT(*) FROM teams WHERE org_id = ? AND tenant_id = ?",
                (org_id, tenant_id),
            ).fetchone()[0]
            return {"org_id": org_id, "active_users": users, "departments": depts, "teams": teams}
        finally:
            con.close()


org_service = OrganizationService()
