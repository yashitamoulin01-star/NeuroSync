"""
TimestampNormalizer — maps a source's media clock onto a common session-relative
clock so video, audio, and transcript never drift apart regardless of origin.

Different sources timestamp differently: a live WebSocket uses wall-clock arrival
time; an uploaded file uses container PTS starting at 0; an RTSP stream uses RTP
timestamps. This normalizes all of them to "seconds since session start", which
is what the fusion synchronizer's sliding window expects.
"""

from __future__ import annotations

import time
from typing import Optional


class TimestampNormalizer:
    def __init__(self, session_started_at: Optional[float] = None) -> None:
        self._session_start = session_started_at if session_started_at is not None else time.time()
        self._source_origin: Optional[float] = None

    def normalize(self, source_ts: Optional[float]) -> float:
        """
        Return seconds-since-session-start for a source timestamp.

        - Live sources pass wall-clock (or None → 'now'); we subtract session start.
        - Offline sources pass media-relative PTS (first frame ~0); we anchor the
          first observed value as the origin so playback maps to elapsed time.
        """
        if source_ts is None:
            return max(0.0, time.time() - self._session_start)

        # Heuristic: wall-clock timestamps are large (epoch seconds); media PTS is small.
        if source_ts > 1_000_000_000:        # looks like epoch seconds
            return max(0.0, source_ts - self._session_start)

        # Media-relative PTS — anchor first value as origin.
        if self._source_origin is None:
            self._source_origin = source_ts
        return max(0.0, source_ts - self._source_origin)
