"""Capture source types and capability negotiation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CaptureSourceType(str, Enum):
    WEBCAM         = "webcam"          # browser getUserMedia (live, in-app)
    UPLOAD         = "upload"          # recorded file, async
    BROWSER_MEET   = "browser_meet"    # Google Meet tab via extension
    BROWSER_ZOOM   = "browser_zoom"    # Zoom Web tab via extension
    BROWSER_TEAMS  = "browser_teams"   # Teams Web tab via extension
    BROWSER_WEBEX  = "browser_webex"   # Webex Web tab via extension
    DESKTOP_AGENT  = "desktop_agent"   # native desktop window capture
    RTSP           = "rtsp"            # enterprise IP camera / interview room
    VIRTUAL_CAMERA = "virtual_camera"  # OBS / virtual camera device


@dataclass(frozen=True)
class CaptureCapabilities:
    """What a source can deliver. The launcher never offers more than this."""
    video:        bool = False
    audio:        bool = False
    transcript:   bool = False
    participants: bool = False
    live:         bool = True          # real-time vs. batch (upload = False)
    screen:       bool = False

    def to_dict(self) -> dict:
        return {
            "video": self.video, "audio": self.audio, "transcript": self.transcript,
            "participants": self.participants, "live": self.live, "screen": self.screen,
        }


@dataclass(frozen=True)
class CaptureSourceInfo:
    """Catalog entry for the Universal Meeting Launcher."""
    source_type:  CaptureSourceType
    display_name: str
    description:  str
    capabilities: CaptureCapabilities
    available:    bool                 # is this source usable in the current deployment?
    requires:     Optional[str] = None # e.g. "browser extension", "desktop agent", "connector"

    def to_dict(self) -> dict:
        return {
            "source_type":  self.source_type.value,
            "display_name": self.display_name,
            "description":  self.description,
            "capabilities": self.capabilities.to_dict(),
            "available":    self.available,
            "requires":     self.requires,
        }
