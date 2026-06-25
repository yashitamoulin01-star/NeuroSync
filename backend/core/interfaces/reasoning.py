"""
IReasoningEngine — contract for the behavioral reasoning layer.

Any reasoning implementation must satisfy this interface, enabling
mocking in tests and future engine swaps without touching business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from backend.models.evidence import (
    BehavioralEvidence,
    ModalityQuality,
    ScoreBreakdown,
)


class IReasoningEngine(ABC):
    """
    Converts a pool of behavioral evidence into calibrated per-dimension scores.

    Implementations must be deterministic for the same input.
    """

    @abstractmethod
    def reason(
        self,
        evidence:         List[BehavioralEvidence],
        quality:          ModalityQuality,
        session_duration: float = 0.0,
        total_words:      int   = 0,
    ) -> ScoreBreakdown:
        """
        Produce a ScoreBreakdown from the current evidence pool.

        Args:
            evidence:         All behavioral evidence items for this window.
            quality:          Per-modality availability and signal strength.
            session_duration: Total elapsed session time in seconds.
            total_words:      Cumulative words spoken so far.

        Returns:
            ScoreBreakdown with calibrated scores, reliability, and coverage.
        """
        ...
