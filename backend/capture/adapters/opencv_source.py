"""
OpenCV-backed capture loop shared by RTSP and Virtual Camera adapters.

Opens a cv2 VideoCapture (RTSP URL or device index), reads frames in a blocking
loop, and pushes them through an InputNormalizer into a live session. Periodic
emit_window() builds the analytics timeline exactly like the live WebSocket path.
The loop is blocking and is always driven from a worker thread by CaptureRunner.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Union

from backend.capture.normalizer import InputNormalizer

logger = logging.getLogger("neurosync.capture.opencv")

_TARGET_FPS = 2.0          # analyzed frames per second
_FUSE_EVERY_SECONDS = 0.5  # analytics window cadence


def run_capture_loop(
    source: Union[str, int],
    normalizer: InputNormalizer,
    stop_event: threading.Event,
) -> int:
    """Blocking capture loop. Returns the number of frames analyzed."""
    try:
        import cv2
    except Exception as exc:
        logger.warning("OpenCV unavailable — capture loop cannot run: %s", exc)
        return 0

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.warning("Capture source could not be opened: %s", source)
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    sample_every = max(1, int(round(fps / _TARGET_FPS)))
    analyzed = 0
    idx = 0
    last_fuse = time.time()
    try:
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                # Live streams can momentarily stall; brief backoff then retry.
                time.sleep(0.05)
                continue
            if idx % sample_every == 0:
                ok2, buf = cv2.imencode(".jpg", frame)
                if ok2:
                    normalizer.ingest_video_frame(buf.tobytes())
                    analyzed += 1
            now = time.time()
            if now - last_fuse >= _FUSE_EVERY_SECONDS:
                normalizer.emit_window()
                last_fuse = now
            idx += 1
    finally:
        cap.release()
        if analyzed:
            normalizer.emit_window()
    logger.info("Capture loop ended: source=%s analyzed=%d", source, analyzed)
    return analyzed
