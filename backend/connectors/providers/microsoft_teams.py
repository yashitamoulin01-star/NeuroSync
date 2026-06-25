"""Microsoft 365 connector — Teams + Graph."""

from __future__ import annotations

from backend.connectors.base import BaseConnector
from backend.connectors.models import (
    ConnectorCapabilities, ConnectorProvider, OAuthConfig, TokenBundle,
)
from backend.connectors.registry import register


@register
class MicrosoftTeamsConnector(BaseConnector):
    provider     = ConnectorProvider.MICROSOFT_TEAMS
    display_name = "Microsoft 365"
    capabilities = ConnectorCapabilities(
        meeting_metadata     = True,
        transcript_support   = True,
        recording_support    = True,
        live_stream_support  = True,    # Graph communications media access
        participant_metadata = True,
    )
    oauth = OAuthConfig(
        authorize_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url     = "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        scopes        = [
            "offline_access",
            "Calendars.Read",
            "OnlineMeetings.Read",
            "OnlineMeetingTranscript.Read.All",
        ],
    )

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        return self._stub_tokens()

    async def refresh(self, refresh_token: str) -> TokenBundle:
        return self._stub_tokens(refresh=True)
