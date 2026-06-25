"""
Temporal Reasoning Engine — analyzes behavioral patterns over the interview timeline.

Instead of reasoning only about the current window, this module reasons over the
entire session history, detecting trends, patterns, and interview segments.

Human interviewers notice trends. Increasing confidence is qualitatively different
from a flat 63% average. This module gives the backend that same capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Trend(str, Enum):
    INCREASING   = "increasing"
    DECREASING   = "decreasing"
    STABLE       = "stable"
    VOLATILE     = "volatile"
    RECOVERING   = "recovering"
    INSUFFICIENT = "insufficient_data"


class BehavioralPattern(str, Enum):
    IMPROVING    = "improving"
    DECLINING    = "declining"
    STABLE       = "stable"
    RECOVERING   = "recovering"
    FATIGUING    = "fatiguing"
    SETTLING     = "settling"
    INCONSISTENT = "inconsistent"


@dataclass
class ScoreSnapshot:
    """Lightweight per-window score record stored in session history."""
    window_index:    int
    elapsed_seconds: float
    confidence:      float
    stress:          float
    communication:   float
    engagement:      float
    consistency:     float
    reliability:     str


@dataclass
class TemporalAnalysis:
    trends:          Dict[str, str]  # dimension → Trend.value
    pattern:         str             # BehavioralPattern.value
    segment:         str             # interview segment name
    slope_confidence: float          # 0–1, how reliable the trend estimate is
    window_count:    int


# ── Private helpers ───────────────────────────────────────────────────────────

def _slope(values: List[float]) -> float:
    """OLS slope per window. Positive = increasing."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den > 0 else 0.0


def _variance(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def _classify_trend(values: List[float]) -> Trend:
    if len(values) < 3:
        return Trend.INSUFFICIENT
    s   = _slope(values)
    var = _variance(values)

    if abs(s) < 0.015 and var < 0.025:
        return Trend.STABLE
    if var > 0.05:
        return Trend.VOLATILE
    if s > 0.015:
        mid = len(values) // 2
        # U-shape (low→lower→higher) = recovery
        if values[0] > values[mid] and values[mid] < values[-1]:
            return Trend.RECOVERING
        return Trend.INCREASING
    if s < -0.015:
        return Trend.DECREASING
    return Trend.STABLE


def _detect_pattern(snapshots: List[ScoreSnapshot]) -> BehavioralPattern:
    if len(snapshots) < 3:
        return BehavioralPattern.SETTLING

    conf  = [s.confidence  for s in snapshots]
    stress= [s.stress      for s in snapshots]
    eng   = [s.engagement  for s in snapshots]
    con   = [s.consistency for s in snapshots]

    conf_t  = _classify_trend(conf)
    stress_t= _classify_trend(stress)
    eng_t   = _classify_trend(eng)
    con_t   = _classify_trend(con)

    # Recovery: confidence was dipping, now rising AND stress dropping
    if conf_t in (Trend.RECOVERING, Trend.INCREASING) and stress_t in (
        Trend.DECREASING, Trend.RECOVERING
    ):
        return BehavioralPattern.RECOVERING

    # Clearly improving
    if conf_t == Trend.INCREASING and stress_t in (Trend.STABLE, Trend.DECREASING):
        return BehavioralPattern.IMPROVING

    # Clearly declining
    if conf_t == Trend.DECREASING and stress_t == Trend.INCREASING:
        return BehavioralPattern.DECLINING

    # Late-session fatigue (only after enough windows)
    if len(snapshots) > 6 and (eng_t == Trend.DECREASING or con_t == Trend.DECREASING):
        return BehavioralPattern.FATIGUING

    if conf_t == Trend.VOLATILE or stress_t == Trend.VOLATILE:
        return BehavioralPattern.INCONSISTENT

    if conf_t == Trend.STABLE:
        return BehavioralPattern.STABLE

    return BehavioralPattern.SETTLING


def _segment(elapsed: float) -> str:
    """Heuristic interview segment from elapsed time."""
    if elapsed < 60:   return "introduction"
    if elapsed < 180:  return "background"
    if elapsed < 420:  return "technical_discussion"
    if elapsed < 720:  return "problem_solving"
    if elapsed < 1200: return "system_design"
    return "closing"


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_temporal(snapshots: List[ScoreSnapshot]) -> TemporalAnalysis:
    """Full temporal analysis from the session's score history."""
    _none = {d: Trend.INSUFFICIENT.value
             for d in ("confidence","stress","communication","engagement","consistency")}

    if not snapshots:
        return TemporalAnalysis(
            trends=_none, pattern=BehavioralPattern.SETTLING.value,
            segment="introduction", slope_confidence=0.0, window_count=0,
        )

    dims = {
        "confidence":    [s.confidence    for s in snapshots],
        "stress":        [s.stress        for s in snapshots],
        "communication": [s.communication for s in snapshots],
        "engagement":    [s.engagement    for s in snapshots],
        "consistency":   [s.consistency   for s in snapshots],
    }

    trends  = {dim: _classify_trend(vals).value for dim, vals in dims.items()}
    pattern = _detect_pattern(snapshots)
    n       = len(snapshots)
    elapsed = snapshots[-1].elapsed_seconds if snapshots else 0.0

    return TemporalAnalysis(
        trends           = trends,
        pattern          = pattern.value,
        segment          = _segment(elapsed),
        slope_confidence = round(min(1.0, n / 10.0), 3),
        window_count     = n,
    )
