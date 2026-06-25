"""
Experiment Tracker — MLflow-compatible experiment management.

Tracks every training and evaluation run. Future migration to MLflow:
replace the in-memory backend with mlflow.start_run() / mlflow.log_metric()
calls — the public API stays the same.

Usage:
    from backend.ai.experiments.tracker import experiment_tracker

    with experiment_tracker.start_run("deberta_v3_behavioral", "v1.1.0 LoRA fine-tune") as run:
        run.hyperparameters = {"lr": 2e-5, "epochs": 3, "lora_r": 8}
        # ... training ...
        run.complete(macro_f1=0.82, precision=0.81, recall=0.83)
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Dict, Generator, List, Optional

from backend.ai.experiments.schemas import Experiment, ExperimentRun, RunStatus

logger = logging.getLogger(__name__)


class ExperimentTracker:

    def __init__(self) -> None:
        self._experiments: Dict[str, Experiment] = {}   # name → Experiment
        self._runs: Dict[str, ExperimentRun] = {}       # run_id → ExperimentRun

    # ── Experiment CRUD ───────────────────────────────────────────────────────

    def create_experiment(
        self,
        name:       str,
        model_name: str,
        description: str = "",
    ) -> Experiment:
        if name in self._experiments:
            return self._experiments[name]
        exp = Experiment(name=name, model_name=model_name, description=description)
        self._experiments[name] = exp
        logger.info("Experiment created: %s", name)
        return exp

    def get_experiment(self, name: str) -> Optional[Experiment]:
        return self._experiments.get(name)

    def list_experiments(self) -> List[Experiment]:
        return list(self._experiments.values())

    # ── Run management ────────────────────────────────────────────────────────

    def start_run(
        self,
        experiment_name: str,
        model_name:      str,
        model_version:   str,
        dataset_name:    str       = "",
        dataset_version: str       = "",
        base_version:    Optional[str] = None,
        hyperparameters: Optional[Dict] = None,
        pipeline_version: str      = "3.0.0",
        tags:            Optional[List[str]] = None,
    ) -> ExperimentRun:
        exp = self._experiments.get(experiment_name)
        if exp is None:
            exp = self.create_experiment(experiment_name, model_name)

        run = ExperimentRun(
            experiment_id    = exp.experiment_id,
            experiment_name  = experiment_name,
            model_name       = model_name,
            model_version    = model_version,
            base_version     = base_version,
            dataset_name     = dataset_name,
            dataset_version  = dataset_version,
            hyperparameters  = hyperparameters or {},
            pipeline_version = pipeline_version,
            tags             = tags or [],
        )
        exp.runs.append(run)
        self._runs[run.run_id] = run
        logger.info("Run started: %s  experiment=%s  model=%s@%s",
                    run.run_id, experiment_name, model_name, model_version)
        return run

    @contextmanager
    def run_context(
        self,
        experiment_name: str,
        model_name:      str,
        model_version:   str,
        **kwargs,
    ) -> Generator[ExperimentRun, None, None]:
        """Context manager — marks run as FAILED if an exception occurs."""
        run = self.start_run(experiment_name, model_name, model_version, **kwargs)
        try:
            yield run
            if run.status == RunStatus.RUNNING:
                run.fail("run_context exited without explicit complete() call")
        except Exception as exc:
            run.fail(str(exc))
            logger.exception("Run %s failed: %s", run.run_id, exc)
            raise

    def get_run(self, run_id: str) -> Optional[ExperimentRun]:
        return self._runs.get(run_id)

    # ── Comparison ────────────────────────────────────────────────────────────

    def compare(
        self,
        run_id_a: str,
        run_id_b: str,
    ) -> Dict:
        """Compare two runs side-by-side on key metrics."""
        a = self.get_run(run_id_a)
        b = self.get_run(run_id_b)
        if not a or not b:
            return {"error": "one or both run_ids not found"}

        def _delta(attr):
            va, vb = getattr(a, attr), getattr(b, attr)
            if va is not None and vb is not None:
                return round(vb - va, 4)
            return None

        return {
            "run_a": {"run_id": a.run_id, "version": a.model_version},
            "run_b": {"run_id": b.run_id, "version": b.model_version},
            "deltas": {
                "macro_f1":         _delta("macro_f1"),
                "precision":        _delta("precision"),
                "recall":           _delta("recall"),
                "ece":              _delta("ece"),
                "brier_score":      _delta("brier_score"),
                "inference_p50_ms": _delta("inference_p50_ms"),
                "inference_p95_ms": _delta("inference_p95_ms"),
                "memory_mb":        _delta("memory_mb"),
            },
        }

    # ── Summary ───────────────────────────────────────────────────────────────

    def summary(self) -> Dict:
        return {
            "total_experiments": len(self._experiments),
            "total_runs": len(self._runs),
            "experiments": [e.to_dict() for e in self._experiments.values()],
        }


experiment_tracker = ExperimentTracker()
