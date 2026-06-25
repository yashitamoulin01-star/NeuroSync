"""Authentication domain models — User, AuthSession, Token."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class User:
    user_id:      str
    tenant_id:    str
    org_id:       Optional[str]
    email:        str
    display_name: str
    status:       str           # active | suspended | pending | deleted
    mfa_enabled:  bool
    created_at:   float
    last_login:   Optional[float] = None

    def is_active(self) -> bool:
        return self.status == "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id":      self.user_id,
            "tenant_id":    self.tenant_id,
            "org_id":       self.org_id,
            "email":        self.email,
            "display_name": self.display_name,
            "status":       self.status,
            "mfa_enabled":  self.mfa_enabled,
            "created_at":   self.created_at,
            "last_login":   self.last_login,
        }

    @classmethod
    def from_row(cls, row) -> "User":
        return cls(
            user_id      = row["user_id"],
            tenant_id    = row["tenant_id"],
            org_id       = row["org_id"],
            email        = row["email"],
            display_name = row["display_name"],
            status       = row["status"],
            mfa_enabled  = bool(row["mfa_enabled"]),
            created_at   = row["created_at"],
            last_login   = row["last_login"],
        )


@dataclass
class AuthSession:
    session_token: str
    user_id:       str
    tenant_id:     str
    created_at:    float
    expires_at:    float
    ip_address:    str
    revoked:       bool

    def is_valid(self) -> bool:
        import time
        return not self.revoked and time.time() < self.expires_at


@dataclass
class TokenPair:
    access_token:  str
    refresh_token: str
    token_type:    str = "Bearer"
    expires_in:    int = 3600

    def to_dict(self) -> Dict:
        return {
            "access_token":  self.access_token,
            "refresh_token": self.refresh_token,
            "token_type":    self.token_type,
            "expires_in":    self.expires_in,
        }
