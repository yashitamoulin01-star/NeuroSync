"""
Rolling-window latency tracker for all inference components.
Thread-safe; no external dependencies beyond stdlib.
"""

import time
import threading
from collections import deque
from typing import Optional

_WINDOW = 300   # keep last 300 samples per component


class _MetricsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lat: dict[str, deque] = {
            "face":   deque(maxlen=_WINDOW),
            "audio":  deque(maxlen=_WINDOW),
            "nlp":    deque(maxlen=_WINDOW),
            "fusion": deque(maxlen=_WINDOW),
        }
        self._ws_messages = 0
        self._ws_frames   = 0
        self._started_at  = time.time()

    # ── recording ────────────────────────────────────────────────────────────

    def record(self, component: str, latency_ms: float) -> None:
        with self._lock:
            if component in self._lat:
                self._lat[component].append(latency_ms)

    def record_ws_message(self) -> None:
        with self._lock:
            self._ws_messages += 1

    def record_ws_frame(self) -> None:
        with self._lock:
            self._ws_frames += 1

    # ── querying ──────────────────────────────────────────────────────────────

    def _pct(self, data: deque, p: float) -> Optional[float]:
        if not data:
            return None
        s = sorted(data)
        idx = max(0, min(int(len(s) * p / 100), len(s) - 1))
        return round(s[idx], 1)

    def get_inference_stats(self) -> dict:
        with self._lock:
            out: dict = {}
            for name, q in self._lat.items():
                out[name] = {
                    "p50": self._pct(q, 50),
                    "p95": self._pct(q, 95),
                    "p99": self._pct(q, 99),
                    "n":   len(q),
                }
            return out

    def get_websocket_stats(self) -> dict:
        with self._lock:
            uptime = time.time() - self._started_at
            rate   = round(self._ws_messages / max(uptime, 1), 2)
            return {
                "total_messages": self._ws_messages,
                "total_frames":   self._ws_frames,
                "messages_per_sec": rate,
                "uptime_seconds": round(uptime),
            }


# Singleton — imported by both ws_session and the benchmarks endpoint
metrics_service = _MetricsStore()
