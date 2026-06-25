"""Microsoft Outlook Calendar connector — interview schedule source via Graph."""

from __future__ import annotations

import time
from typing import List

from backend.connectors.base import BaseConnector
from backend.connectors.models import (
    ConnectorCapabilities, ConnectorProvider, MeetingRef, OAuthConfig, TokenBundle,
)
from backend.connectors.registry import register


@register
class MicrosoftCalendarConnector(BaseConnector):
    provider     = ConnectorProvider.MICROSOFT_CALENDAR
    display_name = "Outlook Calendar"
    capabilities = ConnectorCapabilities(
        meeting_metadata=True, transcript_support=False, recording_support=False,
        live_stream_support=False, participant_metadata=True,
    )
    oauth = OAuthConfig(
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        scopes=["offline_access", "Calendars.Read"],
    )

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        return self._stub_tokens()

    async def refresh(self, refresh_token: str) -> TokenBundle:
        return self._stub_tokens(refresh=True)

    async def list_upcoming_meetings(self, access_token: str) -> List[MeetingRef]:
        if not access_token:
            return []
        now = time.time()
        events = [
            ("Platform Engineer · Hiring Manager Round", 3600,  "microsoft_teams", None, 2),
            ("Data Scientist · Behavioral",              12600, "webex",          None, 3),
        ]
        return [
            MeetingRef(
                external_id=f"mscal-evt-{i}", title=title, start_time=now + offset,
                join_url=url, participants=people, platform=platform,
            )
            for i, (title, offset, platform, url, people) in enumerate(events, 1)
        ]
