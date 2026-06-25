"""
Unit tests for the Temporal Reasoning Engine — Phase 3.
"""

from __future__ import annotations

import pytest

from backend.reasoning.timeline.temporal_engine import (
    ScoreSnapshot,
    TemporalAnalysis,
    Trend,
    analyze_temporal,
)


def _snapshot(i: int, elapsed: float, confidence: float, stress: float = 0.4,
              communication: float = 0.6, engagement: float = 0.55,
              consistency: float = 0.65) -> ScoreSnapshot:
    return ScoreSnapshot(
        window_index=i,
        elapsed_seconds=elapsed,
        confidence=confidence,
        stress=stress,
        communication=communication,
        engagement=engagement,
        consistency=consistency,
        reliability="medium",
    )


class TestAnalyzeTemporal:

    def test_empty_returns_stable(self):
        result = analyze_temporal([])
        assert result.pattern in ("stable", "insufficient_data", "settling")

    def test_single_snapshot(self):
        result = analyze_temporal([_snapshot(0, 10.0, 0.6)])
        assert isinstance(result, TemporalAnalysis)

    def test_rising_confidence_trend(self):
        snapshots = [_snapshot(i, i * 20.0, 0.30 + i * 0.06) for i in range(10)]
        result = analyze_temporal(snapshots)
        assert result.trends.get("confidence") == Trend.INCREASING.value

    def test_falling_confidence_trend(self):
        snapshots = [_snapshot(i, i * 20.0, 0.90 - i * 0.06) for i in range(10)]
        result = analyze_temporal(snapshots)
        assert result.trends.get("confidence") == Trend.DECREASING.value

    def test_stable_trend(self):
        snapshots = [_snapshot(i, i * 20.0, 0.65 + (0.01 if i % 2 else -0.01))
                     for i in range(15)]
        result = analyze_temporal(snapshots)
        assert result.trends.get("confidence") == Trend.STABLE.value

    def test_segment_introduction(self):
        snapshots = [_snapshot(i, i * 5.0, 0.6) for i in range(5)]   # < 60s
        result = analyze_temporal(snapshots)
        assert result.segment in ("introduction", "warming_up", "background")

    def test_segment_closing(self):
        snapshots = [_snapshot(i, 2400.0 + i * 30.0, 0.6) for i in range(5)]
        result = analyze_temporal(snapshots)
        assert result.segment in ("closing", "wrap_up")

    def test_window_count(self):
        snapshots = [_snapshot(i, i * 15.0, 0.6) for i in range(7)]
        result = analyze_temporal(snapshots)
        assert result.window_count == 7

    def test_slope_confidence_bounded(self):
        snapshots = [_snapshot(i, i * 20.0, 0.6 + i * 0.01) for i in range(10)]
        result = analyze_temporal(snapshots)
        assert 0.0 <= result.slope_confidence <= 1.0
