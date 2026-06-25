"""
Built-in capture source descriptors. `available` reflects what this RC actually
ships: webcam (browser) and upload (recordings) are live; browser-meeting,
desktop, RTSP, and virtual-camera sources are defined and capability-negotiated
but gated on components not yet built (extension / desktop agent / config).
"""

from __future__ import annotations

from backend.capture.models import (
    CaptureCapabilities, CaptureSourceInfo, CaptureSourceType,
)
from backend.capture.registry import capture_registry

# RTSP and virtual-camera are pulled server-side via OpenCV; available iff cv2 is installed.
try:
    import cv2  # noqa: F401
    _CV2 = True
except Exception:
    _CV2 = False

_SOURCES = [
    CaptureSourceInfo(
        source_type=CaptureSourceType.WEBCAM,
        display_name="Webcam",
        description="Live in-app interview using the browser camera and microphone.",
        capabilities=CaptureCapabilities(video=True, audio=True, transcript=True, live=True),
        available=True,
    ),
    CaptureSourceInfo(
        source_type=CaptureSourceType.UPLOAD,
        display_name="Recording Upload",
        description="Analyze a recorded interview file. Processed in the background.",
        capabilities=CaptureCapabilities(video=True, audio=True, transcript=True, live=False),
        available=True,
    ),
    CaptureSourceInfo(
        source_type=CaptureSourceType.BROWSER_MEET,
        display_name="Google Meet",
        description="Capture a Google Meet browser tab via the NeuroSync extension.",
        capabilities=CaptureCapabilities(video=True, audio=True, transcript=True, participants=True, live=True, screen=True),
        available=False, requires="browser extension",
    ),
    CaptureSourceInfo(
        source_type=CaptureSourceType.BROWSER_ZOOM,
        display_name="Zoom (Web)",
        description="Capture a Zoom Web tab via the NeuroSync extension.",
        capabilities=CaptureCapabilities(video=True, audio=True, transcript=True, participants=True, live=True, screen=True),
        available=False, requires="browser extension",
    ),
    CaptureSourceInfo(
        source_type=CaptureSourceType.BROWSER_TEAMS,
        display_name="Microsoft Teams (Web)",
        description="Capture a Teams Web tab via the NeuroSync extension.",
        capabilities=CaptureCapabilities(video=True, audio=True, transcript=True, participants=True, live=True, screen=True),
        available=False, requires="browser extension",
    ),
    CaptureSourceInfo(
        source_type=CaptureSourceType.BROWSER_WEBEX,
        display_name="Cisco Webex (Web)",
        description="Capture a Webex Web tab via the NeuroSync extension.",
        capabilities=CaptureCapabilities(video=True, audio=True, transcript=True, participants=True, live=True, screen=True),
        available=False, requires="browser extension",
    ),
    CaptureSourceInfo(
        source_type=CaptureSourceType.DESKTOP_AGENT,
        display_name="Desktop Application",
        description="Capture a native meeting window (Zoom/Teams/Slack desktop) via the NeuroSync Desktop Agent.",
        capabilities=CaptureCapabilities(video=True, audio=True, transcript=True, participants=True, live=True, screen=True),
        available=False, requires="desktop agent",
    ),
    CaptureSourceInfo(
        source_type=CaptureSourceType.RTSP,
        display_name="IP Camera (RTSP)",
        description="Enterprise interview-room camera over RTSP/ONVIF.",
        capabilities=CaptureCapabilities(video=True, audio=False, live=True),
        available=_CV2, requires=None if _CV2 else "OpenCV",
    ),
    CaptureSourceInfo(
        source_type=CaptureSourceType.VIRTUAL_CAMERA,
        display_name="Virtual Camera",
        description="Capture from OBS or a virtual camera device for demos and enterprise deployments.",
        capabilities=CaptureCapabilities(video=True, audio=False, live=True),
        available=_CV2, requires=None if _CV2 else "OpenCV",
    ),
]

for _info in _SOURCES:
    capture_registry.register(_info)
