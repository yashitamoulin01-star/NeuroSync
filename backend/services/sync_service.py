"""
Session synchronization logger.
Collects timestamped events from all modalities and serializes them
to timestamps.json for replay, labeling, and multimodal alignment.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SyncEvent:
    t: float           # seconds since session start
    event_type: str    # e.g. "gaze_shift", "pitch_spike", "hesitation_phrase"
    modality: str      # face | audio | nlp | fusion
    severity: float = 0.0
    text: Optional[str] = None
    data: dict = field(default_factory=dict)


class SessionSyncLogger:
    """
    Thread-safe event log for one session.
    Populated live during recording; serialized on finalize().
    """

    SCHEMA_VERSION = "1.0"

    def __init__(self, session_id: str, started_at: float):
        self.session_id = session_id
        self.started_at = started_at
        self._lock = threading.Lock()
        self._events: List[SyncEvent] = []
        self._transcript_segments: List[dict] = []

    # ── Logging helpers ───────────────────────────────────────────────────────

    def _rel(self, t: float) -> float:
        return round(t - self.started_at, 4)

    def log_event(
        self,
        event_type: str,
        modality: str,
        severity: float = 0.0,
        text: Optional[str] = None,
        **data,
    ):
        ev = SyncEvent(
            t=self._rel(time.time()),
            event_type=event_type,
            modality=modality,
            severity=round(severity, 4),
            text=text,
            data=data,
        )
        with self._lock:
            self._events.append(ev)

    def log_transcript_segment(self, text: str, start_abs: float, end_abs: float):
        seg = {
            "start": self._rel(start_abs),
            "end": self._rel(end_abs),
            "text": text.strip(),
        }
        with self._lock:
            self._transcript_segments.append(seg)

    def log_behavioral_insight(self, insight_type: str, description: str, severity: float, modalities: List[str]):
        self.log_event(
            event_type=insight_type,
            modality=",".join(modalities),
            severity=severity,
            text=description,
        )

    # ── Finalize ──────────────────────────────────────────────────────────────

    def build(
        self,
        duration: float,
        video_frame_timestamps: List[float],
        audio_chunk_meta: List[dict],
        video_fps: float = 15.0,
        audio_sample_rate: int = 16000,
    ) -> dict:
        with self._lock:
            events = sorted(
                [
                    {
                        "t": ev.t,
                        "type": ev.event_type,
                        "modality": ev.modality,
                        "severity": ev.severity,
                        **({"text": ev.text} if ev.text else {}),
                        **(ev.data if ev.data else {}),
                    }
                    for ev in self._events
                ],
                key=lambda x: x["t"],
            )
            segments = sorted(self._transcript_segments, key=lambda x: x["start"])

        return {
            "schema_version": self.SCHEMA_VERSION,
            "session_id": self.session_id,
            "session_start_unix": self.started_at,
            "duration_seconds": round(duration, 3),
            "video_fps": video_fps,
            "audio_sample_rate": audio_sample_rate,
            "video_frames": [
                {"t": t, "frame_idx": i}
                for i, t in enumerate(video_frame_timestamps)
            ],
            "audio_chunks": audio_chunk_meta,
            "transcript_segments": segments,
            "behavioral_events": events,
        }

    def save(self, path: Path, **kwargs) -> dict:
        data = self.build(**kwargs)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(
            "timestamps.json saved for %s — %d events, %d transcript segments",
            self.session_id[:8],
            len(data["behavioral_events"]),
            len(data["transcript_segments"]),
        )
        return data
