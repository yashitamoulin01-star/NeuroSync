"""Compliance domain models — retention policies, consent, data requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class RetentionPolicy:
    policy_id:     str
    org_id:        str
    tenant_id:     str
    name:          str
    resource_type: str   # sessions | reports | evidence | audit_events | candidates
    retain_days:   int
    action_after:  str   # soft_delete | hard_delete | archive
    enabled:       bool
    created_at:    float

    def to_dict(self) -> Dict:
        return self.__dict__.copy()

    @classmethod
    def from_row(cls, row) -> "RetentionPolicy":
        return cls(
            policy_id     = row["policy_id"],
            org_id        = row["org_id"],
            tenant_id     = row["tenant_id"],
            name          = row["name"],
            resource_type = row["resource_type"],
            retain_days   = row["retain_days"],
            action_after  = row["action_after"],
            enabled       = bool(row["enabled"]),
            created_at    = row["created_at"],
        )


@dataclass
class ConsentRecord:
    consent_id: str
    tenant_id:  str
    subject_id: str
    purpose:    str    # analytics | recording | ai_processing | profiling
    granted:    bool
    granted_at: float
    expires_at: Optional[float]
    ip_address: Optional[str]
    version:    str

    def is_active(self) -> bool:
        import time
        if not self.granted:
            return False
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True

    def to_dict(self) -> Dict:
        return self.__dict__.copy()

    @classmethod
    def from_row(cls, row) -> "ConsentRecord":
        return cls(
            consent_id = row["consent_id"],
            tenant_id  = row["tenant_id"],
            subject_id = row["subject_id"],
            purpose    = row["purpose"],
            granted    = bool(row["granted"]),
            granted_at = row["granted_at"],
            expires_at = row["expires_at"],
            ip_address = row["ip_address"],
            version    = row["version"],
        )


@dataclass
class DataRequest:
    request_id:    str
    tenant_id:     str
    subject_id:    str
    request_type:  str    # export | erasure | portability | rectification
    status:        str    # pending | processing | completed | rejected
    requested_at:  float
    completed_at:  Optional[float]
    result_path:   Optional[str]
    notes:         Optional[str]

    def to_dict(self) -> Dict:
        return self.__dict__.copy()

    @classmethod
    def from_row(cls, row) -> "DataRequest":
        return cls(
            request_id   = row["request_id"],
            tenant_id    = row["tenant_id"],
            subject_id   = row["subject_id"],
            request_type = row["request_type"],
            status       = row["status"],
            requested_at = row["requested_at"],
            completed_at = row["completed_at"],
            result_path  = row["result_path"],
            notes        = row["notes"],
        )
