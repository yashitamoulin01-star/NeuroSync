"""Cisco Webex connector."""

from __future__ import annotations

from backend.connectors.base import BaseConnector
from backend.connectors.models import (
    ConnectorCapabilities, ConnectorProvider, OAuthConfig, TokenBundle,
)
from backend.connectors.registry import register


@register
class WebexConnector(BaseConnector):
    provider     = ConnectorProvider.WEBEX
    display_name = "Cisco Webex"
    capabilities = ConnectorCapabilities(
        meeting_metadata     = True,
        transcript_support   = True,
        recording_support    = True,
        live_stream_support  = False,
        participant_metadata = True,
    )
    oauth = OAuthConfig(
        authorize_url = "https://webexapis.com/v1/authorize",
        token_url     = "https://webexapis.com/v1/access_token",
        scopes        = ["meeting:schedules_read", "meeting:recordings_read", "spark:people_read"],
    )

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        return self._stub_tokens()

    async def refresh(self, refresh_token: str) -> TokenBundle:
        return self._stub_tokens(refresh=True)
