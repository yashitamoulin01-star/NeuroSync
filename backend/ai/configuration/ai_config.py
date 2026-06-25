"""
Centralized AI Configuration — single source of truth for all AI thresholds.

Every threshold, weight, and limit that governs AI behavior lives here.
Scattered magic numbers in business logic are a maintenance hazard:
changing a threshold means a grep hunt across the codebase.

Usage:
    from backend.ai.configuration.ai_config import ai_config
    if score < ai_config.reasoning.high_reliability_threshold:
        ...

All values can be overridden via environment variables (prefixed AI_).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


# ── Sub-configurations ─────────────────────────────────────────────────────────

@dataclass
class ReasoningConfig:
    # Reliability thresholds (BehavioralReasoner._assess_reliability)
    high_reliability_threshold:   float = 0.68
    medium_reliability_threshold: float = 0.40
    insufficient_duration_secs:   float = 15.0
    insufficient_evidence_count:  int   = 2

    # Baselines (prior before evidence)
    baseline_confidence:    float = 0.50
    baseline_stress:        float = 0.28
    baseline_communication: float = 0.55
    baseline_engagement:    float = 0.50
    baseline_consistency:   float = 0.65

    # Quality dampening
    missing_nlp_face_blend:  float = 0.60
    missing_audio_face_blend: float = 0.60
    missing_nlp_blend:        float = 0.45


@dataclass
class CalibrationConfig:
    # Prediction confidence weights
    reliability_weight:         float = 0.40
    cross_modal_agreement_weight: float = 0.25
    time_confidence_weight:     float = 0.20
    evidence_quality_weight:    float = 0.15
    conflict_penalty_factor:    float = 0.30

    # Signal quality thresholds
    excellent_confidence_threshold: float = 0.78
    good_confidence_threshold:      float = 0.58
    fair_confidence_threshold:      float = 0.38

    # Time confidence ramp (seconds to reach full confidence)
    full_confidence_at_secs: float = 300.0


@dataclass
class TemporalConfig:
    # OLS trend detection
    rising_slope_threshold:  float = 0.002
    falling_slope_threshold: float = -0.002

    # Behavioral state transitions
    warming_up_duration_secs: float = 45.0
    settling_confident_threshold: float = 0.68
    settling_stress_limit:        float = 0.32
    stressed_threshold:           float = 0.65
    recovery_confidence_min:      float = 0.55

    # History window
    max_snapshots: int = 50


@dataclass
class DriftConfig:
    # Population Stability Index thresholds (standard industry values)
    psi_no_change:   float = 0.10   # PSI < 0.10: no significant shift
    psi_moderate:    float = 0.25   # PSI 0.10–0.25: moderate shift, monitor
                                    # PSI > 0.25: significant shift, investigate
    kl_warning:      float = 0.10   # KL divergence warning threshold
    kl_critical:     float = 0.50   # KL divergence critical threshold
    min_samples_for_drift: int = 30


@dataclass
class RegressionConfig:
    # Gates: deployment blocked if new model regresses beyond these margins
    max_confidence_delta:    float = 0.05   # max allowed drop in avg confidence score
    max_stress_delta:        float = 0.05   # max allowed rise in avg stress score
    max_latency_increase_ms: float = 50.0  # max allowed P95 latency increase
    min_f1_retention:        float = 0.97  # new model must retain 97% of old macro F1


@dataclass
class FeatureStoreConfig:
    max_features_per_session: int = 500
    feature_ttl_days:         int = 90
    compression_enabled:      bool = True


@dataclass
class ExperimentConfig:
    max_runs_per_experiment: int = 100
    auto_log_git_hash:       bool = True
    default_metric_primary:  str  = "macro_f1"


@dataclass
class GoldenTestConfig:
    # Stability: output must not shift more than this on repeated runs
    stability_tolerance: float = 0.02
    # Minimum confidence when running golden tests
    min_acceptable_confidence: float = 0.40
    # Maximum allowable stress on "excellent candidate" scenario
    excellent_max_stress: float = 0.35


@dataclass
class AIConfiguration:
    """Root AI configuration object. Import this singleton everywhere."""
    reasoning:    ReasoningConfig    = field(default_factory=ReasoningConfig)
    calibration:  CalibrationConfig  = field(default_factory=CalibrationConfig)
    temporal:     TemporalConfig     = field(default_factory=TemporalConfig)
    drift:        DriftConfig        = field(default_factory=DriftConfig)
    regression:   RegressionConfig   = field(default_factory=RegressionConfig)
    feature_store: FeatureStoreConfig = field(default_factory=FeatureStoreConfig)
    experiments:  ExperimentConfig   = field(default_factory=ExperimentConfig)
    golden_tests: GoldenTestConfig   = field(default_factory=GoldenTestConfig)

    def to_dict(self) -> Dict:
        import dataclasses
        def _recurse(obj):
            if dataclasses.is_dataclass(obj):
                return {k: _recurse(v) for k, v in dataclasses.asdict(obj).items()}
            return obj
        return _recurse(self)


# Module-level singleton
ai_config = AIConfiguration()
