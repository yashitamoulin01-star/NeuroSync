"""
Reasoning Observability — internal metrics that demonstrate production maturity.

These metrics are not behavioral scores. They measure the reasoning engine itself:
how fast it is, how often it detects conflicts, how much evidence it generates,
how confident it is in its own conclusions on average.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ReasoningMetrics:
    session_id:                    str   = ""
    total_windows:                 int   = 0
    total_evidence_generated:      int   = 0
    total_conflicts_detected:      int   = 0
    total_missing_modality_events: int   = 0
    calibration_adjustments:       int   = 0
    rules_fired_count:             int   = 0
    state_transitions:             int   = 0
    reasoning_latencies_ms:        List[float] = field(default_factory=list)
    prediction_confidences:        List[float] = field(default_factory=list)

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def avg_reasoning_latency_ms(self) -> float:
        if not self.reasoning_latencies_ms:
            return 0.0
        return round(sum(self.reasoning_latencies_ms) / len(self.reasoning_latencies_ms), 2)

    @property
    def avg_prediction_confidence(self) -> float:
        if not self.prediction_confidences:
            return 0.0
        return round(sum(self.prediction_confidences) / len(self.prediction_confidences), 3)

    @property
    def avg_evidence_per_window(self) -> float:
        if self.total_windows == 0:
            return 0.0
        return round(self.total_evidence_generated / self.total_windows, 2)

    # ── Recording ─────────────────────────────────────────────────────────────

    def record_window(
        self,
        evidence_count:       int,
        conflict_count:       int,
        prediction_confidence:float,
        latency_ms:           float,
        rules_fired:          int,
        missing_modalities:   int,
        state_changed:        bool,
        calibration_applied:  bool,
    ) -> None:
        self.total_windows                 += 1
        self.total_evidence_generated      += evidence_count
        self.total_conflicts_detected      += conflict_count
        self.total_missing_modality_events += missing_modalities
        self.rules_fired_count             += rules_fired
        self.reasoning_latencies_ms.append(latency_ms)
        self.prediction_confidences.append(prediction_confidence)
        if state_changed:
            self.state_transitions += 1
        if calibration_applied:
            self.calibration_adjustments += 1

    def to_dict(self) -> dict:
        return {
            "session_id":                    self.session_id,
            "total_windows":                 self.total_windows,
            "avg_evidence_per_window":       self.avg_evidence_per_window,
            "total_conflicts_detected":      self.total_conflicts_detected,
            "total_missing_modality_events": self.total_missing_modality_events,
            "avg_reasoning_latency_ms":      self.avg_reasoning_latency_ms,
            "avg_prediction_confidence":     self.avg_prediction_confidence,
            "calibration_adjustments":       self.calibration_adjustments,
            "rules_fired_count":             self.rules_fired_count,
            "state_transitions":             self.state_transitions,
        }
