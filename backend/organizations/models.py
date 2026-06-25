"""Organization, Department, Team models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OrgBranding:
    logo_url:     Optional[str] = None
    primary_color: str = "#6366F1"
    company_name: str = ""

    def to_dict(self) -> Dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: Dict) -> "OrgBranding":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class OrgConfig:
    default_template_id:  Optional[str] = None
    ai_model_policy:      str = "latest"          # latest | pinned | reviewed_only
    require_report_approval: bool = False
    allow_candidate_portal:  bool = True
    allow_data_export:       bool = True
    session_timeout_minutes: int  = 480
    evidence_retention_days: int  = 365

    def to_dict(self) -> Dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: Dict) -> "OrgConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Organization:
    org_id:         str
    tenant_id:      str
    name:           str
    slug:           str
    branding:       OrgBranding = field(default_factory=OrgBranding)
    config:         OrgConfig   = field(default_factory=OrgConfig)
    retention_days: int         = 365
    created_at:     float       = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "org_id":         self.org_id,
            "tenant_id":      self.tenant_id,
            "name":           self.name,
            "slug":           self.slug,
            "branding":       self.branding.to_dict(),
            "config":         self.config.to_dict(),
            "retention_days": self.retention_days,
            "created_at":     self.created_at,
        }

    @classmethod
    def from_row(cls, row) -> "Organization":
        return cls(
            org_id         = row["org_id"],
            tenant_id      = row["tenant_id"],
            name           = row["name"],
            slug           = row["slug"],
            branding       = OrgBranding.from_dict(json.loads(row["branding_json"] or "{}")),
            config         = OrgConfig.from_dict(json.loads(row["config_json"] or "{}")),
            retention_days = row["retention_days"],
            created_at     = row["created_at"],
        )


@dataclass
class Department:
    dept_id:    str
    org_id:     str
    tenant_id:  str
    name:       str
    created_at: float

    def to_dict(self) -> Dict:
        return self.__dict__.copy()


@dataclass
class Team:
    team_id:    str
    dept_id:    Optional[str]
    org_id:     str
    tenant_id:  str
    name:       str
    created_at: float

    def to_dict(self) -> Dict:
        return self.__dict__.copy()
