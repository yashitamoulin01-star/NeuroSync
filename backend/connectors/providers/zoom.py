"""Zoom Meetings connector."""

from __future__ import annotations

from backend.connectors.base import BaseConnector
from backend.connectors.models import (
    ConnectorCapabilities, ConnectorProvider, OAuthConfig, TokenBundle,
)
from backend.connectors.registry import register


@register
class ZoomConnector(BaseConnector):
    provider     = ConnectorProvider.ZOOM
    display_name = "Zoom"
    capabilities = ConnectorCapabilities(
        meeting_metadata     = True,
        transcript_support   = True,
        recording_support    = True,
        live_stream_support  = True,    # RTMS / meeting SDK raw data
        participant_metadata = True,
    )
    oauth = OAuthConfig(
        authorize_url = "https://zoom.us/oauth/authorize",
        token_url     = "https://zoom.us/oauth/token",
        revoke_url    = "https://zoom.us/oauth/revoke",
        scopes        = ["meeting:read", "recording:read", "user:read"],
    )

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        return self._stub_tokens()

    async def refresh(self, refresh_token: str) -> TokenBundle:
        return self._stub_tokens(refresh=True)
