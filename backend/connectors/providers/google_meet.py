"""Google Workspace connector — Meet + Calendar."""

from __future__ import annotations

from backend.connectors.base import BaseConnector
from backend.connectors.models import (
    ConnectorCapabilities, ConnectorProvider, OAuthConfig, TokenBundle,
)
from backend.connectors.registry import register


@register
class GoogleMeetConnector(BaseConnector):
    provider     = ConnectorProvider.GOOGLE_MEET
    display_name = "Google Workspace"
    capabilities = ConnectorCapabilities(
        meeting_metadata     = True,
        transcript_support   = True,
        recording_support    = True,
        live_stream_support  = False,   # Meet has no public live media stream API
        participant_metadata = True,
    )
    oauth = OAuthConfig(
        authorize_url = "https://accounts.google.com/o/oauth2/v2/auth",
        token_url     = "https://oauth2.googleapis.com/token",
        revoke_url    = "https://oauth2.googleapis.com/revoke",
        scopes        = [
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/meetings.space.readonly",
        ],
    )

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        return self._stub_tokens()

    async def refresh(self, refresh_token: str) -> TokenBundle:
        return self._stub_tokens(refresh=True)
