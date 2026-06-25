"""
Feature Store — structured persistence for all extracted behavioral features.

In-memory ring buffer per session (production-ready for SQLite/PostgreSQL
replacement by swapping out _FeatureBackend).

Every analytics frame that passes through the reasoning pipeline
can log its features here. This enables:
  - Offline model debugging (what did the model actually see?)
  - Retraining signal collection (features + ground truth)
  - Comparison between model versions on the same raw features
  - Drift monitoring (feature distributions over time)
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Dict, List, Optional

from backend.ai.feature_store.schemas import (
    FeatureBatch, FeatureQuality, FeatureRecord, FeatureSource,
)

logger = logging.getLogger(__name__)


class FeatureStore:
    """
    In-memory feature store with per-session ring buffers.

    Replace _batches with a DB backend for long-term persistence:
    the public API doesn't change.
    """

    def __init__(self, max_batches_per_session: int = 200) -> None:
        self._batches: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_batches_per_session)
        )
        self._global_batch_count: int = 0
        self._max = max_batches_per_session

    # ── Writing ───────────────────────────────────────────────────────────────

    def log_batch(self, batch: FeatureBatch) -> None:
        self._batches[batch.session_id].append(batch)
        self._global_batch_count += 1

    def log_features(
        self,
        session_id:   str,
        window_index: int,
        features:     List[FeatureRecord],
        face_available:  bool = False,
        audio_available: bool = False,
        nlp_available:   bool = False,
        evidence_count:  int  = 0,
    ) -> FeatureBatch:
        batch = FeatureBatch(
            session_id      = session_id,
            window_index    = window_index,
            features        = features,
            face_available  = face_available,
            audio_available = audio_available,
            nlp_available   = nlp_available,
            evidence_count  = evidence_count,
        )
        self.log_batch(batch)
        return batch

    # ── Reading ───────────────────────────────────────────────────────────────

    def get_batches(self, session_id: str) -> List[FeatureBatch]:
        return list(self._batches.get(session_id, []))

    def get_features(
        self,
        session_id:   str,
        feature_name: Optional[str] = None,
        source:       Optional[FeatureSource] = None,
    ) -> List[FeatureRecord]:
        records: List[FeatureRecord] = []
        for batch in self.get_batches(session_id):
            for f in batch.features:
                if feature_name and f.name != feature_name:
                    continue
                if source and f.source != source:
                    continue
                records.append(f)
        return records

    def get_feature_values(self, session_id: str, feature_name: str) -> List[float]:
        """Time-series of float values for a named feature (for drift analysis)."""
        return [
            f.value for f in self.get_features(session_id, feature_name)
            if isinstance(f.value, (int, float))
        ]

    def flush(self, session_id: str) -> List[FeatureBatch]:
        batches = self.get_batches(session_id)
        self._batches.pop(session_id, None)
        return batches

    # ── Observability ─────────────────────────────────────────────────────────

    def stats(self) -> Dict:
        return {
            "active_sessions": len(self._batches),
            "total_batches_logged": self._global_batch_count,
            "per_session_counts": {
                sid: len(buf) for sid, buf in self._batches.items()
            },
        }

    # ── Helpers for building feature records ──────────────────────────────────

    @staticmethod
    def make_face_features(
        session_id: str,
        window_index: int,
        eye_contact: float,
        head_stability: float,
        blink_rate: float,
        expression_label: str,
        face_quality: float,
        pipeline_version: str = "3.0.0",
    ) -> List[FeatureRecord]:
        q = FeatureQuality.HIGH if face_quality > 0.80 else (
            FeatureQuality.MEDIUM if face_quality > 0.50 else FeatureQuality.LOW
        )
        return [
            FeatureRecord(session_id=session_id, window_index=window_index,
                          name="eye_contact_score", value=eye_contact,
                          source=FeatureSource.FACE, quality=q,
                          pipeline_version=pipeline_version, extractor="mediapipe_face_mesh"),
            FeatureRecord(session_id=session_id, window_index=window_index,
                          name="head_stability_score", value=head_stability,
                          source=FeatureSource.FACE, quality=q,
                          pipeline_version=pipeline_version, extractor="mediapipe_face_mesh"),
            FeatureRecord(session_id=session_id, window_index=window_index,
                          name="blink_rate", value=blink_rate,
                          source=FeatureSource.FACE, quality=q,
                          pipeline_version=pipeline_version, extractor="mediapipe_face_mesh"),
            FeatureRecord(session_id=session_id, window_index=window_index,
                          name="expression_label", value=expression_label,
                          source=FeatureSource.FACE, quality=q,
                          pipeline_version=pipeline_version, extractor="mediapipe_face_mesh"),
        ]

    @staticmethod
    def make_audio_features(
        session_id: str,
        window_index: int,
        is_speaking: bool,
        speech_rate_wpm: float,
        voice_energy: float,
        audio_quality: float,
        pipeline_version: str = "3.0.0",
    ) -> List[FeatureRecord]:
        q = FeatureQuality.HIGH if audio_quality > 0.80 else (
            FeatureQuality.MEDIUM if audio_quality > 0.50 else FeatureQuality.LOW
        )
        return [
            FeatureRecord(session_id=session_id, window_index=window_index,
                          name="is_speaking", value=is_speaking,
                          source=FeatureSource.AUDIO, quality=q,
                          pipeline_version=pipeline_version, extractor="faster_whisper"),
            FeatureRecord(session_id=session_id, window_index=window_index,
                          name="speech_rate_wpm", value=speech_rate_wpm,
                          source=FeatureSource.AUDIO, quality=q,
                          pipeline_version=pipeline_version, extractor="faster_whisper"),
            FeatureRecord(session_id=session_id, window_index=window_index,
                          name="voice_energy", value=voice_energy,
                          source=FeatureSource.AUDIO, quality=q,
                          pipeline_version=pipeline_version, extractor="faster_whisper"),
        ]


feature_store = FeatureStore()
