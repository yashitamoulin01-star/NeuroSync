"""
Regression Gate — deployment blocking based on metric comparison.

Before deploying a new model version, run this gate.
If the new model regresses on any critical metric beyond the configured
threshold, deployment is blocked automatically.

This prevents "silent regressions" — cases where a new model looks
good in isolation but is measurably worse than the version it replaces.

Usage:
    gate = RegressionGate()
    result = gate.evaluate(baseline_metrics, candidate_metrics)
    if not result.passed:
        # Do NOT deploy
        logger.warning("Regression gate blocked: %s", result.failures)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from backend.ai.configuration.ai_config import ai_config


@dataclass
class GateCheck:
    """One individual metric check."""
    metric:       str
    baseline:     Optional[float]
    candidate:    Optional[float]
    threshold:    float
    delta:        Optional[float]
    passed:       bool
    reason:       str


@dataclass
class RegressionGateResult:
    """Aggregate result of all gate checks."""
    model_name:      str
    baseline_version: str
    candidate_version: str
    passed:          bool
    checks:          List[GateCheck] = field(default_factory=list)
    failures:        List[str]       = field(default_factory=list)
    warnings:        List[str]       = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "model_name":         self.model_name,
            "baseline_version":   self.baseline_version,
            "candidate_version":  self.candidate_version,
            "passed":             self.passed,
            "failure_count":      len(self.failures),
            "warning_count":      len(self.warnings),
            "failures":           self.failures,
            "warnings":           self.warnings,
            "checks": [
                {
                    "metric":    c.metric,
                    "baseline":  round(c.baseline, 4) if c.baseline is not None else None,
                    "candidate": round(c.candidate, 4) if c.candidate is not None else None,
                    "threshold": c.threshold,
                    "delta":     round(c.delta, 4) if c.delta is not None else None,
                    "passed":    c.passed,
                    "reason":    c.reason,
                }
                for c in self.checks
            ],
        }


class RegressionGate:
    """
    Compares baseline vs candidate model metrics and blocks regression.

    Thresholds come from ai_config.regression so they're centrally managed.
    """

    def evaluate(
        self,
        model_name:        str,
        baseline_version:  str,
        candidate_version: str,
        baseline_metrics:  Dict,
        candidate_metrics: Dict,
    ) -> RegressionGateResult:
        cfg = ai_config.regression
        checks: List[GateCheck] = []
        failures: List[str]     = []
        warnings: List[str]     = []

        # ── F1 retention ──────────────────────────────────────────────────────
        b_f1 = baseline_metrics.get("macro_f1")
        c_f1 = candidate_metrics.get("macro_f1")
        if b_f1 is not None and c_f1 is not None:
            delta   = c_f1 - b_f1
            min_f1  = b_f1 * cfg.min_f1_retention
            passed  = c_f1 >= min_f1
            reason  = (
                f"F1 retained ({c_f1:.4f} ≥ {min_f1:.4f})"
                if passed
                else f"F1 dropped below retention floor ({c_f1:.4f} < {min_f1:.4f})"
            )
            check = GateCheck(
                metric="macro_f1", baseline=b_f1, candidate=c_f1,
                threshold=cfg.min_f1_retention, delta=delta,
                passed=passed, reason=reason,
            )
            checks.append(check)
            if not passed:
                failures.append(f"FAIL macro_f1: {reason}")

        # ── Average confidence score ──────────────────────────────────────────
        b_conf = baseline_metrics.get("avg_confidence")
        c_conf = candidate_metrics.get("avg_confidence")
        if b_conf is not None and c_conf is not None:
            delta  = b_conf - c_conf    # positive = regression
            passed = delta <= cfg.max_confidence_delta
            reason = (
                f"Confidence within tolerance (dropped {delta:.4f} ≤ {cfg.max_confidence_delta})"
                if passed
                else f"Confidence regressed by {delta:.4f} > {cfg.max_confidence_delta}"
            )
            check = GateCheck(
                metric="avg_confidence", baseline=b_conf, candidate=c_conf,
                threshold=cfg.max_confidence_delta, delta=delta,
                passed=passed, reason=reason,
            )
            checks.append(check)
            if not passed:
                failures.append(f"FAIL avg_confidence: {reason}")

        # ── Stress score (lower is better — high stress = bad) ────────────────
        b_stress = baseline_metrics.get("avg_stress")
        c_stress = candidate_metrics.get("avg_stress")
        if b_stress is not None and c_stress is not None:
            delta  = c_stress - b_stress    # positive = regression
            passed = delta <= cfg.max_stress_delta
            reason = (
                f"Stress within tolerance (rose {delta:.4f} ≤ {cfg.max_stress_delta})"
                if passed
                else f"Stress regressed by {delta:.4f} > {cfg.max_stress_delta}"
            )
            check = GateCheck(
                metric="avg_stress", baseline=b_stress, candidate=c_stress,
                threshold=cfg.max_stress_delta, delta=delta,
                passed=passed, reason=reason,
            )
            checks.append(check)
            if not passed:
                failures.append(f"FAIL avg_stress: {reason}")

        # ── P95 latency ───────────────────────────────────────────────────────
        b_lat = baseline_metrics.get("inference_p95_ms")
        c_lat = candidate_metrics.get("inference_p95_ms")
        if b_lat is not None and c_lat is not None:
            delta  = c_lat - b_lat
            passed = delta <= cfg.max_latency_increase_ms
            reason = (
                f"Latency within tolerance (+{delta:.1f}ms ≤ {cfg.max_latency_increase_ms}ms)"
                if passed
                else f"Latency regressed by {delta:.1f}ms > {cfg.max_latency_increase_ms}ms"
            )
            check = GateCheck(
                metric="inference_p95_ms", baseline=b_lat, candidate=c_lat,
                threshold=cfg.max_latency_increase_ms, delta=delta,
                passed=passed, reason=reason,
            )
            checks.append(check)
            if not passed:
                warnings.append(f"WARN inference_p95_ms: {reason}")   # latency is warning not blocker

        # ── ECE (lower is better) ─────────────────────────────────────────────
        b_ece = baseline_metrics.get("ece")
        c_ece = candidate_metrics.get("ece")
        if b_ece is not None and c_ece is not None:
            delta  = c_ece - b_ece
            passed = delta <= 0.05    # allow 5% ECE increase
            reason = (
                f"Calibration within tolerance (ECE delta {delta:.4f} ≤ 0.05)"
                if passed
                else f"Calibration degraded (ECE rose {delta:.4f} > 0.05)"
            )
            check = GateCheck(
                metric="ece", baseline=b_ece, candidate=c_ece,
                threshold=0.05, delta=delta,
                passed=passed, reason=reason,
            )
            checks.append(check)
            if not passed:
                warnings.append(f"WARN ece: {reason}")

        gate_passed = len(failures) == 0
        return RegressionGateResult(
            model_name        = model_name,
            baseline_version  = baseline_version,
            candidate_version = candidate_version,
            passed            = gate_passed,
            checks            = checks,
            failures          = failures,
            warnings          = warnings,
        )


regression_gate = RegressionGate()
