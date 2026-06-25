"""
Face analysis service — wraps eye tracker and expression analyzer.
Processes base64-encoded JPEG frames sent via WebSocket.
"""

import cv2
import numpy as np
import base64
import time
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.models.schemas import FaceMetrics

logger = logging.getLogger(__name__)


class FaceAnalysisService:
    def __init__(self):
        self._initialized = False
        self._eye_tracker = None
        self._expression_analyzer = None
        try:
            from ml.face.eye_tracker import EyeContactTracker
            from ml.face.expression_analyzer import ExpressionAnalyzer
            self._eye_tracker = EyeContactTracker()
            self._expression_analyzer = ExpressionAnalyzer()
            self._initialized = True
            logger.info("FaceAnalysisService ready (MediaPipe)")
        except Exception as exc:
            logger.warning("FaceAnalysisService degraded — face analysis disabled: %s", exc)

    def process_frame_b64(self, frame_b64: str) -> FaceMetrics:
        if not self._initialized:
            return FaceMetrics()
        try:
            img_data = base64.b64decode(frame_b64)
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return FaceMetrics()
            return self._process(frame)
        except Exception:
            return FaceMetrics()

    def process_frame_bytes(self, frame_bytes: bytes) -> FaceMetrics:
        if not self._initialized:
            return FaceMetrics()
        try:
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return FaceMetrics()
            return self._process(frame)
        except Exception:
            return FaceMetrics()

    def _process(self, frame: np.ndarray) -> FaceMetrics:
        eye_result  = self._eye_tracker.process_frame(frame)
        expr_result = self._expression_analyzer.process_frame(frame)
        return FaceMetrics(
            timestamp=time.time(),
            eye_contact_score=eye_result.eye_contact_score,
            gaze_direction=eye_result.gaze_direction,
            blink_rate=eye_result.blink_rate,
            head_stability=eye_result.head_stability,
            facial_tension=expr_result.facial_tension,
            expression_label=expr_result.expression_label,
            face_detected=eye_result.face_detected,
        )

    def release(self):
        try:
            if self._eye_tracker:
                self._eye_tracker.release()
            if self._expression_analyzer:
                self._expression_analyzer.release()
        except Exception:
            pass
