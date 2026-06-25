"""
ATSConnector — the ATS adapter contract.

Reuses the OAuth plumbing from the meeting-connector framework (OAuthConfig,
TokenBundle) and adds the export-direction methods: push_report and
sync_candidates. Adapters translate the platform's normalized report into the
target ATS API. First-slice adapters ship deterministic stubs.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import ClassVar, List
from urllib.parse import urlencode

from backend.ats.models import ATSCapabilities, ATSProvider, CandidateRef, ExportResult
from backend.connectors.models import OAuthConfig, TokenBundle


class ATSConnector(ABC):
    provider:      ClassVar[ATSProvider]
    display_name:  ClassVar[str]
    capabilities:  ClassVar[ATSCapabilities]
    oauth:         ClassVar[OAuthConfig]

    # ── OAuth (shared shape with meeting connectors) ──────────────────────────

    def authorize_url(self, redirect_uri: str, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id":     f"{self.provider.value}-client-id",
            "redirect_uri":  redirect_uri,
            "scope":         " ".join(self.oauth.scopes),
            "state":         state,
        }
        return f"{self.oauth.authorize_url}?{urlencode(params)}"

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle: ...

    @abstractmethod
    async def refresh(self, refresh_token: str) -> TokenBundle: ...

    async def test(self, access_token: str) -> ExportResult:
        if access_token:
            return ExportResult(ok=True, message=f"{self.display_name} reachable")
        return ExportResult(ok=False, message="No access token")

    # ── Export direction ──────────────────────────────────────────────────────

    @abstractmethod
    async def push_report(self, access_token: str, report: dict) -> ExportResult:
        """Write a NeuroSync behavioral report onto the candidate in the ATS."""

    async def sync_candidates(self, access_token: str) -> List[CandidateRef]:
        """Pull the candidate roster from the ATS. Stub: empty."""
        return []

    # ── Stub helper ───────────────────────────────────────────────────────────

    def _stub_tokens(self, refresh: bool = False) -> TokenBundle:
        now = time.time()
        tag = "refreshed" if refresh else "stub"
        return TokenBundle(
            access_token=f"{self.provider.value}-{tag}-access-{int(now)}",
            refresh_token=f"{self.provider.value}-refresh",
            expires_at=now + 3600,
            scopes=list(self.oauth.scopes),
        )

    def _stub_push(self, report: dict) -> ExportResult:
        sid = report.get("session_id", "unknown")
        return ExportResult(
            ok=True,
            message=f"Report for session {sid} written to {self.display_name}",
            external_ref=f"{self.provider.value}-activity-{sid}",
        )
