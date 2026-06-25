"""Tenant domain model — top-level isolation boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TenantConfig:
    max_orgs:          int   = 5
    max_users:         int   = 100
    max_sessions:      int   = 1000
    retention_days:    int   = 365
    mfa_required:      bool  = False
    sso_enabled:       bool  = False
    audit_level:       str   = "standard"     # minimal | standard | verbose
    custom_branding:   bool  = True
    api_access:        bool  = True

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: Dict) -> "TenantConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Tenant:
    tenant_id:  str
    name:       str
    slug:       str
    status:     str            # active | suspended | deleted
    plan:       str            # free | professional | enterprise
    created_at: float
    config:     TenantConfig = field(default_factory=TenantConfig)

    def is_active(self) -> bool:
        return self.status == "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id":  self.tenant_id,
            "name":       self.name,
            "slug":       self.slug,
            "status":     self.status,
            "plan":       self.plan,
            "created_at": self.created_at,
            "config":     self.config.to_dict(),
        }

    @classmethod
    def from_row(cls, row) -> "Tenant":
        import json
        cfg = json.loads(row["config_json"] or "{}")
        return cls(
            tenant_id  = row["tenant_id"],
            name       = row["name"],
            slug       = row["slug"],
            status     = row["status"],
            plan       = row["plan"],
            created_at = row["created_at"],
            config     = TenantConfig.from_dict(cfg),
        )
