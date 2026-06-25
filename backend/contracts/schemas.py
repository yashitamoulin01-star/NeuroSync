"""
API contract schemas — Pydantic models for all major request/response types.

These models serve two purposes:
  1. Runtime validation — FastAPI uses them to validate and document endpoints.
  2. Contract testing — tests import these models to verify API responses conform
     to the documented contract without breaking changes.

Every public API endpoint should have a corresponding response model here.
When a breaking change is needed, bump the version in the schema name.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Shared primitives ─────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error:   str
    message: str
    context: Optional[Dict[str, Any]] = None


class OkResponse(BaseModel):
    ok:      bool = True
    message: Optional[str] = None


# ── Session schemas ───────────────────────────────────────────────────────────

class SessionCreateRequest(BaseModel):
    session_name: str     = Field(..., min_length=1, max_length=200)
    mode:         str     = Field("interview", pattern="^(interview|coaching|presentation)$")
    user_id:      Optional[str] = None


class SessionCreateResponse(BaseModel):
    session_id:  str
    name:        str
    mode:        str
    started_at:  float
    status:      str


class SessionSummaryResponse(BaseModel):
    session_id:       str
    duration:         float
    avg_confidence:   float
    avg_stress:       float
    avg_engagement:   float
    avg_communication: float
    avg_consistency:  float
    total_words:      int
    total_filler_words: int
    model_version:    Optional[str] = None
    reasoning_version: Optional[str] = None


# ── Health schemas ────────────────────────────────────────────────────────────

class ComponentHealthResponse(BaseModel):
    name:        str
    status:      str   # healthy | degraded | unhealthy | unknown
    latency_ms:  Optional[float]
    details:     Dict[str, Any] = Field(default_factory=dict)
    error:       Optional[str] = None


class HealthSummary(BaseModel):
    healthy:   int
    degraded:  int
    unhealthy: int
    unknown:   int = 0


class HealthResponse(BaseModel):
    status:      str
    checked_at:  float
    duration_ms: float
    version:     str
    environment: str
    summary:     HealthSummary
    components:  List[ComponentHealthResponse]


class LivenessResponse(BaseModel):
    alive:     bool = True
    timestamp: float


class ReadinessResponse(BaseModel):
    ready:     bool
    timestamp: float


# ── System / metrics schemas ──────────────────────────────────────────────────

class VersionResponse(BaseModel):
    name:      str
    version:   str
    phase:     int
    engine:    str
    reasoning: str
    timestamp: float


class BenchmarkResult(BaseModel):
    name:               str
    iterations:         int
    p50_ms:             float
    p95_ms:             float
    p99_ms:             float
    min_ms:             float
    max_ms:             float
    throughput_per_sec: float


class BenchmarkResponse(BaseModel):
    benchmark_suite:    str
    total_duration_ms:  float
    results:            List[BenchmarkResult]
    summary:            Dict[str, Any]


# ── Alert schemas ─────────────────────────────────────────────────────────────

class AlertEntry(BaseModel):
    name:        str
    level:       str   # info | warning | critical
    message:     str
    fired_at:    float
    age_seconds: int


class AlertReport(BaseModel):
    evaluated_at: float
    total_rules:  int
    firing:       int
    healthy:      bool
    alerts:       List[AlertEntry]


# ── Golden test schemas ───────────────────────────────────────────────────────

class GoldenTestCheck(BaseModel):
    name:   str
    passed: bool
    reason: str


class GoldenTestResult(BaseModel):
    scenario_id:      str
    name:             str
    category:         str
    passed:           bool
    duration_ms:      float
    scores:           Dict[str, float]
    behavioral_state: str
    reliability:      str
    validation:       Dict[str, Any]


class GoldenTestReport(BaseModel):
    total:            int
    passed:           int
    failed:           int
    skipped:          int
    pass_rate:        float
    duration_ms:      float
    pipeline_version: str
    failures:         List[str]
    results:          List[GoldenTestResult]


# ── Stability schemas ─────────────────────────────────────────────────────────

class DimensionStability(BaseModel):
    dimension:   str
    base_score:  float
    min:         float
    max:         float
    score_range: float
    mean:        float
    std_dev:     float
    cv:          float
    is_stable:   bool


class StabilityReportResponse(BaseModel):
    scenario_id:         str
    scenario_name:       str
    n_perturbations:     int
    noise_pct:           float
    cv_threshold:        float
    base_evidence_count: int
    overall_stable:      bool
    max_cv:              float
    evidence_count_cv:   float
    label_flip_rate:     float
    duration_ms:         float
    instability_reasons: List[str]
    dimensions:          List[DimensionStability]


# ── AI Platform schemas ───────────────────────────────────────────────────────

class ModelDeployRequest(BaseModel):
    model_name:        str
    version:           str
    force:             bool = False
    baseline_metrics:  Optional[Dict[str, float]] = None
    candidate_metrics: Optional[Dict[str, float]] = None


class RegressionGateRequest(BaseModel):
    model_name:        str
    baseline_version:  str
    candidate_version: str
    baseline_metrics:  Dict[str, float]
    candidate_metrics: Dict[str, float]


class DatasetValidationRequest(BaseModel):
    dataset_name:    str
    dataset_version: str
    samples:         List[Dict[str, Any]]


# ── Load test schemas ─────────────────────────────────────────────────────────

class LoadScenarioInfo(BaseModel):
    name:           str
    description:    str
    concurrent:     int
    duration_s:     float
    max_p95_ms:     float
    max_error_rate: float


class LoadTestResult(BaseModel):
    scenario:       str
    duration_s:     float
    total_requests: int
    successful:     int
    failed:         int
    p50_ms:         float
    p95_ms:         float
    p99_ms:         float
    rps:            float
    error_rate:     float
    passed:         bool
    failures:       List[str]
