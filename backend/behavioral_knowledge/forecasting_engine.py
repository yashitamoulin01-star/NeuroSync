"""
CBIP — Forecasting Engine.

Generates growth trajectory forecasts for individual candidates.

Critically:
  • Forecasts predict BEHAVIOURAL GROWTH only — not hiring outcomes.
  • Every forecast includes confidence intervals derived from historical variance.
  • Forecasts are clearly labelled as projections, not guarantees.
  • At least 3 sessions are required before any projection is made.

Method:
  Ordinary Least Squares on (session_index, dimension_value) pairs from
  the candidate's behavioral_history.  Projects forward by horizon_interviews.
  Confidence interval = projection ± (residual std dev * coverage_factor).
"""

from __future__ import annotations
import logging
import math
from typing import Any, Dict, List, Optional

from backend.behavioral_knowledge.models import DimensionForecast, GrowthForecast

logger = logging.getLogger(__name__)

_MIN_SESSIONS   = 3
_HORIZON        = 3        # sessions to forecast forward
_COVERAGE_COEFF = 1.5      # ≈ 86% prediction interval without scipy dependency

_DIMS = {
    "confidence":    "avg_confidence",
    "engagement":    "avg_engagement",
    "communication": "avg_communication",
    "consistency":   "avg_consistency",
}


def _ols_slope_intercept(xs: List[float], ys: List[float]):
    """Return (slope, intercept) via OLS."""
    n  = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    ss_xx = sum((x - mx) ** 2 for x in xs)
    ss_xy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = ss_xy / ss_xx if ss_xx > 1e-9 else 0.0
    intercept = my - slope * mx
    return slope, intercept


def _residual_std(xs: List[float], ys: List[float], slope: float, intercept: float) -> float:
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    if len(residuals) < 2:
        return 0.05
    mean_r = sum(residuals) / len(residuals)
    var    = sum((r - mean_r) ** 2 for r in residuals) / (len(residuals) - 1)
    return math.sqrt(var)


def _trend_label(slope: float) -> str:
    if slope > 0.005:   return "improving"
    if slope < -0.005:  return "declining"
    return "stable"


def build_growth_forecast(candidate_id: str, history: List[Dict[str, Any]]) -> Optional[GrowthForecast]:
    """
    Build a per-dimension growth forecast from interview history rows.

    history — list of dicts with keys: avg_confidence, avg_engagement,
               avg_communication, avg_consistency, conducted_at.
               Should be ordered DESCENDING (most recent first).
    """
    if len(history) < _MIN_SESSIONS:
        return None

    # Reverse to chronological order for regression
    chron = list(reversed(history))
    xs    = list(range(len(chron)))   # session index 0, 1, 2, ...

    forecasts: List[DimensionForecast] = []
    trajectories: List[str] = []

    for label, key in _DIMS.items():
        ys = [float(row.get(key, 0) or 0) for row in chron]
        if not any(y > 0 for y in ys):
            continue

        slope, intercept = _ols_slope_intercept(xs, ys)
        std              = _residual_std(xs, ys, slope, intercept)
        n_next           = len(xs) + _HORIZON

        pred  = slope * n_next + intercept
        pred  = max(0.0, min(1.0, pred))
        lo    = max(0.0, pred - _COVERAGE_COEFF * std)
        hi    = min(1.0, pred + _COVERAGE_COEFF * std)
        trend = _trend_label(slope)
        trajectories.append(trend)

        forecasts.append(DimensionForecast(
            dimension=label,
            current_value=round(ys[-1], 4),
            predicted_value=round(pred, 4),
            confidence_low=round(lo, 4),
            confidence_high=round(hi, 4),
            horizon_interviews=_HORIZON,
            trend=trend,
        ))

    if not forecasts:
        return None

    improving = sum(1 for t in trajectories if t == "improving")
    declining = sum(1 for t in trajectories if t == "declining")
    if improving > declining:
        overall = "positive"
    elif declining > improving:
        overall = "negative"
    else:
        overall = "neutral"

    n = len(chron)
    if n >= 10:
        note = f"Projection based on {n} interviews — confidence is moderate to high."
    elif n >= 5:
        note = f"Projection based on {n} interviews — treat as indicative."
    else:
        note = f"Early-stage projection from only {n} interviews — high uncertainty."

    return GrowthForecast(
        candidate_id=candidate_id,
        total_interviews=n,
        forecasts=forecasts,
        overall_trajectory=overall,
        confidence_note=note,
    )
