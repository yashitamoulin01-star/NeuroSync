"""
Offline Replay Engine — re-run the reasoning pipeline on recorded session data.

Instead of conducting a new interview, load a recorded session's feature history
and replay it through the current pipeline version. This enables:

  - Debugging: "why did session X score 0.31 confidence in window 8?"
  - Model comparison: "what would v2 have scored on the same session?"
  - Pipeline validation: determinism check (same input → same output)
  - Regression detection: run all sessions from last week through new pipeline

The replay engine is a pure computation engine — no I/O, no WebSockets.
It reads stored FeatureStore batches and runs them through the reasoning pipeline.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReplayFrame:
    """One replayed analytics window."""
    window_index:    int
    timestamp:       float
    original_scores: Dict[str, float]
    replayed_scores: Dict[str, float]
    score_deltas:    Dict[str, float]    # replayed - original
    reliability:     str
    evidence_count:  int


@dataclass
class ReplayReport:
    """Full replay of one recorded session."""
    session_id:        str
    original_version:  str
    replay_version:    str
    total_windows:     int
    replayed_windows:  int
    duration_ms:       float
    frames:            List[ReplayFrame] = field(default_factory=list)
    max_score_delta:   float = 0.0
    avg_score_delta:   float = 0.0
    is_deterministic:  bool  = True   # True if replayed scores match originals exactly

    def to_dict(self) -> Dict:
        return {
            "session_id":       self.session_id,
            "original_version": self.original_version,
            "replay_version":   self.replay_version,
            "total_windows":    self.total_windows,
            "replayed_windows": self.replayed_windows,
            "duration_ms":      round(self.duration_ms, 1),
            "max_score_delta":  round(self.max_score_delta, 4),
            "avg_score_delta":  round(self.avg_score_delta, 4),
            "is_deterministic": self.is_deterministic,
            "frames": [
                {
                    "window_index":    f.window_index,
                    "original_scores": {k: round(v, 4) for k, v in f.original_scores.items()},
                    "replayed_scores": {k: round(v, 4) for k, v in f.replayed_scores.items()},
                    "score_deltas":    {k: round(v, 4) for k, v in f.score_deltas.items()},
                    "reliability":     f.reliability,
                    "evidence_count":  f.evidence_count,
                }
                for f in self.frames
            ],
        }


class ReplayEngine:
    """
    Replays a recorded session through the reasoning pipeline.

    Input: session_id whose FeatureStore batches are available.
    Output: ReplayReport comparing original vs replayed scores.
    """

    def __init__(self, pipeline_version: str = "3.0.0") -> None:
        self._pipeline_version = pipeline_version

    def replay_session(
        self,
        session_id:         str,
        original_analytics: List[Dict],    # list of FusedAnalytics.model_dump() records
        original_version:   str = "unknown",
    ) -> ReplayReport:
        """
        Replay a session using stored analytics records.

        This re-runs the raw scoring (not the full 13-stage pipeline, which
        requires live modality data) using the evidence and quality info
        stored in each analytics frame.
        """
        from backend.reasoning.reasoner import reasoner

        t0 = time.perf_counter()
        frames: List[ReplayFrame] = []
        all_deltas: List[float] = []

        for i, frame_dict in enumerate(original_analytics):
            try:
                # Extract stored evidence (if available)
                evidence_list = frame_dict.get("evidence", [])
                dq = frame_dict.get("data_quality")

                if not evidence_list or not dq:
                    continue

                # Reconstruct evidence objects
                from backend.models.evidence import (
                    BehavioralEvidence, EvidenceDimension, EvidencePolarity, ModalityQuality,
                )
                evidence = []
                for ev_dict in evidence_list:
                    try:
                        evidence.append(BehavioralEvidence(
                            id                = ev_dict.get("id", f"r{i}"),
                            dimension         = EvidenceDimension(ev_dict["dimension"]),
                            polarity          = EvidencePolarity(ev_dict["polarity"]),
                            description       = ev_dict.get("description", ""),
                            source_modalities = ev_dict.get("source_modalities", []),
                            contribution      = ev_dict.get("contribution", 0.2),
                        ))
                    except Exception:
                        continue

                quality = ModalityQuality(
                    face_available  = dq.get("face_available", False),
                    face_quality    = dq.get("face_quality", 0.0),
                    audio_available = dq.get("audio_available", False),
                    audio_quality   = dq.get("audio_quality", 0.0),
                    nlp_available   = dq.get("nlp_available", False),
                    nlp_quality     = dq.get("nlp_quality", 0.0),
                    transcript_words = dq.get("transcript_words", 0),
                    evidence_coverage = dq.get("evidence_coverage", 0.5),
                )

                breakdown = reasoner.reason(
                    evidence         = evidence,
                    quality          = quality,
                    session_duration = frame_dict.get("session_duration", 120.0),
                    total_words      = frame_dict.get("total_words_spoken", 0),
                )

                original_scores = {
                    "confidence":    frame_dict.get("overall_confidence", 0.0),
                    "stress":        frame_dict.get("stress_level", 0.0),
                    "communication": frame_dict.get("communication_quality", 0.0),
                    "engagement":    frame_dict.get("engagement_score", 0.0),
                    "consistency":   frame_dict.get("behavioral_consistency", 0.0),
                }
                replayed_scores = {
                    "confidence":    breakdown.confidence,
                    "stress":        breakdown.stress,
                    "communication": breakdown.communication,
                    "engagement":    breakdown.engagement,
                    "consistency":   breakdown.consistency,
                }
                deltas = {
                    k: round(replayed_scores[k] - original_scores[k], 4)
                    for k in original_scores
                }
                max_delta = max(abs(v) for v in deltas.values())
                all_deltas.append(max_delta)

                frames.append(ReplayFrame(
                    window_index    = i,
                    timestamp       = frame_dict.get("timestamp", 0.0),
                    original_scores = original_scores,
                    replayed_scores = replayed_scores,
                    score_deltas    = deltas,
                    reliability     = breakdown.reliability.value,
                    evidence_count  = breakdown.evidence_count,
                ))

            except Exception as e:
                logger.warning("Replay frame %d error: %s", i, e)

        duration_ms = (time.perf_counter() - t0) * 1000
        max_delta = max(all_deltas) if all_deltas else 0.0
        avg_delta = sum(all_deltas) / len(all_deltas) if all_deltas else 0.0

        return ReplayReport(
            session_id       = session_id,
            original_version = original_version,
            replay_version   = self._pipeline_version,
            total_windows    = len(original_analytics),
            replayed_windows = len(frames),
            duration_ms      = duration_ms,
            frames           = frames,
            max_score_delta  = max_delta,
            avg_score_delta  = avg_delta,
            is_deterministic = max_delta < 0.001,
        )


replay_engine = ReplayEngine()
