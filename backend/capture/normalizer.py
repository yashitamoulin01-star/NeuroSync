"""
InputNormalizer — the Unified Stream API.

Every capture source pushes raw media here; the normalizer routes it through the
SAME per-modality services and fusion bridge that a live session uses. This is
the single choke point that guarantees provider independence: ws_session.py
(live), the upload processor (recordings), and any future adapter all converge on
identical ingestion, so the MBA engine sees one stream shape.

It wraps an existing ActiveSession rather than duplicating service wiring.
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.capture.synchronizer import TimestampNormalizer

logger = logging.getLogger("neurosync.capture.normalizer")


class InputNormalizer:
    def __init__(self, session) -> None:
        self._session = session
        self._clock = TimestampNormalizer(session_started_at=session.started_at)

    # ── Unified ingestion ─────────────────────────────────────────────────────

    def ingest_video_frame(self, frame_bytes: bytes, source_ts: Optional[float] = None) -> None:
        metrics = self._session.face_service.process_frame_bytes(frame_bytes)
        self._session.fusion_bridge.push_face(metrics)
        self._session.frame_count += 1
        if metrics.face_detected:
            self._session.camera_status = "active"
        elif self._session.camera_status == "unknown":
            self._session.camera_status = "no_signal"

    def ingest_audio_chunk(self, pcm_bytes: bytes, sample_rate: int = 16000,
                           source_ts: Optional[float] = None) -> None:
        metrics = self._session.audio_service.process_audio_chunk(pcm_bytes, sample_rate)
        self._session.fusion_bridge.push_audio(metrics)
        self._session.audio_chunk_count += 1
        if metrics.is_speaking:
            self._session.microphone_status = "active"
        elif self._session.microphone_status == "unknown":
            self._session.microphone_status = "no_signal"

    def ingest_audio_for_transcript(self, pcm_bytes: bytes) -> Optional[str]:
        chunk = self._session.audio_service.process_audio_for_transcript(pcm_bytes)
        if chunk and getattr(chunk, "text", ""):
            nlp = self._session.nlp_service.analyze_transcript_chunk(chunk.text)
            self._session.fusion_bridge.push_nlp(nlp)
            self._session.transcript_status = "active"
            return chunk.text
        return None

    # ── Window emission ───────────────────────────────────────────────────────

    def emit_window(self):
        """Fuse the current window and record it on the session (shared by all sources)."""
        temporal = self._session.get_temporal_context()
        fused = self._session.fusion_bridge.get_fused(**temporal)
        self._session.record_frame(fused)
        return fused
