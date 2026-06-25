"""
Administrative console — platform-level operations.

Used by platform administrators to manage:
  - Tenants and organizations
  - User management across tenants
  - Feature flags
  - Platform metrics
  - System configuration
  - Deployment status

This is the operational control center. All operations here are
automatically recorded in the audit log.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("neurosync.admin")


class AdminConsole:
    # ── Tenant Operations ─────────────────────────────────────────────────────

    def list_tenants(self, status: Optional[str] = None) -> List[Dict]:
        from backend.tenants.service import tenant_service
        tenants = tenant_service.list_all(status=status)
        result  = []
        for t in tenants:
            stats = tenant_service.stats(t.tenant_id)
            d = t.to_dict()
            d["stats"] = stats
            result.append(d)
        return result

    def create_tenant(
        self,
        name:       str,
        slug:       str,
        plan:       str,
        admin_id:   str,
    ) -> Dict:
        from backend.tenants.service import tenant_service
        from backend.billing.service import billing_service
        from backend.audit_center.service import audit_service

        tenant = tenant_service.create(name=name, slug=slug, plan=plan)
        billing_service.upsert_plan(tenant.tenant_id, plan)
        audit_service.log(
            tenant_id     = tenant.tenant_id,
            actor_id      = admin_id,
            action        = "org.created",
            resource_type = "tenant",
            resource_id   = tenant.tenant_id,
            actor_role    = "platform_admin",
        )
        logger.info("Admin created tenant: %s plan=%s by %s", name, plan, admin_id)
        return tenant.to_dict()

    def suspend_tenant(self, tenant_id: str, admin_id: str, reason: str = "") -> bool:
        from backend.tenants.service import tenant_service
        from backend.audit_center.service import audit_service

        ok = tenant_service.update_status(tenant_id, "suspended", actor_id=admin_id)
        if ok:
            audit_service.log(
                tenant_id     = tenant_id,
                actor_id      = admin_id,
                action        = "org.updated",
                resource_type = "tenant",
                resource_id   = tenant_id,
                actor_role    = "platform_admin",
                metadata      = {"reason": reason, "new_status": "suspended"},
            )
        return ok

    # ── Feature Flag Management ───────────────────────────────────────────────

    def list_flags(self) -> List[Dict]:
        from backend.feature_flags.service import feature_flag_service
        return [f.to_dict() for f in feature_flag_service.list_all()]

    def toggle_flag(
        self, name: str, enabled: bool, admin_id: str
    ) -> bool:
        from backend.feature_flags.service import feature_flag_service
        from backend.audit_center.service import audit_service

        ok = feature_flag_service.set_enabled(name, enabled, admin_id)
        if ok:
            audit_service.log(
                tenant_id     = "platform",
                actor_id      = admin_id,
                action        = "flag.toggled",
                resource_type = "feature_flag",
                resource_id   = name,
                actor_role    = "platform_admin",
                metadata      = {"enabled": enabled},
            )
        return ok

    def set_flag_rollout(self, name: str, pct: int, admin_id: str) -> bool:
        from backend.feature_flags.service import feature_flag_service
        return feature_flag_service.set_rollout(name, pct, admin_id)

    # ── Platform Metrics ──────────────────────────────────────────────────────

    def platform_metrics(self) -> Dict[str, Any]:
        from backend.services.enterprise_db import get_enterprise_conn
        con = get_enterprise_conn()
        try:
            total_tenants = con.execute(
                "SELECT COUNT(*) FROM tenants WHERE status = 'active'"
            ).fetchone()[0]
            total_orgs = con.execute(
                "SELECT COUNT(*) FROM organizations"
            ).fetchone()[0]
            total_users = con.execute(
                "SELECT COUNT(*) FROM users WHERE status = 'active'"
            ).fetchone()[0]
            total_sessions = con.execute(
                "SELECT COUNT(*) FROM sessions"
            ).fetchone()[0]
            total_api_keys = con.execute(
                "SELECT COUNT(*) FROM api_keys WHERE status = 'active'"
            ).fetchone()[0]
            pending_requests = con.execute(
                "SELECT COUNT(*) FROM data_requests WHERE status = 'pending'"
            ).fetchone()[0]
        finally:
            con.close()

        return {
            "generated_at":       time.time(),
            "active_tenants":     total_tenants,
            "organizations":      total_orgs,
            "active_users":       total_users,
            "total_sessions":     total_sessions,
            "active_api_keys":    total_api_keys,
            "pending_data_requests": pending_requests,
        }

    # ── System Configuration ──────────────────────────────────────────────────

    def get_system_config(self) -> Dict:
        from backend.core.config import settings
        return {
            "app_name":       settings.APP_NAME,
            "app_version":    settings.APP_VERSION,
            "debug":          settings.DEBUG,
            "whisper_model":  settings.WHISPER_MODEL,
            "whisper_device": settings.WHISPER_DEVICE,
            "dataset_dir":    settings.DATASET_DIR,
        }

    # ── Deployment Status ─────────────────────────────────────────────────────

    def deployment_status(self) -> Dict:
        from backend.monitoring.metrics import registry
        from backend.health.checker import health_checker
        from backend.monitoring.alerts import alert_manager

        health = health_checker.check_all()
        alerts = alert_manager.evaluate()

        return {
            "status":        health.status,
            "health_summary": health.summary,
            "firing_alerts": alerts.firing,
            "healthy":       alerts.healthy,
            "generated_at":  time.time(),
        }

    # ── User Search ───────────────────────────────────────────────────────────

    def search_users(self, email_query: str, tenant_id: Optional[str] = None) -> List[Dict]:
        from backend.services.enterprise_db import get_enterprise_conn
        con = get_enterprise_conn()
        try:
            if tenant_id:
                rows = con.execute(
                    "SELECT user_id, tenant_id, org_id, email, display_name, status, created_at, last_login FROM users WHERE tenant_id = ? AND email LIKE ? AND status != 'deleted' ORDER BY created_at DESC LIMIT 50",
                    (tenant_id, f"%{email_query}%"),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT user_id, tenant_id, org_id, email, display_name, status, created_at, last_login FROM users WHERE email LIKE ? AND status != 'deleted' ORDER BY created_at DESC LIMIT 50",
                    (f"%{email_query}%",),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


admin_console = AdminConsole()
