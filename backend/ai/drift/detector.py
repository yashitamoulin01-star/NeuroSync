"""
Drift Detector — statistical feature distribution monitoring.

Detects when the distribution of incoming features shifts significantly
from the training distribution. Uses two complementary statistics:

Population Stability Index (PSI) — industry standard for credit scoring:
    PSI = Σ (actual% - expected%) * ln(actual% / expected%)
    < 0.10: no change  |  0.10–0.25: monitor  |  > 0.25: investigate

KL Divergence — information-theoretic measurement of distribution shift:
    KL(P||Q) = Σ P(i) * log(P(i) / Q(i))
    Asymmetric: how much information is lost when Q approximates P.

Both statistics operate on continuous features by bucketing into bins.
Categorical features use normalized frequency comparison.

Why this matters:
  If interview candidates in production differ significantly from the
  training data (different age group, different cultural communication
  patterns, different interview format), model accuracy degrades silently.
  Drift detection catches this before it impacts hiring decisions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from backend.ai.configuration.ai_config import ai_config


@dataclass
class DriftResult:
    """Result of a drift test for one feature."""
    feature_name: str
    psi:          float
    kl_divergence: float
    n_reference:  int
    n_current:    int
    n_bins:       int
    status:       str         # "no_change" | "monitor" | "warning" | "critical"
    message:      str

    def to_dict(self) -> Dict:
        return {
            "feature_name":  self.feature_name,
            "psi":           round(self.psi, 4),
            "kl_divergence": round(self.kl_divergence, 4),
            "n_reference":   self.n_reference,
            "n_current":     self.n_current,
            "n_bins":        self.n_bins,
            "status":        self.status,
            "message":       self.message,
        }


@dataclass
class DriftReport:
    """Aggregate drift report across all monitored features."""
    features:       List[DriftResult] = field(default_factory=list)
    critical_count: int = 0
    warning_count:  int = 0
    monitor_count:  int = 0
    overall_status: str = "no_change"

    def to_dict(self) -> Dict:
        return {
            "overall_status": self.overall_status,
            "critical_count": self.critical_count,
            "warning_count":  self.warning_count,
            "monitor_count":  self.monitor_count,
            "feature_count":  len(self.features),
            "features":       [f.to_dict() for f in self.features],
        }


def _make_bins(
    values: List[float],
    n_bins: int,
    lo: Optional[float] = None,
    hi: Optional[float] = None,
) -> Tuple[List[float], List[float]]:
    """Bin continuous values, returning (edges, counts)."""
    if not values:
        return [0.0, 1.0], [0.0]
    lo = lo if lo is not None else min(values)
    hi = hi if hi is not None else max(values)
    if lo == hi:
        hi = lo + 1e-9
    bin_width = (hi - lo) / n_bins
    edges = [lo + i * bin_width for i in range(n_bins + 1)]
    counts = [0.0] * n_bins
    for v in values:
        idx = int((v - lo) / bin_width)
        idx = min(idx, n_bins - 1)
        counts[idx] += 1
    return edges, counts


def _normalize(counts: List[float], epsilon: float = 1e-6) -> List[float]:
    total = sum(counts) + epsilon
    return [(c + epsilon) / (total + epsilon * len(counts)) for c in counts]


def compute_psi(
    reference: List[float],
    current:   List[float],
    n_bins:    int = 10,
) -> float:
    """
    Population Stability Index between reference and current distributions.

    Standard thresholds:
        < 0.10  → no significant change
        0.10–0.25 → moderate change, investigate
        > 0.25  → significant change, model likely degraded
    """
    if len(reference) < 5 or len(current) < 5:
        return 0.0

    lo = min(min(reference), min(current))
    hi = max(max(reference), max(current))

    _, ref_counts = _make_bins(reference, n_bins, lo, hi)
    _, cur_counts = _make_bins(current,   n_bins, lo, hi)

    ref_pct = _normalize(ref_counts)
    cur_pct = _normalize(cur_counts)

    psi = sum(
        (c - r) * math.log(c / r)
        for r, c in zip(ref_pct, cur_pct)
    )
    return max(0.0, psi)


def compute_kl_divergence(
    reference: List[float],
    current:   List[float],
    n_bins:    int = 10,
) -> float:
    """
    KL divergence KL(current || reference).

    Measures information lost when using reference to approximate current.
    Asymmetric: KL(P||Q) ≠ KL(Q||P)
    """
    if len(reference) < 5 or len(current) < 5:
        return 0.0

    lo = min(min(reference), min(current))
    hi = max(max(reference), max(current))

    _, ref_counts = _make_bins(reference, n_bins, lo, hi)
    _, cur_counts = _make_bins(current,   n_bins, lo, hi)

    ref_pct = _normalize(ref_counts)
    cur_pct = _normalize(cur_counts)

    kl = sum(
        c * math.log(c / r)
        for r, c in zip(ref_pct, cur_pct)
        if c > 0
    )
    return max(0.0, kl)


class DriftDetector:
    """
    Monitors feature distributions and raises drift alerts.

    Usage:
        detector = DriftDetector()
        detector.set_reference("eye_contact_score", training_values)
        detector.update("eye_contact_score", production_values)
        report = detector.detect()
    """

    def __init__(self, n_bins: int = 10) -> None:
        self._reference: Dict[str, List[float]] = {}
        self._current:   Dict[str, List[float]] = {}
        self._n_bins = n_bins
        self._cfg = ai_config.drift

    def set_reference(self, feature_name: str, values: List[float]) -> None:
        """Set the training/baseline distribution for a feature."""
        self._reference[feature_name] = list(values)
        self._current.setdefault(feature_name, [])

    def update(self, feature_name: str, values: List[float]) -> None:
        """Append new production values for a feature."""
        if feature_name not in self._current:
            self._current[feature_name] = []
        self._current[feature_name].extend(values)

    def detect_feature(self, feature_name: str) -> Optional[DriftResult]:
        ref = self._reference.get(feature_name, [])
        cur = self._current.get(feature_name, [])

        if len(ref) < self._cfg.min_samples_for_drift:
            return None
        if len(cur) < self._cfg.min_samples_for_drift:
            return None

        psi = compute_psi(ref, cur, self._n_bins)
        kl  = compute_kl_divergence(ref, cur, self._n_bins)

        # Classify
        if psi > self._cfg.psi_moderate or kl > self._cfg.kl_critical:
            status  = "critical"
            message = f"Significant distribution shift detected (PSI={psi:.3f}, KL={kl:.3f}). Investigate and consider retraining."
        elif psi > self._cfg.psi_no_change or kl > self._cfg.kl_warning:
            status  = "warning"
            message = f"Moderate distribution shift (PSI={psi:.3f}, KL={kl:.3f}). Monitor closely."
        elif psi > self._cfg.psi_no_change / 2:
            status  = "monitor"
            message = f"Minor distribution shift (PSI={psi:.3f}, KL={kl:.3f}). No action needed yet."
        else:
            status  = "no_change"
            message = f"Distribution stable (PSI={psi:.3f}, KL={kl:.3f})."

        return DriftResult(
            feature_name  = feature_name,
            psi           = psi,
            kl_divergence = kl,
            n_reference   = len(ref),
            n_current     = len(cur),
            n_bins        = self._n_bins,
            status        = status,
            message       = message,
        )

    def detect(self) -> DriftReport:
        """Run drift detection across all monitored features."""
        results: List[DriftResult] = []
        for name in self._reference:
            r = self.detect_feature(name)
            if r:
                results.append(r)

        critical = sum(1 for r in results if r.status == "critical")
        warning  = sum(1 for r in results if r.status == "warning")
        monitor  = sum(1 for r in results if r.status == "monitor")

        if critical:
            overall = "critical"
        elif warning:
            overall = "warning"
        elif monitor:
            overall = "monitor"
        else:
            overall = "no_change"

        return DriftReport(
            features       = results,
            critical_count = critical,
            warning_count  = warning,
            monitor_count  = monitor,
            overall_status = overall,
        )

    def reset_current(self, feature_name: Optional[str] = None) -> None:
        if feature_name:
            self._current[feature_name] = []
        else:
            self._current = {k: [] for k in self._current}


drift_detector = DriftDetector()
