"""
Multimodal Synchronizer — ring-buffer windowing layer.

Responsibility: collect per-modality metrics as they arrive, maintain a rolling
time window, and expose averaged metrics snapshots to the reasoning pipeline.

This module no longer computes composite scores or generates insights directly.
Score computation is handled by backend.reasoning.pipeline, which transforms
averaged metrics into evidence → scores → insights.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import List, Optional, Tuple

from backend.models.schemas import (
    AudioMetrics,
    FaceMetrics,
    FusedAnalytics,
    NLPMetrics,
)

logger = logging.getLogger(__name__)

_BUF_CAP = 300   # maximum items per modality ring-buffer


class MultimodalSynchronizer:
    def __init__(self, window_seconds: float = 3.0, session_id: str = "default") -> None:
        self._window       = window_seconds
        self._session_id   = session_id
        self._session_start = time.time()

        self._face_buf:  deque[Tuple[float, FaceMetrics]]  = deque(maxlen=_BUF_CAP)
        self._audio_buf: deque[Tuple[float, AudioMetrics]] = deque(maxlen=_BUF_CAP)
        self._nlp_buf:   deque[Tuple[float, NLPMetrics]]   = deque(maxlen=_BUF_CAP)

        self._total_words:   int   = 0
        self._total_fillers: int   = 0
        self._pace_samples:  list  = []

    # ── ingest ────────────────────────────────────────────────────────────────

    def ingest_face(self, metrics: FaceMetrics) -> None:
        now = time.time()
        self._face_buf.append((now, metrics))
        self._prune(self._face_buf)

    def ingest_audio(self, metrics: AudioMetrics) -> None:
        now = time.time()
        self._audio_buf.append((now, metrics))
        self._prune(self._audio_buf)
        if metrics.speaking_pace > 0:
            self._pace_samples.append(metrics.speaking_pace)

    def ingest_nlp(self, metrics: NLPMetrics) -> None:
        now = time.time()
        self._nlp_buf.append((now, metrics))
        self._prune(self._nlp_buf)
        self._total_words   += metrics.words_per_chunk
        self._total_fillers += metrics.filler_word_count

    # ── fuse ──────────────────────────────────────────────────────────────────

    def fuse(
        self,
        score_history:    Optional[list] = None,
        behavioral_state: str            = "warming_up",
        window_index:     int            = 0,
    ) -> FusedAnalytics:
        """
        Compute window averages then run the full reasoning pipeline.

        Phase 3: temporal context (score_history, behavioral_state, window_index)
        is passed through from the session so the pipeline can reason over history.
        """
        from backend.reasoning.pipeline import run_reasoning_pipeline

        now = time.time()

        face_items  = self._window_items(self._face_buf,  now)
        audio_items = self._window_items(self._audio_buf, now)
        nlp_items   = self._window_items(self._nlp_buf,   now)

        avg_face  = self._average_face(face_items)
        avg_audio = self._average_audio(audio_items)
        avg_nlp   = self._average_nlp(nlp_items)

        avg_pace = (
            sum(self._pace_samples) / len(self._pace_samples)
            if self._pace_samples else 0.0
        )

        return run_reasoning_pipeline(
            face             = avg_face,
            audio            = avg_audio,
            nlp              = avg_nlp,
            session_id       = self._session_id,
            session_start    = self._session_start,
            total_words      = self._total_words,
            total_fillers    = self._total_fillers,
            avg_pace         = round(avg_pace, 1),
            score_history    = score_history,
            behavioral_state = behavioral_state,
            window_index     = window_index,
        )

    # ── reset ─────────────────────────────────────────────────────────────────

    def reset(self, new_session_id: str = "default") -> None:
        self._session_id    = new_session_id
        self._session_start = time.time()
        self._face_buf.clear()
        self._audio_buf.clear()
        self._nlp_buf.clear()
        self._total_words   = 0
        self._total_fillers = 0
        self._pace_samples  = []

    # ── window averagers ─────────────────────────────────────────────────────

    def _average_face(self, items: List[FaceMetrics]) -> Optional[FaceMetrics]:
        if not items:
            return None
        # Use the most recent item for non-numeric fields; average all numeric fields.
        latest = items[-1]
        n = len(items)
        return FaceMetrics(
            timestamp         = latest.timestamp,
            eye_contact_score = _avg(items, lambda m: m.eye_contact_score),
            gaze_direction    = latest.gaze_direction,
            blink_rate        = _avg(items, lambda m: m.blink_rate),
            head_stability    = _avg(items, lambda m: m.head_stability),
            facial_tension    = _avg(items, lambda m: m.facial_tension),
            expression_label  = latest.expression_label,
            face_detected     = any(m.face_detected for m in items),
        )

    def _average_audio(self, items: List[AudioMetrics]) -> Optional[AudioMetrics]:
        if not items:
            return None
        latest = items[-1]
        speaking_items = [m for m in items if m.is_speaking]
        # Averages over speaking frames only, so silence doesn't dilute energy.
        ref = speaking_items if speaking_items else items
        return AudioMetrics(
            timestamp       = latest.timestamp,
            pitch_mean      = _avg(ref, lambda m: m.pitch_mean),
            pitch_variance  = _avg(ref, lambda m: m.pitch_variance),
            speaking_pace   = _avg(ref, lambda m: m.speaking_pace),
            pause_ratio     = _avg(items, lambda m: m.pause_ratio),
            energy_level    = _avg(ref, lambda m: m.energy_level),
            vocal_stability = _avg(ref, lambda m: m.vocal_stability),
            voice_stress_score = _avg(ref, lambda m: m.voice_stress_score),
            is_speaking     = any(m.is_speaking for m in items),
        )

    def _average_nlp(self, items: List[NLPMetrics]) -> Optional[NLPMetrics]:
        if not items:
            return None
        latest = items[-1]
        return NLPMetrics(
            timestamp                 = latest.timestamp,
            transcript_chunk          = " ".join(
                m.transcript_chunk for m in items if m.transcript_chunk.strip()
            ),
            filler_word_count         = round(_avg(items, lambda m: float(m.filler_word_count))),
            filler_words_detected     = [],  # per-chunk events not meaningful after averaging
            confidence_language_score = _avg(items, lambda m: m.confidence_language_score),
            hesitation_score          = _avg(items, lambda m: m.hesitation_score),
            clarity_score             = _avg(items, lambda m: m.clarity_score),
            sentiment_polarity        = _avg(items, lambda m: m.sentiment_polarity),
            words_per_chunk           = round(_avg(items, lambda m: float(m.words_per_chunk))),
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _prune(self, buf: deque) -> None:
        cutoff = time.time() - self._window
        while buf and buf[0][0] < cutoff:
            buf.popleft()

    def _window_items(self, buf: deque, now: float) -> list:
        cutoff = now - self._window
        return [m for ts, m in buf if ts >= cutoff]


def _avg(items: list, fn, default: float = 0.0) -> float:
    vals = [fn(m) for m in items]
    return float(sum(vals) / len(vals)) if vals else default
