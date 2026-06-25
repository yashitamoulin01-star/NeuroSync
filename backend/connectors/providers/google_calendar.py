"""Google Calendar connector — the recruiter's interview schedule source."""

from __future__ import annotations

import time
from typing import List

from backend.connectors.base import BaseConnector
from backend.connectors.models import (
    ConnectorCapabilities, ConnectorProvider, MeetingRef, OAuthConfig, TokenBundle,
)
from backend.connectors.registry import register


@register
class GoogleCalendarConnector(BaseConnector):
    provider     = ConnectorProvider.GOOGLE_CALENDAR
    display_name = "Google Calendar"
    capabilities = ConnectorCapabilities(
        meeting_metadata=True, transcript_support=False, recording_support=False,
        live_stream_support=False, participant_metadata=True,
    )
    oauth = OAuthConfig(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        revoke_url="https://oauth2.googleapis.com/revoke",
        scopes=["https://www.googleapis.com/auth/calendar.events.readonly"],
    )

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        return self._stub_tokens()

    async def refresh(self, refresh_token: str) -> TokenBundle:
        return self._stub_tokens(refresh=True)

    async def list_upcoming_meetings(self, access_token: str) -> List[MeetingRef]:
        if not access_token:
            return []
        now = time.time()
        # Placeholder schedule until the Google Calendar API is wired. Each event
        # carries a detected meeting platform so the dashboard can route Join Analysis.
        events = [
            ("Senior Backend Engineer · Final Round", 1800,  "google_meet", "https://meet.google.com/abc-defg-hij", 2),
            ("ML Engineer · Technical Screen",        9000,  "zoom",        "https://zoom.us/j/123456789", 2),
            ("Product Manager · Panel",               16200, "microsoft_teams", None, 4),
        ]
        return [
            MeetingRef(
                external_id=f"gcal-evt-{i}", title=title, start_time=now + offset,
                join_url=url, participants=people, platform=platform,
            )
            for i, (title, offset, platform, url, people) in enumerate(events, 1)
        ]
