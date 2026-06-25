"""
Centralized permission evaluator.

Every permission check in the platform MUST go through this module.
No ad-hoc role or permission checks elsewhere.

Evaluation order:
  1. Hard deny overrides  (permission_overrides.granted = 0)
  2. Hard grant overrides (permission_overrides.granted = 1)
  3. Role-based permissions (union of all user roles)

Platform admins bypass all checks — they implicitly have every permission.
"""

from __future__ import annotations

import logging
from typing import FrozenSet, List, Set

from backend.services.enterprise_db import get_enterprise_conn
from backend.rbac.roles import ROLE_PERMISSIONS, permissions_for_role

logger = logging.getLogger("neurosync.rbac")


class PermissionEvaluator:
    def get_user_roles(self, user_id: str, tenant_id: str) -> List[str]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                """
                SELECT role FROM role_assignments
                WHERE user_id = ? AND tenant_id = ?
                  AND (expires_at IS NULL OR expires_at > unixepoch())
                """,
                (user_id, tenant_id),
            ).fetchall()
            return [r["role"] for r in rows]
        finally:
            con.close()

    def get_user_permissions(self, user_id: str, tenant_id: str) -> Set[str]:
        roles = self.get_user_roles(user_id, tenant_id)
        # Platform admins have all permissions
        if "platform_admin" in roles:
            all_perms: Set[str] = set()
            for perms in ROLE_PERMISSIONS.values():
                all_perms |= perms
            return all_perms

        # Union of role permissions
        effective: Set[str] = set()
        for role in roles:
            effective |= permissions_for_role(role)

        # Apply overrides
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT permission, granted FROM permission_overrides WHERE user_id = ? AND tenant_id = ?",
                (user_id, tenant_id),
            ).fetchall()
            for row in rows:
                if row["granted"]:
                    effective.add(row["permission"])
                else:
                    effective.discard(row["permission"])
        finally:
            con.close()

        return effective

    def has_permission(self, user_id: str, tenant_id: str, permission: str) -> bool:
        return permission in self.get_user_permissions(user_id, tenant_id)

    def has_any_permission(self, user_id: str, tenant_id: str, *permissions: str) -> bool:
        effective = self.get_user_permissions(user_id, tenant_id)
        return any(p in effective for p in permissions)

    def has_all_permissions(self, user_id: str, tenant_id: str, *permissions: str) -> bool:
        effective = self.get_user_permissions(user_id, tenant_id)
        return all(p in effective for p in permissions)

    def assign_role(
        self,
        user_id:    str,
        tenant_id:  str,
        role:       str,
        granted_by: str,
        org_id:     str = None,
        expires_at: float = None,
    ) -> str:
        import uuid, time
        if role not in ROLE_PERMISSIONS:
            raise ValueError(f"Unknown role: {role}")
        assignment_id = f"ra_{uuid.uuid4().hex[:10]}"
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT OR REPLACE INTO role_assignments
                  (assignment_id, user_id, tenant_id, org_id, role, granted_by, granted_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (assignment_id, user_id, tenant_id, org_id, role,
                 granted_by, time.time(), expires_at),
            )
            con.commit()
            logger.info("Role %s assigned to %s by %s", role, user_id, granted_by)
            return assignment_id
        finally:
            con.close()

    def revoke_role(self, user_id: str, tenant_id: str, role: str) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "DELETE FROM role_assignments WHERE user_id = ? AND tenant_id = ? AND role = ?",
                (user_id, tenant_id, role),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    def set_permission_override(
        self,
        user_id:    str,
        tenant_id:  str,
        permission: str,
        granted:    bool,
        granted_by: str,
    ) -> None:
        import uuid, time
        override_id = f"po_{uuid.uuid4().hex[:10]}"
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT OR REPLACE INTO permission_overrides
                  (override_id, user_id, tenant_id, permission, granted, granted_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (override_id, user_id, tenant_id, permission, 1 if granted else 0,
                 granted_by, time.time()),
            )
            con.commit()
        finally:
            con.close()

    def get_permission_matrix(self, user_id: str, tenant_id: str) -> dict:
        roles  = self.get_user_roles(user_id, tenant_id)
        perms  = self.get_user_permissions(user_id, tenant_id)
        return {
            "user_id":     user_id,
            "tenant_id":   tenant_id,
            "roles":       roles,
            "permissions": sorted(perms),
        }


permission_evaluator = PermissionEvaluator()
