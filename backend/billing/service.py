"""
Billing service — subscription plans, usage tracking, quota enforcement.

No payment integration. Only architecture:
  - Subscription plan tiers
  - Usage recording per metric
  - Quota limit checks
  - Monthly usage aggregation
  - Overage detection

This supports a SaaS billing integration in a future phase (Stripe, etc.).
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.billing")


@dataclass
class SubscriptionPlan:
    plan_id:         str
    tenant_id:       str
    plan_name:       str
    seat_limit:      int
    interview_limit: int
    storage_gb:      int
    api_calls_month: int
    valid_from:      float
    valid_until:     Optional[float]

    def to_dict(self) -> Dict:
        return self.__dict__.copy()

    @classmethod
    def from_row(cls, row) -> "SubscriptionPlan":
        return cls(
            plan_id         = row["plan_id"],
            tenant_id       = row["tenant_id"],
            plan_name       = row["plan_name"],
            seat_limit      = row["seat_limit"],
            interview_limit = row["interview_limit"],
            storage_gb      = row["storage_gb"],
            api_calls_month = row["api_calls_month"],
            valid_from      = row["valid_from"],
            valid_until     = row["valid_until"],
        )


_PLAN_DEFAULTS = {
    "free":         {"seat_limit": 3,   "interview_limit": 50,   "storage_gb": 1,   "api_calls_month": 1000},
    "professional": {"seat_limit": 25,  "interview_limit": 500,  "storage_gb": 25,  "api_calls_month": 25000},
    "enterprise":   {"seat_limit": 500, "interview_limit": 10000, "storage_gb": 500, "api_calls_month": 500000},
}


class BillingService:
    def upsert_plan(self, tenant_id: str, plan_name: str) -> SubscriptionPlan:
        defaults  = _PLAN_DEFAULTS.get(plan_name, _PLAN_DEFAULTS["professional"])
        plan_id   = f"sp_{uuid.uuid4().hex[:10]}"
        valid_from = time.time()
        con = get_enterprise_conn()
        try:
            existing = con.execute(
                "SELECT * FROM subscription_plans WHERE tenant_id = ?", (tenant_id,)
            ).fetchone()
            if existing:
                con.execute(
                    "UPDATE subscription_plans SET plan_name=?, seat_limit=?, interview_limit=?, storage_gb=?, api_calls_month=?, valid_from=?, valid_until=NULL WHERE tenant_id=?",
                    (plan_name, defaults["seat_limit"], defaults["interview_limit"],
                     defaults["storage_gb"], defaults["api_calls_month"], valid_from, tenant_id),
                )
                plan_id = existing["plan_id"]
            else:
                con.execute(
                    "INSERT INTO subscription_plans (plan_id, tenant_id, plan_name, seat_limit, interview_limit, storage_gb, api_calls_month, valid_from) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (plan_id, tenant_id, plan_name, defaults["seat_limit"],
                     defaults["interview_limit"], defaults["storage_gb"],
                     defaults["api_calls_month"], valid_from),
                )
            con.commit()
        finally:
            con.close()
        return SubscriptionPlan(
            plan_id=plan_id, tenant_id=tenant_id, plan_name=plan_name,
            seat_limit=defaults["seat_limit"], interview_limit=defaults["interview_limit"],
            storage_gb=defaults["storage_gb"], api_calls_month=defaults["api_calls_month"],
            valid_from=valid_from, valid_until=None,
        )

    def get_plan(self, tenant_id: str) -> Optional[SubscriptionPlan]:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM subscription_plans WHERE tenant_id = ?", (tenant_id,)
            ).fetchone()
            return SubscriptionPlan.from_row(row) if row else None
        finally:
            con.close()

    def record_usage(
        self,
        tenant_id: str,
        metric:    str,
        quantity:  float,
        org_id:    Optional[str] = None,
    ) -> None:
        period = time.strftime("%Y-%m")
        con = get_enterprise_conn()
        try:
            existing = con.execute(
                "SELECT rowid, quantity FROM usage_records WHERE tenant_id=? AND metric=? AND period=? AND org_id IS ?",
                (tenant_id, metric, period, org_id),
            ).fetchone()
            if existing:
                con.execute(
                    "UPDATE usage_records SET quantity = quantity + ? WHERE rowid = ?",
                    (quantity, existing["rowid"]),
                )
            else:
                con.execute(
                    "INSERT INTO usage_records (tenant_id, org_id, metric, quantity, period) VALUES (?, ?, ?, ?, ?)",
                    (tenant_id, org_id, metric, quantity, period),
                )
            con.commit()
        finally:
            con.close()

    def get_usage(self, tenant_id: str, period: Optional[str] = None) -> List[Dict]:
        p = period or time.strftime("%Y-%m")
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT metric, SUM(quantity) as total FROM usage_records WHERE tenant_id=? AND period=? GROUP BY metric",
                (tenant_id, p),
            ).fetchall()
            return [{"metric": r["metric"], "quantity": r["total"], "period": p} for r in rows]
        finally:
            con.close()

    def check_quota(self, tenant_id: str, metric: str) -> Dict[str, Any]:
        plan  = self.get_plan(tenant_id)
        usage = {u["metric"]: u["quantity"] for u in self.get_usage(tenant_id)}
        limits = {
            "interviews":  plan.interview_limit if plan else 500,
            "seats":       plan.seat_limit      if plan else 25,
            "api_calls":   plan.api_calls_month if plan else 25000,
            "storage_gb":  plan.storage_gb      if plan else 25,
        }
        limit   = limits.get(metric, float("inf"))
        current = usage.get(metric, 0)
        return {
            "metric":    metric,
            "current":   current,
            "limit":     limit,
            "remaining": max(0, limit - current),
            "exceeded":  current >= limit,
            "pct_used":  round((current / limit * 100) if limit else 0, 1),
        }

    def usage_summary(self, tenant_id: str) -> Dict:
        plan = self.get_plan(tenant_id)
        return {
            "plan":   plan.to_dict() if plan else None,
            "period": time.strftime("%Y-%m"),
            "usage":  self.get_usage(tenant_id),
            "quotas": {
                m: self.check_quota(tenant_id, m)
                for m in ("interviews", "seats", "api_calls", "storage_gb")
            },
        }


billing_service = BillingService()
