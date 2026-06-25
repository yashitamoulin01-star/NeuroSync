"""
Recommendation Stability Checker.

Small input variations should not produce unstable score swings.
This module measures output stability under Gaussian noise perturbations
applied to raw input signals before evidence extraction.

Methodology:
  1. Run the reasoning pipeline once on the original scenario signals.
  2. Repeat N times with Gaussian noise (±noise_pct) added to each float signal.
  3. Compute per-dimension coefficient of variation (CV = std / mean).
  4. A CV below cv_threshold (default 0.15) indicates stable output.
  5. Track reliability label flips across perturbed runs.

Measures:
  - Behavior stability     — CV per behavioral dimension
  - Recommendation stability — reliability label flip rate
  - Evidence stability     — evidence count variance
  - Calibration stability  — reliability label consistency
  - Report stability       — overall score spread (max - min)
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# A CV below this is "stable" for behavioral scores.
CV_STABLE_THRESHOLD = 0.15

# More than 15% reliability label flips under 5% noise = unstable.
MAX_LABEL_FLIP_RATE = 0.15


@dataclass
class DimensionStability:
    """Stability statistics for one behavioral dimension."""
    dimension:  str
    base_score: float
    min_score:  float
    max_score:  float
    score_range: float      # max - min
    mean:       float
    std_dev:    float
    cv:         float       # coefficient of variation
    is_stable:  bool


@dataclass
class StabilityReport:
    """Aggregated stability results for one scenario."""
    scenario_id:         str
    scenario_name:       str
    n_perturbations:     int
    noise_pct:           float
    cv_threshold:        float
    base_evidence_count: int
    dimensions:          List[DimensionStability] = field(default_factory=list)
    evidence_count_cv:   float = 0.0
    label_flip_rate:     float = 0.0
    overall_stable:      bool  = True
    max_cv:              float = 0.0
    instability_reasons: List[str] = field(default_factory=list)
    duration_ms:         float = 0.0

    def to_dict(self) -> Dict:
        return {
            "scenario_id":          self.scenario_id,
            "scenario_name":        self.scenario_name,
            "n_perturbations":      self.n_perturbations,
            "noise_pct":            self.noise_pct,
            "cv_threshold":         self.cv_threshold,
            "base_evidence_count":  self.base_evidence_count,
            "overall_stable":       self.overall_stable,
            "max_cv":               round(self.max_cv, 4),
            "evidence_count_cv":    round(self.evidence_count_cv, 4),
            "label_flip_rate":      round(self.label_flip_rate, 3),
            "duration_ms":          round(self.duration_ms, 1),
            "instability_reasons":  self.instability_reasons,
            "dimensions": [
                {
                    "dimension":    d.dimension,
                    "base_score":   round(d.base_score, 4),
                    "min":          round(d.min_score, 4),
                    "max":          round(d.max_score, 4),
                    "score_range":  round(d.score_range, 4),
                    "mean":         round(d.mean, 4),
                    "std_dev":      round(d.std_dev, 4),
                    "cv":           round(d.cv, 4),
                    "is_stable":    d.is_stable,
                }
                for d in self.dimensions
            ],
        }


# Signal keys that accept float jitter (boolean/string keys are left unchanged).
_FLOAT_KEYS = frozenset({
    "eye_contact", "head_stability", "voice_energy", "speech_rate_wpm",
    "filler_rate", "clarity_score", "confidence_language",
})


def _jitter_value(value: float, noise_pct: float, rng: random.Random) -> float:
    """Apply zero-mean Gaussian noise, clip to [0, 1]."""
    noise = rng.gauss(0.0, noise_pct * max(value, 0.01))
    return max(0.0, min(1.0, value + noise))


def _jitter_dict(d: Dict, noise_pct: float, rng: random.Random) -> Dict:
    out = {}
    for k, v in d.items():
        if k in _FLOAT_KEYS and isinstance(v, (int, float)):
            out[k] = _jitter_value(float(v), noise_pct, rng)
        else:
            out[k] = v
    return out


class _JitteredScenario:
    """Thin wrapper around jittered signal dicts — duck-types GoldenScenario."""
    __slots__ = (
        "scenario_id", "face_signals", "audio_signals",
        "nlp_signals", "session_duration_s", "total_words",
    )

    def __init__(self, base, face, audio, nlp):
        self.scenario_id       = base.scenario_id
        self.face_signals      = face
        self.audio_signals     = audio
        self.nlp_signals       = nlp
        self.session_duration_s = base.session_duration_s
        self.total_words       = base.total_words


def _stats(values: List[float]):
    n    = len(values)
    mean = sum(values) / n
    var  = sum((x - mean) ** 2 for x in values) / n
    std  = math.sqrt(var)
    cv   = std / mean if mean > 1e-6 else 0.0
    return mean, std, cv


class StabilityChecker:
    """
    Measures NeuroSync output stability under Gaussian input perturbations.

    Usage:
        report = stability_checker.run(scenario)
        suite  = stability_checker.run_suite()
    """

    def __init__(
        self,
        noise_pct:       float = 0.05,   # 5% Gaussian noise per float signal
        n_perturbations: int   = 20,     # number of noisy runs per scenario
        cv_threshold:    float = CV_STABLE_THRESHOLD,
        seed:            int   = 42,     # deterministic by default
    ):
        self.noise_pct       = noise_pct
        self.n_perturbations = n_perturbations
        self.cv_threshold    = cv_threshold
        self.seed            = seed

    def run(self, scenario) -> StabilityReport:
        """Run a full stability check for one scenario."""
        from backend.ai.golden_tests.runner import _build_mock_evidence, _build_mock_quality
        from backend.reasoning.reasoner import reasoner

        rng = random.Random(self.seed)
        t0  = time.perf_counter()

        DIMS = ["confidence", "stress", "communication", "engagement", "consistency"]

        # ── Base run ──────────────────────────────────────────────────────────
        base_ev  = _build_mock_evidence(scenario)
        base_q   = _build_mock_quality(scenario)
        base_bd  = reasoner.reason(
            evidence         = base_ev,
            quality          = base_q,
            session_duration = scenario.session_duration_s,
            total_words      = scenario.total_words,
        )
        base_scores = {
            "confidence":    base_bd.confidence,
            "stress":        base_bd.stress,
            "communication": base_bd.communication,
            "engagement":    base_bd.engagement,
            "consistency":   base_bd.consistency,
        }
        base_reliability    = base_bd.reliability.value
        base_evidence_count = len(base_ev)

        # ── Perturbed runs ────────────────────────────────────────────────────
        perturbed:      Dict[str, List[float]] = {d: [] for d in DIMS}
        evidence_counts: List[int]             = []
        reliability_flips                      = 0

        for _ in range(self.n_perturbations):
            jf = _jitter_dict(scenario.face_signals,  self.noise_pct, rng)
            ja = _jitter_dict(scenario.audio_signals, self.noise_pct, rng)
            jn = _jitter_dict(scenario.nlp_signals,   self.noise_pct, rng)

            js = _JitteredScenario(scenario, jf, ja, jn)
            j_ev = _build_mock_evidence(js)
            j_q  = _build_mock_quality(js)
            j_bd = reasoner.reason(
                evidence         = j_ev,
                quality          = j_q,
                session_duration = scenario.session_duration_s,
                total_words      = scenario.total_words,
            )

            perturbed["confidence"].append(j_bd.confidence)
            perturbed["stress"].append(j_bd.stress)
            perturbed["communication"].append(j_bd.communication)
            perturbed["engagement"].append(j_bd.engagement)
            perturbed["consistency"].append(j_bd.consistency)
            evidence_counts.append(len(j_ev))

            if j_bd.reliability.value != base_reliability:
                reliability_flips += 1

        # ── Aggregate results ─────────────────────────────────────────────────
        dimension_results: List[DimensionStability] = []
        max_cv = 0.0
        instability_reasons: List[str] = []
        overall_stable = True

        for dim in DIMS:
            scores = perturbed[dim]
            mean, std, cv = _stats(scores)
            is_stable = cv < self.cv_threshold
            if not is_stable:
                overall_stable = False
                instability_reasons.append(
                    f"{dim}: CV={cv:.3f} exceeds threshold {self.cv_threshold:.2f}"
                )
            max_cv = max(max_cv, cv)
            dimension_results.append(DimensionStability(
                dimension   = dim,
                base_score  = base_scores[dim],
                min_score   = min(scores),
                max_score   = max(scores),
                score_range = max(scores) - min(scores),
                mean        = mean,
                std_dev     = std,
                cv          = cv,
                is_stable   = is_stable,
            ))

        ev_mean, ev_std, ev_cv = _stats([float(c) for c in evidence_counts])

        flip_rate = reliability_flips / self.n_perturbations
        if flip_rate > MAX_LABEL_FLIP_RATE:
            overall_stable = False
            instability_reasons.append(
                f"reliability label flipped {reliability_flips}/{self.n_perturbations} times "
                f"({flip_rate:.1%} > {MAX_LABEL_FLIP_RATE:.0%} threshold)"
            )

        duration_ms = (time.perf_counter() - t0) * 1000

        return StabilityReport(
            scenario_id         = scenario.scenario_id,
            scenario_name       = scenario.name,
            n_perturbations     = self.n_perturbations,
            noise_pct           = self.noise_pct,
            cv_threshold        = self.cv_threshold,
            base_evidence_count = base_evidence_count,
            dimensions          = dimension_results,
            evidence_count_cv   = ev_cv,
            label_flip_rate     = flip_rate,
            overall_stable      = overall_stable,
            max_cv              = max_cv,
            instability_reasons = instability_reasons,
            duration_ms         = duration_ms,
        )

    def run_suite(
        self,
        scenarios: Optional[List] = None,
        category:  Optional[str]  = None,
    ) -> Dict:
        """
        Run stability checks across all (or a filtered subset of) golden scenarios.

        Args:
            scenarios: explicit list of scenarios; defaults to GOLDEN_SCENARIOS.
            category:  filter by scenario category if scenarios is None.
        """
        from backend.ai.golden_tests.scenarios import GOLDEN_SCENARIOS, get_scenarios_by_category

        if scenarios is not None:
            targets = scenarios
        elif category is not None:
            targets = get_scenarios_by_category(category)
        else:
            targets = GOLDEN_SCENARIOS

        t0 = time.perf_counter()
        reports = [self.run(s) for s in targets]
        total_ms = (time.perf_counter() - t0) * 1000

        stable_count   = sum(1 for r in reports if r.overall_stable)
        unstable_count = len(reports) - stable_count
        max_cv_overall = max((r.max_cv for r in reports), default=0.0)

        return {
            "total":            len(reports),
            "stable":           stable_count,
            "unstable":         unstable_count,
            "stability_rate":   round(stable_count / len(reports), 3) if reports else 1.0,
            "noise_pct":        self.noise_pct,
            "n_perturbations":  self.n_perturbations,
            "cv_threshold":     self.cv_threshold,
            "max_cv_observed":  round(max_cv_overall, 4),
            "total_duration_ms": round(total_ms, 1),
            "results":          [r.to_dict() for r in reports],
        }


# Module-level singleton — use this everywhere instead of constructing directly.
stability_checker = StabilityChecker()
