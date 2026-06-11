"""
Session media recorder.
Captures webcam frames → video.mp4 and PCM audio → audio.wav
using a dedicated background thread per session so the WebSocket
handler is never blocked by I/O.
"""

import base64
import logging
import queue
import threading
import time
import wave
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_SENTINEL = object()
_DEFAULT_FPS = 15.0


class SessionMediaRecorder:
    """
    Thread-safe, non-blocking recorder for one interview session.
    Call write_frame() and write_audio() from any thread.
    Call finalize() exactly once when the session ends.
    """

    def __init__(self, session_id: str, raw_dir: Path):
        self.session_id = session_id
        self._dir = raw_dir / session_id
        self._dir.mkdir(parents=True, exist_ok=True)

        self._video_path = self._dir / "video.mp4"
        self._audio_path = self._dir / "audio.wav"

        self._q: queue.Queue = queue.Queue(maxsize=512)
        self._lock = threading.Lock()

        # Video state
        self._vw: Optional[cv2.VideoWriter] = None
        self._fps = _DEFAULT_FPS
        self._frame_count = 0
        self._frame_timestamps: list[float] = []

        # Audio state
        self._wav: Optional[wave.Wave_write] = None
        self._sample_rate: int = 16000
        self._audio_chunk_count = 0
        self._audio_chunk_meta: list[dict] = []

        self._started_at = time.time()
        self._finalized = False

        self._thread = threading.Thread(target=self._worker, daemon=True, name=f"media-{session_id[:8]}")
        self._thread.start()

    # ── Public API (non-blocking) ─────────────────────────────────────────────

    def write_frame(self, jpeg_bytes: bytes, timestamp: float):
        if self._finalized:
            return
        try:
            self._q.put_nowait(("frame", jpeg_bytes, timestamp))
        except queue.Full:
            logger.warning("Media queue full for %s — dropping frame", self.session_id[:8])

    def write_audio(self, pcm_bytes: bytes, sample_rate: int, timestamp: float):
        if self._finalized:
            return
        try:
            self._q.put_nowait(("audio", pcm_bytes, sample_rate, timestamp))
        except queue.Full:
            logger.warning("Media queue full for %s — dropping audio chunk", self.session_id[:8])

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def frame_timestamps(self) -> list[float]:
        return self._frame_timestamps

    @property
    def audio_chunk_meta(self) -> list[dict]:
        return self._audio_chunk_meta

    def finalize(self) -> dict:
        if self._finalized:
            return {}
        self._finalized = True
        self._q.put(_SENTINEL)
        self._thread.join(timeout=60)
        with self._lock:
            if self._vw and self._vw.isOpened():
                self._vw.release()
            if self._wav:
                try:
                    self._wav.close()
                except Exception:
                    pass
        result = {
            "video_path": str(self._video_path) if self._video_path.exists() else None,
            "audio_path": str(self._audio_path) if self._audio_path.exists() else None,
            "total_frames": self._frame_count,
            "total_audio_chunks": self._audio_chunk_count,
        }
        logger.info(
            "Media finalized for %s — %d frames, %d audio chunks",
            self.session_id[:8], self._frame_count, self._audio_chunk_count,
        )
        return result

    # ── Worker thread ─────────────────────────────────────────────────────────

    def _worker(self):
        while True:
            item = self._q.get()
            if item is _SENTINEL:
                self._q.task_done()
                break
            try:
                if item[0] == "frame":
                    self._write_frame(item[1], item[2])
                elif item[0] == "audio":
                    self._write_audio(item[1], item[2], item[3])
            except Exception as e:
                logger.error("Media write error for %s: %s", self.session_id[:8], e)
            finally:
                self._q.task_done()

    def _write_frame(self, jpeg_bytes: bytes, timestamp: float):
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return

        h, w = frame.shape[:2]
        with self._lock:
            if self._vw is None:
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                self._vw = cv2.VideoWriter(str(self._video_path), fourcc, self._fps, (w, h))
                if not self._vw.isOpened():
                    logger.error("VideoWriter failed to open for %s", self.session_id[:8])
                    self._vw = None
                    return
            self._vw.write(frame)

        self._frame_timestamps.append(round(timestamp - self._started_at, 4))
        self._frame_count += 1

    def _write_audio(self, pcm_bytes: bytes, sample_rate: int, timestamp: float):
        with self._lock:
            if self._wav is None:
                self._sample_rate = sample_rate
                self._wav = wave.open(str(self._audio_path), "wb")
                self._wav.setnchannels(1)
                self._wav.setsampwidth(2)           # 16-bit signed PCM
                self._wav.setframerate(sample_rate)
            self._wav.writeframes(pcm_bytes)

        chunk_duration = len(pcm_bytes) / (2 * self._sample_rate)   # 2 bytes per sample
        self._audio_chunk_meta.append({
            "t": round(timestamp - self._started_at, 4),
            "chunk_idx": self._audio_chunk_count,
            "duration": round(chunk_duration, 4),
        })
        self._audio_chunk_count += 1


class MediaService:
    """Registry: one SessionMediaRecorder per active session_id."""

    def __init__(self, raw_dir: Path):
        self._raw_dir = raw_dir
        self._recorders: dict[str, SessionMediaRecorder] = {}
        self._lock = threading.Lock()

    def start(self, session_id: str) -> SessionMediaRecorder:
        rec = SessionMediaRecorder(session_id, self._raw_dir)
        with self._lock:
            self._recorders[session_id] = rec
        logger.info("MediaRecorder started for %s", session_id[:8])
        return rec

    def get(self, session_id: str) -> Optional[SessionMediaRecorder]:
        return self._recorders.get(session_id)

    def stop(self, session_id: str) -> dict:
        with self._lock:
            rec = self._recorders.pop(session_id, None)
        if rec:
            return rec.finalize()
        return {}
