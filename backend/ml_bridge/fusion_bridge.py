"""
Bridge between per-modality services and the multimodal fusion synchronizer.
Keeps fusion logic cleanly separated from the session manager.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ml.fusion.synchronizer import MultimodalSynchronizer
from backend.models.schemas import FaceMetrics, AudioMetrics, NLPMetrics, FusedAnalytics


class FusionBridge:
    def __init__(self, session_id: str = "default", window_seconds: float = 3.0):
        self._sync = MultimodalSynchronizer(
            window_seconds=window_seconds,
            session_id=session_id,
        )

    def push_face(self, metrics: FaceMetrics):
        self._sync.ingest_face(metrics)

    def push_audio(self, metrics: AudioMetrics):
        self._sync.ingest_audio(metrics)

    def push_nlp(self, metrics: NLPMetrics):
        self._sync.ingest_nlp(metrics)

    def get_fused(
        self,
        score_history:    list = None,
        behavioral_state: str  = "warming_up",
        window_index:     int  = 0,
    ) -> FusedAnalytics:
        return self._sync.fuse(
            score_history    = score_history,
            behavioral_state = behavioral_state,
            window_index     = window_index,
        )

    def reset(self, session_id: str = "default"):
        self._sync.reset(new_session_id=session_id)
