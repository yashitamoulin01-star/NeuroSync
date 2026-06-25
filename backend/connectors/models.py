"""
Normalized connector types — the only shapes that escape the provider edge.

Nothing provider-specific (API payloads, vendor field names) is allowed past
this module. The service, router, UI, and AI consume these types exclusively.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ConnectorProvider(str, Enum):
    GOOGLE_MEET       = "google_meet"
    MICROSOFT_TEAMS   = "microsoft_teams"
    ZOOM              = "zoom"
    WEBEX             = "webex"
    SLACK             = "slack"
    GOOGLE_CALENDAR   = "google_calendar"
    MICROSOFT_CALENDAR = "microsoft_calendar"


class ConnectorStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED    = "connected"
    EXPIRED      = "expired"
    ERROR        = "error"


@dataclass(frozen=True)
class ConnectorCapabilities:
    """What a connector can actually deliver. The UI/scheduler never offers more."""
    meeting_metadata:    bool = True
    transcript_support:  bool = False
    recording_support:   bool = False
    live_stream_support: bool = False
    participant_metadata: bool = False

    def to_dict(self) -> dict:
        return {
            "meeting_metadata":     self.meeting_metadata,
            "transcript_support":   self.transcript_support,
            "recording_support":    self.recording_support,
            "live_stream_support":  self.live_stream_support,
            "participant_metadata": self.participant_metadata,
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "ConnectorCapabilities":
        d = d or {}
        return cls(
            meeting_metadata     = d.get("meeting_metadata", True),
            transcript_support   = d.get("transcript_support", False),
            recording_support    = d.get("recording_support", False),
            live_stream_support  = d.get("live_stream_support", False),
            participant_metadata = d.get("participant_metadata", False),
        )


@dataclass(frozen=True)
class OAuthConfig:
    """Per-provider OAuth 2.0 endpoints and default scopes."""
    authorize_url: str
    token_url:     str
    scopes:        List[str]
    revoke_url:    Optional[str] = None


@dataclass
class TokenBundle:
    """Normalized result of an authorization-code exchange or refresh."""
    access_token:  str
    refresh_token: Optional[str]
    expires_at:    Optional[float]    # epoch seconds
    scopes:        List[str] = field(default_factory=list)


@dataclass
class MeetingRef:
    """A scheduled meeting surfaced by a connector (drives 'Upcoming Interviews')."""
    external_id: str
    title:       str
    start_time:  float               # epoch seconds
    join_url:    Optional[str] = None
    participants: int = 0
    platform:    Optional[str] = None  # detected meeting platform (google_meet, zoom, ...)

    def to_dict(self) -> dict:
        return {
            "external_id":  self.external_id,
            "title":        self.title,
            "start_time":   self.start_time,
            "join_url":     self.join_url,
            "participants": self.participants,
            "platform":     self.platform,
        }


@dataclass
class ConnectorTestResult:
    ok:       bool
    message:  str
    latency_ms: Optional[float] = None

    def to_dict(self) -> dict:
        return {"ok": self.ok, "message": self.message, "latency_ms": self.latency_ms}


@dataclass
class ConnectorRecord:
    """DB-backed connector connection. Token columns NEVER appear in public output."""
    connector_id:      str
    tenant_id:         str
    org_id:            Optional[str]
    provider:          str
    name:              str
    status:            str
    token_expires_at:  Optional[float]
    scopes:            List[str]
    capabilities:      ConnectorCapabilities
    last_sync:         Optional[float]
    last_error:        Optional[str]
    created_by:        str
    created_at:        float
    updated_at:        float

    def is_expired(self) -> bool:
        return bool(self.token_expires_at and time.time() > self.token_expires_at)

    def to_public_dict(self) -> dict:
        """Safe for API responses — no token material, ever."""
        status = self.status
        if status == ConnectorStatus.CONNECTED.value and self.is_expired():
            status = ConnectorStatus.EXPIRED.value
        return {
            "connector_id":     self.connector_id,
            "provider":         self.provider,
            "name":             self.name,
            "status":           status,
            "token_expires_at": self.token_expires_at,
            "scopes":           self.scopes,
            "capabilities":     self.capabilities.to_dict(),
            "last_sync":        self.last_sync,
            "last_error":       self.last_error,
            "created_by":       self.created_by,
            "created_at":       self.created_at,
            "updated_at":       self.updated_at,
        }

    @classmethod
    def from_row(cls, row) -> "ConnectorRecord":
        return cls(
            connector_id     = row["connector_id"],
            tenant_id        = row["tenant_id"],
            org_id           = row["org_id"],
            provider         = row["provider"],
            name             = row["name"],
            status           = row["status"],
            token_expires_at = row["token_expires_at"],
            scopes           = json.loads(row["scopes_json"] or "[]"),
            capabilities     = ConnectorCapabilities.from_dict(
                json.loads(row["capabilities_json"] or "{}")
            ),
            last_sync        = row["last_sync"],
            last_error       = row["last_error"],
            created_by       = row["created_by"],
            created_at       = row["created_at"],
            updated_at       = row["updated_at"],
        )
