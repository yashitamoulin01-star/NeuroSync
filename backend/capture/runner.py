"""
CaptureRunner — manages backend-pulled capture sessions (RTSP, virtual camera).

Each run creates a real session via the session manager, wraps it in an
InputNormalizer, and drives an OpenCV capture loop on a worker thread. The
resulting session is an ordinary live session: the dashboard polls
/api/sessions/{id}/live and the final report is identical to any other source.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Dict, Union

from backend.capture.adapters.opencv_source import run_capture_loop
from backend.capture.normalizer import InputNormalizer
from backend.models.schemas import SessionConfig
from backend.services.session_manager import session_manager

logger = logging.getLogger("neurosync.capture.runner")


@dataclass
class _RunningCapture:
    session_id: str
    source:     str
    stop_event: threading.Event
    thread:     threading.Thread


class CaptureRunner:
    def __init__(self) -> None:
        self._running: Dict[str, _RunningCapture] = {}

    def start(self, source: Union[str, int], name: str, mode: str = "interview",
              source_label: str = "rtsp") -> str:
        config = SessionConfig(session_name=name or source_label, mode=mode)
        session_id = session_manager.create_session(config)
        session = session_manager.get_session(session_id)
        normalizer = InputNormalizer(session)
        stop_event = threading.Event()

        def _worker():
            try:
                run_capture_loop(source, normalizer, stop_event)
            except Exception:
                logger.exception("Capture worker crashed for %s", session_id)
            finally:
                # Finalize so the session is a complete, reportable record.
                try:
                    session_manager.end_session(session_id)
                except Exception:
                    pass
                self._running.pop(session_id, None)

        thread = threading.Thread(target=_worker, name=f"capture-{session_id[:8]}", daemon=True)
        self._running[session_id] = _RunningCapture(session_id, str(source), stop_event, thread)
        thread.start()
        logger.info("Capture started: session=%s source=%s label=%s", session_id, source, source_label)
        return session_id

    def stop(self, session_id: str) -> bool:
        rc = self._running.get(session_id)
        if not rc:
            return False
        rc.stop_event.set()
        logger.info("Capture stop requested: session=%s", session_id)
        return True

    def is_running(self, session_id: str) -> bool:
        return session_id in self._running

    def list_running(self) -> list:
        return [{"session_id": rc.session_id, "source": rc.source} for rc in self._running.values()]


capture_runner = CaptureRunner()
