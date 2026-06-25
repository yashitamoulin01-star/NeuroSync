"""
BaseConnector — the pluggability contract every provider implements.

A connector translates a provider's OAuth + meeting API into the normalized
types in models.py. Nothing else about the provider escapes this edge.

First-slice connectors ship deterministic stubs for exchange_code / refresh /
test / list_upcoming_meetings that model the real flow (token shape, expiry,
capability gating) without live network calls. Wiring real HTTP is a change
inside a single provider file — the framework, service, router, and UI are
untouched.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import ClassVar, List
from urllib.parse import urlencode

from backend.connectors.models import (
    ConnectorCapabilities, ConnectorProvider, ConnectorTestResult,
    MeetingRef, OAuthConfig, TokenBundle,
)


class BaseConnector(ABC):
    # ── Identity (set by subclass) ────────────────────────────────────────────
    provider:      ClassVar[ConnectorProvider]
    display_name:  ClassVar[str]
    capabilities:  ClassVar[ConnectorCapabilities]
    oauth:         ClassVar[OAuthConfig]

    # ── OAuth ─────────────────────────────────────────────────────────────────

    def authorize_url(self, redirect_uri: str, state: str) -> str:
        """Build the provider consent URL. Same shape for all OAuth2 providers."""
        params = {
            "response_type": "code",
            "client_id":     self._client_id(),
            "redirect_uri":  redirect_uri,
            "scope":         " ".join(self.oauth.scopes),
            "state":         state,
            "access_type":   "offline",   # request a refresh token
            "prompt":        "consent",
        }
        return f"{self.oauth.authorize_url}?{urlencode(params)}"

    def _client_id(self) -> str:
        """Per-deployment OAuth client id. Stubbed until real apps are registered."""
        return f"{self.provider.value}-client-id"

    # ── Provider-specific edge (override with real HTTP when wiring live) ──────

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        """Exchange an authorization code for tokens."""

    @abstractmethod
    async def refresh(self, refresh_token: str) -> TokenBundle:
        """Refresh an expired access token."""

    async def test(self, access_token: str) -> ConnectorTestResult:
        """Lightweight reachability/permission probe. Stub: token presence."""
        if access_token:
            return ConnectorTestResult(ok=True, message=f"{self.display_name} reachable", latency_ms=0.0)
        return ConnectorTestResult(ok=False, message="No access token")

    async def list_upcoming_meetings(self, access_token: str) -> List[MeetingRef]:
        """
        Upcoming meetings for the 'Upcoming Interviews' dashboard.

        Meeting connectors (Meet/Zoom/Teams/Webex/Slack) are capture *targets*, not
        schedule sources, so they return nothing here. The recruiter's schedule
        comes from a connected calendar (see GOOGLE_CALENDAR / MICROSOFT_CALENDAR),
        which detects each event's meeting platform.
        """
        return []

    # ── Stub helpers (shared by built-in connector stubs) ─────────────────────

    def _stub_tokens(self, refresh: bool = False) -> TokenBundle:
        now = time.time()
        tag = "refreshed" if refresh else "stub"
        return TokenBundle(
            access_token  = f"{self.provider.value}-{tag}-access-{int(now)}",
            refresh_token = f"{self.provider.value}-refresh",
            expires_at    = now + 3600,
            scopes        = list(self.oauth.scopes),
        )
