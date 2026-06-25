"""Greenhouse ATS adapter."""

from __future__ import annotations

from backend.ats.base import ATSConnector
from backend.ats.models import ATSCapabilities, ATSProvider, ExportResult
from backend.ats.registry import register
from backend.connectors.models import OAuthConfig, TokenBundle


@register
class GreenhouseConnector(ATSConnector):
    provider     = ATSProvider.GREENHOUSE
    display_name = "Greenhouse"
    capabilities = ATSCapabilities(push_report=True, write_scorecard=True, sync_candidates=True, write_back_stage=True)
    oauth = OAuthConfig(
        authorize_url="https://app.greenhouse.io/oauth/authorize",
        token_url="https://app.greenhouse.io/oauth/token",
        scopes=["candidates.read", "candidates.write", "scorecards.write"],
    )

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        return self._stub_tokens()

    async def refresh(self, refresh_token: str) -> TokenBundle:
        return self._stub_tokens(refresh=True)

    async def push_report(self, access_token: str, report: dict) -> ExportResult:
        return self._stub_push(report)
