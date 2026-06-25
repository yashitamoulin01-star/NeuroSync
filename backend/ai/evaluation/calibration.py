"""
Calibration Evaluator — Expected Calibration Error (ECE), Brier Score,
reliability curves.

A well-calibrated model that claims 80% confidence should be correct
approximately 80% of the time. A model that's overconfident claims 90%
when it should claim 60%.

ECE measures this gap:
  ECE = Σ (|Bk| / N) * |acc(Bk) - conf(Bk)|
  where Bk = bins of predictions grouped by confidence level

Brier Score measures the mean squared error of probability predictions:
  BS = (1/N) Σ (f_t - o_t)²
  Perfect score: 0.0 | Worst: 1.0

These metrics matter because:
  - A perfectly accurate model that claims 99% confidence on everything
    looks great on F1 but is uncalibrated and untrustworthy
  - Calibration score determines whether users can trust confidence levels
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class CalibrationBin:
    """One bin in a reliability diagram."""
    bin_idx:    int
    lower:      float
    upper:      float
    count:      int
    avg_confidence: float
    avg_accuracy:   float
    gap:        float   # |accuracy - confidence|

    def to_dict(self) -> Dict:
        return {
            "bin":          f"{self.lower:.1f}–{self.upper:.1f}",
            "count":        self.count,
            "avg_confidence": round(self.avg_confidence, 4),
            "avg_accuracy":   round(self.avg_accuracy, 4),
            "gap":            round(self.gap, 4),
        }


@dataclass
class CalibrationReport:
    """Full calibration evaluation result."""
    n_samples:    int
    n_bins:       int
    ece:          float             # Expected Calibration Error (lower is better)
    brier_score:  float             # Mean squared probability error (lower is better)
    mce:          float             # Maximum Calibration Error
    overconfidence_fraction: float  # fraction of bins where model is overconfident
    bins:         List[CalibrationBin] = field(default_factory=list)

    interpretation: str = ""        # human-readable summary

    def to_dict(self) -> Dict:
        return {
            "n_samples":    self.n_samples,
            "n_bins":       self.n_bins,
            "ece":          round(self.ece, 4),
            "brier_score":  round(self.brier_score, 4),
            "mce":          round(self.mce, 4),
            "overconfidence_fraction": round(self.overconfidence_fraction, 3),
            "interpretation": self.interpretation,
            "reliability_diagram": [b.to_dict() for b in self.bins],
        }


def compute_ece(
    confidences: List[float],
    correct:     List[bool],
    n_bins:      int = 10,
) -> CalibrationReport:
    """
    Compute Expected Calibration Error and Brier Score.

    Args:
        confidences: Model's predicted confidence for each sample [0, 1].
        correct:     Whether each prediction was actually correct.
        n_bins:      Number of bins for the reliability diagram (default 10).

    Returns:
        CalibrationReport with ECE, Brier Score, reliability diagram.

    Example:
        confidences = [0.9, 0.8, 0.7, 0.6, 0.5]
        correct     = [True, True, False, True, False]
        report = compute_ece(confidences, correct)
    """
    if len(confidences) != len(correct):
        raise ValueError("confidences and correct must have the same length")
    if len(confidences) == 0:
        return CalibrationReport(
            n_samples=0, n_bins=n_bins, ece=0.0, brier_score=0.0,
            mce=0.0, overconfidence_fraction=0.0,
            interpretation="No samples provided",
        )

    n = len(confidences)
    bin_width = 1.0 / n_bins
    bins: List[CalibrationBin] = []

    ece = 0.0
    mce = 0.0
    overconfident_bins = 0

    for i in range(n_bins):
        lo = i * bin_width
        hi = lo + bin_width
        indices = [
            j for j, c in enumerate(confidences)
            if lo <= c < hi or (i == n_bins - 1 and c == 1.0)
        ]
        if not indices:
            continue

        bin_conf = sum(confidences[j] for j in indices) / len(indices)
        bin_acc  = sum(1 for j in indices if correct[j]) / len(indices)
        gap      = abs(bin_acc - bin_conf)

        ece += (len(indices) / n) * gap
        mce = max(mce, gap)

        if bin_conf > bin_acc:
            overconfident_bins += 1

        bins.append(CalibrationBin(
            bin_idx         = i,
            lower           = lo,
            upper           = hi,
            count           = len(indices),
            avg_confidence  = bin_conf,
            avg_accuracy    = bin_acc,
            gap             = gap,
        ))

    # Brier Score: mean squared error of probabilities
    brier_score = sum(
        (c - (1.0 if ok else 0.0)) ** 2
        for c, ok in zip(confidences, correct)
    ) / n

    overconfidence_frac = overconfident_bins / max(len(bins), 1)

    # Interpretation
    if ece < 0.05:
        interp = "Excellent calibration — model confidence closely matches observed accuracy."
    elif ece < 0.10:
        interp = "Good calibration — minor gaps between confidence and accuracy."
    elif ece < 0.20:
        interp = "Moderate miscalibration — consider temperature scaling or Platt scaling."
    else:
        interp = "Poor calibration — model confidence is unreliable. Calibration required."

    return CalibrationReport(
        n_samples               = n,
        n_bins                  = n_bins,
        ece                     = ece,
        brier_score             = brier_score,
        mce                     = mce,
        overconfidence_fraction = overconfidence_frac,
        bins                    = bins,
        interpretation          = interp,
    )


def compute_reliability_curve(
    confidences: List[float],
    correct:     List[bool],
    n_bins:      int = 10,
) -> List[Tuple[float, float]]:
    """
    Return (mean_confidence, fraction_correct) pairs for plotting.

    This is the data behind a reliability diagram — a calibrated model
    should produce points that lie close to the diagonal y=x.
    """
    report = compute_ece(confidences, correct, n_bins)
    return [(b.avg_confidence, b.avg_accuracy) for b in report.bins]
