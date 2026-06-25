from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ExpressionResult:
    facial_tension: float = 0.0
    expression_label: str = "neutral"


class ExpressionAnalyzer:
    def __init__(self) -> None:
        self._face_mesh = None
        self._initialized = False
        self._init()

    def _init(self) -> None:
        try:
            import mediapipe as mp
            self._mp = mp.solutions.face_mesh
            self._face_mesh = self._mp.FaceMesh(
                max_num_faces=1,
                refine_landmarks=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._initialized = True
            logger.debug("ExpressionAnalyzer: MediaPipe FaceMesh ready")
        except Exception as exc:
            logger.warning("ExpressionAnalyzer: MediaPipe unavailable (%s) — returning defaults", exc)

    def process_frame(self, frame: np.ndarray) -> ExpressionResult:
        if not self._initialized or frame is None or frame.size == 0:
            return ExpressionResult()

        try:
            import cv2
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._face_mesh.process(rgb)

            if not results.multi_face_landmarks:
                return ExpressionResult()

            lm = results.multi_face_landmarks[0].landmark
            h, w = frame.shape[:2]
            pts = np.array([[m.x * w, m.y * h] for m in lm])

            # Mouth openness: distance between upper (13) and lower (14) lip
            mouth_open = float(abs(pts[13, 1] - pts[14, 1]) / (h + 1e-6))

            # Brow position: brow landmark vs upper-eyelid landmark
            # Left: brow=70, upper-lid=159 | Right: brow=300, upper-lid=386
            left_raise  = float((pts[159, 1] - pts[70,  1]) / (h + 1e-6))
            right_raise = float((pts[386, 1] - pts[300, 1]) / (h + 1e-6))
            brow_raise  = (left_raise + right_raise) / 2.0

            # Jaw tension: face height ratio (152=chin, 10=forehead)
            face_height = float(abs(pts[152, 1] - pts[10, 1]) / (h + 1e-6))
            # Tighter jaw → smaller vertical extent relative to face
            facial_tension = float(np.clip(1.0 - face_height * 3.5, 0.0, 1.0))

            # Label
            if mouth_open > 0.04:
                label = "talking"
            elif brow_raise > 0.025:
                label = "surprised"
            elif facial_tension > 0.65:
                label = "tense"
            else:
                label = "neutral"

            return ExpressionResult(facial_tension=facial_tension, expression_label=label)

        except Exception as exc:
            logger.debug("ExpressionAnalyzer.process_frame error: %s", exc)
            return ExpressionResult()

    def release(self) -> None:
        if self._face_mesh is not None:
            try:
                self._face_mesh.close()
            except Exception:
                pass
        self._initialized = False
