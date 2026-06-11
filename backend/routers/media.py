"""
Media serving router.
Streams saved video and audio files with range-request support
so the HTML5 <video> element can seek without downloading the full file.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/media", tags=["media"])


def _raw_path(session_id: str) -> Path:
    return Path(settings.DATASET_DIR) / "raw" / "sessions" / session_id


def _processed_path(session_id: str) -> Path:
    return Path(settings.DATASET_DIR) / "processed" / "sessions" / session_id


@router.get("/{session_id}/video")
async def get_video(session_id: str):
    path = _raw_path(session_id) / "video.mp4"
    if not path.exists():
        raise HTTPException(404, "Video not found for this session")
    return FileResponse(
        str(path),
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/{session_id}/audio")
async def get_audio(session_id: str):
    path = _raw_path(session_id) / "audio.wav"
    if not path.exists():
        raise HTTPException(404, "Audio not found for this session")
    return FileResponse(str(path), media_type="audio/wav")


@router.get("/{session_id}/timestamps")
async def get_timestamps(session_id: str):
    path = _processed_path(session_id) / "timestamps.json"
    if not path.exists():
        raise HTTPException(404, "Timestamps not found for this session")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@router.get("/{session_id}/transcript")
async def get_transcript(session_id: str):
    path = _processed_path(session_id) / "transcript.txt"
    if not path.exists():
        raise HTTPException(404, "Transcript not found")
    return {"transcript": path.read_text(encoding="utf-8")}


@router.get("/{session_id}/exists")
async def media_exists(session_id: str):
    raw = _raw_path(session_id)
    proc = _processed_path(session_id)
    return {
        "video": (raw / "video.mp4").exists(),
        "audio": (raw / "audio.wav").exists(),
        "timestamps": (proc / "timestamps.json").exists(),
        "transcript": (proc / "transcript.txt").exists(),
    }
