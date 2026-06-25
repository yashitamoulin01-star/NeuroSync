"""
AI Platform Router — engineering endpoints for the AI lifecycle.

These endpoints are for engineers, not recruiters.
They expose the full AI platform:

  GET  /ai/models/registry        — all model versions, deployment history
  POST /ai/models/deploy          — promote a version to production
  POST /ai/models/rollback        — roll back to a previous version
  GET  /ai/experiments            — experiment history
  POST /ai/experiments/run        — log a new experiment run
  GET  /ai/experiments/{id}       — single experiment detail
  GET  /ai/features/{session_id}  — feature store data for a session
  GET  /ai/drift                  — feature distribution drift report
  GET  /ai/calibration/evaluate   — run ECE/Brier calibration evaluation
  GET  /ai/benchmarks/history     — historical P50/P95/P99 trend
  POST /ai/benchmarks/run         — run benchmark suite + persist to history
  GET  /ai/golden-tests           — run golden test suite
  GET  /ai/golden-tests/{id}      — single scenario detail
  POST /ai/replay/{session_id}    — replay a session through current pipeline
  GET  /ai/config                 — active AI configuration
  POST /ai/datasets/validate      — validate a dataset before training
  POST /ai/regression/gate        — regression gate comparison
  POST /ai/stability/run          — recommendation stability check (one scenario)
  GET  /ai/stability/suite        — full stability sweep across all golden scenarios
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from backend.authentication.middleware import AuthContext, require_permission
from backend.rbac.permissions import Permission

from backend.ai.configuration.ai_config import ai_config
from backend.ai.registry.lifecycle import lifecycle_registry
from backend.ai.experiments.tracker import experiment_tracker
from backend.ai.feature_store.store import feature_store
from backend.ai.drift.detector import drift_detector
from backend.ai.benchmarks.history import benchmark_history
from backend.ai.evaluation.regression import regression_gate
from backend.ai.golden_tests.scenarios import GOLDEN_SCENARIOS, get_scenario, get_scenarios_by_category
from backend.ai.datasets.validator import dataset_validator
from backend.ai.evaluation.stability import stability_checker

router = APIRouter(prefix="/ai", tags=["AI Platform"])


# ── Model Registry & Lifecycle ─────────────────────────────────────────────────

@router.get("/models/registry", summary="Full model version catalog with deployment history")
async def model_registry():
    return lifecycle_registry.summary()


@router.get("/models/registry/{model_name}", summary="All versions of a specific model")
async def model_versions(model_name: str):
    versions = lifecycle_registry.get_all_versions(model_name)
    if not versions:
        raise HTTPException(404, f"Model '{model_name}' not found in lifecycle registry")
    prod = lifecycle_registry.get_production(model_name)
    return {
        "model_name":        model_name,
        "production_version": prod.version if prod else None,
        "versions":          [v.to_dict() for v in versions],
        "deployment_history": lifecycle_registry.deployment_history(model_name),
    }


@router.post("/models/deploy", summary="Promote a model version to production (with regression gate)")
async def deploy_model(
    payload: Dict = Body(...),
    _ctx: AuthContext = Depends(require_permission(Permission.PLATFORM_ADMIN)),
):
    """
    Deploy a model version to production.

    Optionally runs the regression gate first. If gate fails, deployment
    is blocked unless force=true is passed.

    Body:
        model_name: str
        version: str
        baseline_metrics: {macro_f1, avg_confidence, avg_stress, inference_p95_ms}
        candidate_metrics: {same}
        triggered_by: str
        reason: str
        force: bool (skip gate)
    """
    model_name = payload.get("model_name")
    version    = payload.get("version")
    triggered  = payload.get("triggered_by", "api")
    reason     = payload.get("reason", "")
    force      = payload.get("force", False)

    if not model_name or not version:
        raise HTTPException(400, "model_name and version are required")

    gate_result = None
    baseline_v  = payload.get("baseline_version", "")
    b_metrics   = payload.get("baseline_metrics", {})
    c_metrics   = payload.get("candidate_metrics", {})

    if b_metrics and c_metrics and not force:
        gate = regression_gate.evaluate(
            model_name        = model_name,
            baseline_version  = baseline_v,
            candidate_version = version,
            baseline_metrics  = b_metrics,
            candidate_metrics = c_metrics,
        )
        gate_result = gate.to_dict()
        if not gate.passed:
            return {
                "deployed": False,
                "blocked_by_regression_gate": True,
                "gate_result": gate_result,
            }

    try:
        event = lifecycle_registry.deploy(
            model_name   = model_name,
            version      = version,
            triggered_by = triggered,
            reason       = reason,
            gate_result  = gate_result,
        )
        return {
            "deployed":     True,
            "event":        event.to_dict(),
            "gate_result":  gate_result,
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/models/rollback", summary="Roll back a model to a previous version")
async def rollback_model(
    payload: Dict = Body(...),
    _ctx: AuthContext = Depends(require_permission(Permission.PLATFORM_ADMIN)),
):
    model_name = payload.get("model_name")
    to_version = payload.get("to_version")
    reason     = payload.get("reason", "manual rollback")
    triggered  = payload.get("triggered_by", "api")

    if not model_name or not to_version:
        raise HTTPException(400, "model_name and to_version are required")

    try:
        event = lifecycle_registry.rollback(
            model_name   = model_name,
            to_version   = to_version,
            triggered_by = triggered,
            reason       = reason,
        )
        return {"rolled_back": True, "event": event.to_dict()}
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/models/history", summary="Full deployment history across all models")
async def deployment_history(model_name: Optional[str] = None):
    return {"history": lifecycle_registry.deployment_history(model_name)}


# ── Experiments ────────────────────────────────────────────────────────────────

@router.get("/experiments", summary="All experiments with run history")
async def list_experiments():
    return experiment_tracker.summary()


@router.get("/experiments/{experiment_name}", summary="Single experiment detail")
async def get_experiment(experiment_name: str):
    exp = experiment_tracker.get_experiment(experiment_name)
    if exp is None:
        raise HTTPException(404, f"Experiment '{experiment_name}' not found")
    return exp.to_dict()


@router.post("/experiments/run", summary="Log a new experiment run")
async def log_experiment_run(payload: Dict = Body(...)):
    """
    Log a training or evaluation run.

    Body:
        experiment_name: str
        model_name: str
        model_version: str
        dataset_name: str
        dataset_version: str
        hyperparameters: {lr, epochs, ...}
        macro_f1: float
        precision: float
        recall: float
        ece: float
        brier_score: float
        inference_p50_ms: float
        inference_p95_ms: float
        memory_mb: float
        notes: str
    """
    run = experiment_tracker.start_run(
        experiment_name  = payload.get("experiment_name", "default"),
        model_name       = payload.get("model_name", ""),
        model_version    = payload.get("model_version", ""),
        dataset_name     = payload.get("dataset_name", ""),
        dataset_version  = payload.get("dataset_version", ""),
        hyperparameters  = payload.get("hyperparameters", {}),
    )
    if "macro_f1" in payload:
        run.complete(
            macro_f1         = payload.get("macro_f1", 0.0),
            precision        = payload.get("precision", 0.0),
            recall           = payload.get("recall", 0.0),
            accuracy         = payload.get("accuracy", 0.0),
            ece              = payload.get("ece", 0.0),
            brier_score      = payload.get("brier_score", 0.0),
            inference_p50_ms = payload.get("inference_p50_ms", 0.0),
            inference_p95_ms = payload.get("inference_p95_ms", 0.0),
            memory_mb        = payload.get("memory_mb", 0.0),
        )
        run.notes = payload.get("notes", "")
    return run.to_dict()


@router.post("/experiments/compare", summary="Compare two experiment runs side-by-side")
async def compare_runs(payload: Dict = Body(...)):
    run_a = payload.get("run_id_a")
    run_b = payload.get("run_id_b")
    if not run_a or not run_b:
        raise HTTPException(400, "run_id_a and run_id_b required")
    return experiment_tracker.compare(run_a, run_b)


# ── Feature Store ─────────────────────────────────────────────────────────────

@router.get("/features/{session_id}", summary="All logged features for a session")
async def get_features(session_id: str, feature_name: Optional[str] = None):
    batches = feature_store.get_batches(session_id)
    if not batches:
        raise HTTPException(404, f"No feature data found for session '{session_id}'")
    if feature_name:
        values = feature_store.get_feature_values(session_id, feature_name)
        return {"session_id": session_id, "feature_name": feature_name, "values": values}
    return {
        "session_id":  session_id,
        "batch_count": len(batches),
        "batches":     [b.to_dict() for b in batches],
    }


@router.get("/features", summary="Feature store statistics")
async def feature_store_stats():
    return feature_store.stats()


# ── Drift Detection ───────────────────────────────────────────────────────────

@router.get("/drift", summary="Current feature distribution drift report")
async def drift_report():
    report = drift_detector.detect()
    return report.to_dict()


@router.post("/drift/update", summary="Push production feature values for drift monitoring")
async def update_drift(payload: Dict = Body(...)):
    """
    Update drift detector with recent production feature values.

    Body:
        features: {feature_name: [val1, val2, ...], ...}
    """
    features = payload.get("features", {})
    for name, values in features.items():
        if isinstance(values, list):
            drift_detector.update(name, values)
    return {"updated_features": list(features.keys())}


# ── Calibration Evaluation ────────────────────────────────────────────────────

@router.post("/calibration/evaluate", summary="Compute ECE and Brier Score from prediction samples")
async def calibration_evaluate(payload: Dict = Body(...)):
    """
    Evaluate calibration from a list of (confidence, correct) pairs.

    Body:
        confidences: [0.9, 0.8, ...]   — model predicted confidence per sample
        correct: [true, false, ...]     — whether prediction was correct
        n_bins: int (default 10)
    """
    from backend.ai.evaluation.calibration import compute_ece
    confs   = payload.get("confidences", [])
    correct = payload.get("correct", [])
    n_bins  = payload.get("n_bins", 10)
    if not confs or not correct:
        raise HTTPException(400, "confidences and correct lists required")
    if len(confs) != len(correct):
        raise HTTPException(400, "confidences and correct must have the same length")
    report = compute_ece([float(c) for c in confs], [bool(b) for b in correct], n_bins)
    return report.to_dict()


# ── Benchmarks ────────────────────────────────────────────────────────────────

@router.get("/benchmarks/history", summary="Historical P50/P95/P99 benchmark trends")
async def get_benchmark_history(n: int = 20):
    recent = benchmark_history.get_recent(n)
    trends = {
        comp: benchmark_history.trend(comp, n)
        for comp in [
            "evidence_graph_build",
            "temporal_analysis",
            "behavioral_state_transition",
            "context_rules_evaluation",
            "confidence_calibration",
        ]
    }
    return {
        "recent_runs": recent,
        "trends":      trends,
        "stats":       benchmark_history.stats(),
    }


@router.post("/benchmarks/run", summary="Run benchmark suite and persist to history")
async def run_and_record_benchmark():
    from backend.benchmarks.pipeline_benchmark import run_quick_benchmark
    loop    = asyncio.get_running_loop()
    results_dict = await loop.run_in_executor(None, run_quick_benchmark)
    entry = benchmark_history.record(
        results  = results_dict["results"],
        total_ms = results_dict["total_duration_ms"],
    )
    return {
        "recorded": True,
        "run_id":   entry.run_id,
        "results":  results_dict,
    }


# ── Golden Tests ──────────────────────────────────────────────────────────────

@router.get("/golden-tests", summary="Run all golden test scenarios through the reasoning pipeline")
async def run_golden_tests(category: Optional[str] = None):
    from backend.ai.golden_tests.runner import run_golden_suite
    scenarios = (
        get_scenarios_by_category(category) if category else None
    )
    loop   = asyncio.get_running_loop()
    report = await loop.run_in_executor(None, lambda: run_golden_suite(scenarios))
    return report.to_dict()


@router.get("/golden-tests/scenarios", summary="List all golden test scenarios without running them")
async def list_golden_scenarios():
    return {
        "total": len(GOLDEN_SCENARIOS),
        "scenarios": [
            {
                "scenario_id": s.scenario_id,
                "name":        s.name,
                "description": s.description,
                "category":    s.category,
            }
            for s in GOLDEN_SCENARIOS
        ],
    }


@router.get("/golden-tests/{scenario_id}", summary="Run a single golden test scenario")
async def run_single_golden_test(scenario_id: str):
    from backend.ai.golden_tests.runner import run_golden_suite
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found")
    loop   = asyncio.get_running_loop()
    report = await loop.run_in_executor(None, lambda: run_golden_suite([scenario]))
    return report.to_dict()


# ── Replay ────────────────────────────────────────────────────────────────────

@router.post("/replay/{session_id}", summary="Replay a recorded session through current pipeline")
async def replay_session(session_id: str, payload: Dict = Body(...)):
    """
    Replay a session's stored analytics through the current reasoning pipeline.

    Body:
        analytics: [FusedAnalytics.model_dump(), ...]  — stored session frames
        original_version: str
    """
    from backend.ai.replay.engine import replay_engine
    analytics = payload.get("analytics", [])
    original  = payload.get("original_version", "unknown")
    if not analytics:
        raise HTTPException(400, "analytics list required in body")
    loop   = asyncio.get_running_loop()
    report = await loop.run_in_executor(
        None,
        lambda: replay_engine.replay_session(session_id, analytics, original),
    )
    return report.to_dict()


# ── Dataset Validation ────────────────────────────────────────────────────────

@router.post("/datasets/validate", summary="Validate a dataset before training")
async def validate_dataset(payload: Dict = Body(...)):
    """
    Run pre-training dataset quality checks.

    Body:
        samples: [{session_id, features: {...}, labels: {confidence, stress, ...}}, ...]
        dataset_name: str
        dataset_version: str
    """
    samples  = payload.get("samples", [])
    name     = payload.get("dataset_name", "unknown")
    version  = payload.get("dataset_version", "unknown")
    if not samples:
        raise HTTPException(400, "samples list required")
    report = dataset_validator.validate(samples, name, version)
    return report.to_dict()


# ── Regression Gate ───────────────────────────────────────────────────────────

@router.post("/regression/gate", summary="Run regression gate between baseline and candidate model")
async def regression_gate_check(payload: Dict = Body(...)):
    """
    Compare baseline vs candidate metrics and determine if deployment is safe.

    Body:
        model_name: str
        baseline_version: str
        candidate_version: str
        baseline_metrics: {macro_f1, avg_confidence, avg_stress, inference_p95_ms, ece}
        candidate_metrics: {same}
    """
    result = regression_gate.evaluate(
        model_name        = payload.get("model_name", ""),
        baseline_version  = payload.get("baseline_version", ""),
        candidate_version = payload.get("candidate_version", ""),
        baseline_metrics  = payload.get("baseline_metrics", {}),
        candidate_metrics = payload.get("candidate_metrics", {}),
    )
    return result.to_dict()


# ── Recommendation Stability ──────────────────────────────────────────────────

@router.post(
    "/stability/run",
    summary="Measure output stability for one scenario under Gaussian input noise",
)
async def stability_run(payload: Dict = Body(...)):
    """
    Run a stability check on a single golden scenario.

    Body:
        scenario_id:     str   — e.g. "GS-001"
        noise_pct:       float — fraction of Gaussian noise per signal (default 0.05)
        n_perturbations: int   — how many noisy runs (default 20)

    Returns per-dimension CV, score spread, reliability flip rate, and overall
    stable/unstable verdict.
    """
    scenario_id = payload.get("scenario_id", "")
    if not scenario_id:
        raise HTTPException(400, "scenario_id required")

    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(404, f"scenario '{scenario_id}' not found")

    noise_pct       = float(payload.get("noise_pct",       stability_checker.noise_pct))
    n_perturbations = int(  payload.get("n_perturbations", stability_checker.n_perturbations))

    from backend.ai.evaluation.stability import StabilityChecker
    checker = StabilityChecker(noise_pct=noise_pct, n_perturbations=n_perturbations)

    loop   = asyncio.get_running_loop()
    report = await loop.run_in_executor(None, lambda: checker.run(scenario))
    return report.to_dict()


@router.get(
    "/stability/suite",
    summary="Full stability sweep — all golden scenarios under default noise settings",
)
async def stability_suite(
    category:        Optional[str] = None,
    noise_pct:       float         = 0.05,
    n_perturbations: int           = 20,
):
    """
    Run the recommendation stability check across all (or a category-filtered
    subset of) golden scenarios.

    Query params:
        category:        optional filter (positive / negative / edge_case / missing_data)
        noise_pct:       Gaussian noise fraction (default 0.05 = 5%)
        n_perturbations: noisy runs per scenario (default 20)
    """
    from backend.ai.evaluation.stability import StabilityChecker
    checker = StabilityChecker(noise_pct=noise_pct, n_perturbations=n_perturbations)

    loop   = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: checker.run_suite(category=category),
    )
    return result


# ── AI Configuration ──────────────────────────────────────────────────────────

@router.get("/config", summary="Active AI configuration — all thresholds and weights")
async def get_ai_config():
    return ai_config.to_dict()


# ── Load Testing ──────────────────────────────────────────────────────────────

@router.get("/load-test/scenarios", summary="List available HTTP load test scenarios")
async def load_test_scenarios():
    from backend.load_testing.scenarios import SCENARIOS
    return {
        "total": len(SCENARIOS),
        "scenarios": [
            {
                "name":           s.name,
                "description":    s.description,
                "concurrent":     s.concurrent,
                "duration_s":     s.duration_s,
                "max_p95_ms":     s.max_p95_ms,
                "max_error_rate": s.max_error_rate,
                "min_rps":        s.min_rps,
            }
            for s in SCENARIOS
        ],
    }


@router.post("/load-test/run", summary="Run an HTTP load test scenario in-process")
async def run_load_test(payload: Dict = Body(...)):
    """
    Run one of the built-in HTTP load scenarios against a target server.

    Body:
        scenario: str        — name from GET /ai/load-test/scenarios
        base_url: str        — target (default: http://localhost:8000)

    Note: soak scenario runs for 30 minutes — use only in dedicated test runs.
    """
    from backend.load_testing.scenarios import SCENARIOS, run_scenario_in_process

    name = payload.get("scenario", "smoke")
    base_url = payload.get("base_url", "http://localhost:8000")

    scenario = next((s for s in SCENARIOS if s.name == name), None)
    if scenario is None:
        raise HTTPException(400, f"Unknown scenario '{name}'. Available: {[s.name for s in SCENARIOS]}")

    loop   = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: asyncio.run(run_scenario_in_process(scenario, base_url)),
    )
    return result.to_dict()


@router.get("/stress-test/scenarios", summary="List WebSocket stress test scenarios")
async def ws_stress_scenarios():
    from backend.stress_testing.websocket import WS_SCENARIOS
    return {
        "total": len(WS_SCENARIOS),
        "scenarios": [
            {
                "name":               s.name,
                "description":        s.description,
                "concurrent":         s.concurrent,
                "messages_per_conn":  s.messages_per_conn,
                "message_interval":   s.message_interval,
                "max_error_rate":     s.max_error_rate,
                "max_p95_latency_ms": s.max_p95_latency_ms,
            }
            for s in WS_SCENARIOS
        ],
    }


@router.post("/stress-test/run", summary="Run a WebSocket stress test scenario")
async def run_ws_stress_test(payload: Dict = Body(...)):
    """
    Run a WebSocket stress scenario against a target server.

    Body:
        scenario: str   — name from GET /ai/stress-test/scenarios
        base_url: str   — ws:// target (default: ws://localhost:8000)
    """
    from backend.stress_testing.websocket import WS_SCENARIOS, run_ws_scenario

    name     = payload.get("scenario", "rapid_reconnect")
    base_url = payload.get("base_url", "ws://localhost:8000")

    scenario = next((s for s in WS_SCENARIOS if s.name == name), None)
    if scenario is None:
        raise HTTPException(400, f"Unknown scenario '{name}'. Available: {[s.name for s in WS_SCENARIOS]}")

    result = await run_ws_scenario(scenario, base_url)
    return result.to_dict()


# ── Operations (backup) ───────────────────────────────────────────────────────

@router.post("/operations/backup", summary="Run full system backup (database + config + model registry)")
async def run_backup():
    from backend.operations.backup import run_full_backup
    loop   = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, run_full_backup)
    return {"backup_results": result}


@router.get("/operations/backups", summary="List existing backup files")
async def list_backups():
    from backend.operations.backup import list_backups as _list
    loop   = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _list)
