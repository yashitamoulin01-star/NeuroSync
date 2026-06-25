"""
Capture router — /api/capture/*

Source discovery for the Universal Meeting Launcher. Returns the catalog of
capture sources (webcam, upload, browser meetings, desktop, RTSP, virtual camera)
with negotiated capabilities and a runtime availability flag.

Core-pipeline prefix (/api/*) — this is a static capability catalog with no
tenant data, consistent with the open live-session flow.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from backend.capture.registry import capture_registry
from backend.capture.runner import capture_runner

router = APIRouter(prefix="/api/capture", tags=["capture"])


@router.get("/sources")
async def list_capture_sources():
    return {"sources": capture_registry.list_sources()}


@router.get("/running")
async def list_running():
    return {"running": capture_runner.list_running()}


@router.post("/rtsp/start")
async def start_rtsp(
    url: str = Body(..., embed=True),
    name: str = Body("", embed=True),
    mode: str = Body("interview", embed=True),
):
    """Open an RTSP/IP-camera stream server-side and analyze it as a live session."""
    if not (url.startswith("rtsp://") or url.startswith("http")):
        raise HTTPException(400, "Provide an rtsp:// or http(s):// stream URL")
    session_id = capture_runner.start(url, name or "IP Camera", mode, source_label="rtsp")
    return {"session_id": session_id, "status": "capturing"}


@router.post("/virtual-camera/start")
async def start_virtual_camera(
    device_index: int = Body(0, embed=True),
    name: str = Body("", embed=True),
    mode: str = Body("interview", embed=True),
):
    """Open a local/virtual camera device server-side and analyze it as a live session."""
    session_id = capture_runner.start(device_index, name or "Virtual Camera", mode, source_label="virtual_camera")
    return {"session_id": session_id, "status": "capturing"}


@router.post("/{session_id}/stop")
async def stop_capture(session_id: str):
    if not capture_runner.stop(session_id):
        raise HTTPException(404, "No running capture for that session")
    return {"ok": True, "session_id": session_id, "status": "stopping"}
