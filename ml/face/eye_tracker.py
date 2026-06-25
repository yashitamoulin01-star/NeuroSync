from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

_BLINK_THRESHOLD = 0.22
_MAX_BLINK_RATE  = 45.0   # physiological cap (blinks/min)


@dataclass
class EyeTrackerResult:
    eye_contact_score: float = 0.5
    gaze_direction: str = "unknown"
    blink_rate: float = 0.0
    head_stability: float = 0.5
    face_detected: bool = False


class EyeContactTracker:
    def __init__(self) -> None:
        self._face_mesh = None
        self._initialized = False
        self._frame_count = 0
        self._blink_count = 0
        self._prev_ear: float = 1.0
        self._head_positions: list[tuple[float, float]] = []
        self._init()

    # ── init ──────────────────────────────────────────────────────────────────

    def _init(self) -> None:
        try:
            import mediapipe as mp
            self._mp = mp.solutions.face_mesh
            self._face_mesh = self._mp.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._initialized = True
            logger.debug("EyeContactTracker: MediaPipe FaceMesh ready")
        except Exception as exc:
            logger.warning("EyeContactTracker: MediaPipe unavailable (%s) — returning defaults", exc)

    # ── public ────────────────────────────────────────────────────────────────

    def process_frame(self, frame: np.ndarray) -> EyeTrackerResult:
        if not self._initialized or frame is None or frame.size == 0:
            return EyeTrackerResult()

        try:
            import cv2
            self._frame_count += 1
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._face_mesh.process(rgb)

            if not results.multi_face_landmarks:
                return EyeTrackerResult(face_detected=False)

            lm = results.multi_face_landmarks[0].landmark
            h, w = frame.shape[:2]

            # ── iris centre (refined landmarks 468/473) ──────────────────────
            if len(lm) > 473:
                ix = (lm[468].x + lm[473].x) / 2
                iy = (lm[468].y + lm[473].y) / 2
            else:
                ix, iy = lm[1].x, lm[1].y   # nose tip fallback

            dx = abs(ix - 0.5)
            dy = abs(iy - 0.5)
            eye_contact_score = float(np.clip(1.0 - (dx * 2.8 + dy * 2.8), 0.0, 1.0))

            # ── gaze direction ───────────────────────────────────────────────
            if ix < 0.40:
                gaze = "right"
            elif ix > 0.60:
                gaze = "left"
            elif iy < 0.40:
                gaze = "up"
            elif iy > 0.60:
                gaze = "down"
            else:
                gaze = "center"

            # ── blink (EAR) ──────────────────────────────────────────────────
            def _ear(pts: list[int]) -> float:
                p = [(lm[i].x * w, lm[i].y * h) for i in pts]
                v1 = np.linalg.norm(np.array(p[1]) - np.array(p[5]))
                v2 = np.linalg.norm(np.array(p[2]) - np.array(p[4]))
                hz = np.linalg.norm(np.array(p[0]) - np.array(p[3]))
                return float((v1 + v2) / (2.0 * hz + 1e-6))

            ear = (_ear([33, 160, 158, 133, 153, 144]) +
                   _ear([362, 385, 387, 263, 373, 380])) / 2.0

            if self._prev_ear > _BLINK_THRESHOLD and ear <= _BLINK_THRESHOLD:
                self._blink_count += 1
            self._prev_ear = ear

            # Approximate 30 fps; clip to physiological range
            blink_rate = float(np.clip(
                self._blink_count * 30.0 * 60.0 / max(self._frame_count, 1),
                0.0, _MAX_BLINK_RATE,
            ))

            # ── head stability ───────────────────────────────────────────────
            nx, ny = lm[1].x, lm[1].y
            self._head_positions.append((nx, ny))
            if len(self._head_positions) > 30:
                self._head_positions.pop(0)

            if len(self._head_positions) > 2:
                arr = np.array(self._head_positions)
                jitter = float(np.std(arr, axis=0).mean())
                head_stability = float(np.clip(1.0 - jitter * 20.0, 0.0, 1.0))
            else:
                head_stability = 0.8

            return EyeTrackerResult(
                eye_contact_score=eye_contact_score,
                gaze_direction=gaze,
                blink_rate=blink_rate,
                head_stability=head_stability,
                face_detected=True,
            )
        except Exception as exc:
            logger.debug("EyeContactTracker.process_frame error: %s", exc)
            return EyeTrackerResult()

    def release(self) -> None:
        if self._face_mesh is not None:
            try:
                self._face_mesh.close()
            except Exception:
                pass
        self._initialized = False
