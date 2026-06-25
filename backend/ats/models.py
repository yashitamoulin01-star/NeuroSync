"""Normalized ATS types."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ATSProvider(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER      = "lever"
    WORKDAY    = "workday"
    ASHBY      = "ashby"


class ATSStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED    = "connected"
    EXPIRED      = "expired"
    ERROR        = "error"


@dataclass(frozen=True)
class ATSCapabilities:
    push_report:      bool = True   # write a behavioral report onto a candidate
    write_scorecard:  bool = False  # structured scorecard fields
    sync_candidates:  bool = True   # pull candidate roster
    write_back_stage: bool = False  # advance/move pipeline stage

    def to_dict(self) -> dict:
        return {
            "push_report": self.push_report, "write_scorecard": self.write_scorecard,
            "sync_candidates": self.sync_candidates, "write_back_stage": self.write_back_stage,
        }


@dataclass
class ExportResult:
    ok:           bool
    message:      str
    external_ref: Optional[str] = None   # ATS-side id of the written record

    def to_dict(self) -> dict:
        return {"ok": self.ok, "message": self.message, "external_ref": self.external_ref}


@dataclass
class CandidateRef:
    external_id: str
    name:        str
    email:       Optional[str] = None
    stage:       Optional[str] = None

    def to_dict(self) -> dict:
        return {"external_id": self.external_id, "name": self.name, "email": self.email, "stage": self.stage}


@dataclass
class ATSConnectionRecord:
    connection_id:    str
    tenant_id:        str
    org_id:           Optional[str]
    provider:         str
    name:             str
    status:           str
    token_expires_at: Optional[float]
    capabilities:     ATSCapabilities
    last_sync:        Optional[float]
    last_error:       Optional[str]
    created_by:       str
    created_at:       float
    updated_at:       float

    def is_expired(self) -> bool:
        return bool(self.token_expires_at and time.time() > self.token_expires_at)

    def to_public_dict(self) -> dict:
        status = self.status
        if status == ATSStatus.CONNECTED.value and self.is_expired():
            status = ATSStatus.EXPIRED.value
        return {
            "connection_id":    self.connection_id,
            "provider":         self.provider,
            "name":             self.name,
            "status":           status,
            "token_expires_at": self.token_expires_at,
            "capabilities":     self.capabilities.to_dict(),
            "last_sync":        self.last_sync,
            "last_error":       self.last_error,
            "created_by":       self.created_by,
            "created_at":       self.created_at,
            "updated_at":       self.updated_at,
        }

    @classmethod
    def from_row(cls, row) -> "ATSConnectionRecord":
        return cls(
            connection_id=row["connection_id"], tenant_id=row["tenant_id"], org_id=row["org_id"],
            provider=row["provider"], name=row["name"], status=row["status"],
            token_expires_at=row["token_expires_at"],
            capabilities=ATSCapabilities(**(json.loads(row["capabilities_json"] or "{}") or {})),
            last_sync=row["last_sync"], last_error=row["last_error"],
            created_by=row["created_by"], created_at=row["created_at"], updated_at=row["updated_at"],
        )
