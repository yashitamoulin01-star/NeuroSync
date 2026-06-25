"""Slack connector — huddles / calls metadata."""

from __future__ import annotations

from backend.connectors.base import BaseConnector
from backend.connectors.models import (
    ConnectorCapabilities, ConnectorProvider, OAuthConfig, TokenBundle,
)
from backend.connectors.registry import register


@register
class SlackConnector(BaseConnector):
    provider     = ConnectorProvider.SLACK
    display_name = "Slack"
    capabilities = ConnectorCapabilities(
        meeting_metadata     = True,
        transcript_support   = False,
        recording_support    = False,
        live_stream_support  = False,
        participant_metadata = True,
    )
    oauth = OAuthConfig(
        authorize_url = "https://slack.com/oauth/v2/authorize",
        token_url     = "https://slack.com/api/oauth.v2.access",
        scopes        = ["calls:read", "users:read"],
    )

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        return self._stub_tokens()

    async def refresh(self, refresh_token: str) -> TokenBundle:
        return self._stub_tokens(refresh=True)
