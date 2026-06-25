"""
Experiment schemas — structured records for every training or evaluation run.

Modeled after MLflow's experiment/run concept.
Future migration to MLflow or W&B: replace the tracker backend,
keep these schemas unchanged.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RunStatus(str, Enum):
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    KILLED    = "killed"


@dataclass
class ExperimentRun:
    """One training / evaluation run within an experiment."""

    run_id:          str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    experiment_id:   str = ""
    experiment_name: str = ""

    # Model identity
    model_name:     str = ""
    model_version:  str = ""
    base_version:   Optional[str] = None    # version this run improves on

    # Dataset
    dataset_name:    str = ""
    dataset_version: str = ""
    train_samples:   int = 0
    eval_samples:    int = 0

    # Configuration
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    git_hash:        Optional[str]  = None
    pipeline_version: str = ""

    # Results (filled after run)
    status:      RunStatus    = RunStatus.RUNNING
    started_at:  float        = field(default_factory=time.time)
    ended_at:    Optional[float] = None
    duration_s:  Optional[float] = None

    # Evaluation metrics
    macro_f1:    Optional[float] = None
    precision:   Optional[float] = None
    recall:      Optional[float] = None
    accuracy:    Optional[float] = None
    ece:         Optional[float] = None   # Expected Calibration Error
    brier_score: Optional[float] = None

    # Performance metrics
    inference_p50_ms: Optional[float] = None
    inference_p95_ms: Optional[float] = None
    memory_mb:        Optional[float] = None

    # Comparison vs baseline
    f1_delta:     Optional[float] = None  # new - baseline
    latency_delta: Optional[float] = None

    notes: str = ""
    tags:  List[str] = field(default_factory=list)

    def complete(
        self,
        macro_f1: float,
        precision: float = 0.0,
        recall: float = 0.0,
        accuracy: float = 0.0,
        ece: float = 0.0,
        brier_score: float = 0.0,
        inference_p50_ms: float = 0.0,
        inference_p95_ms: float = 0.0,
        memory_mb: float = 0.0,
    ) -> None:
        self.status    = RunStatus.COMPLETED
        self.ended_at  = time.time()
        self.duration_s = self.ended_at - self.started_at
        self.macro_f1        = macro_f1
        self.precision       = precision
        self.recall          = recall
        self.accuracy        = accuracy
        self.ece             = ece
        self.brier_score     = brier_score
        self.inference_p50_ms = inference_p50_ms
        self.inference_p95_ms = inference_p95_ms
        self.memory_mb       = memory_mb

    def fail(self, reason: str = "") -> None:
        self.status   = RunStatus.FAILED
        self.ended_at = time.time()
        self.notes    = reason or self.notes

    def to_dict(self) -> Dict:
        return {
            "run_id":           self.run_id,
            "experiment_id":    self.experiment_id,
            "experiment_name":  self.experiment_name,
            "model_name":       self.model_name,
            "model_version":    self.model_version,
            "base_version":     self.base_version,
            "dataset_name":     self.dataset_name,
            "dataset_version":  self.dataset_version,
            "train_samples":    self.train_samples,
            "eval_samples":     self.eval_samples,
            "hyperparameters":  self.hyperparameters,
            "git_hash":         self.git_hash,
            "pipeline_version": self.pipeline_version,
            "status":           self.status.value,
            "started_at":       self.started_at,
            "ended_at":         self.ended_at,
            "duration_s":       round(self.duration_s, 2) if self.duration_s else None,
            "macro_f1":         self.macro_f1,
            "precision":        self.precision,
            "recall":           self.recall,
            "accuracy":         self.accuracy,
            "ece":              self.ece,
            "brier_score":      self.brier_score,
            "inference_p50_ms": self.inference_p50_ms,
            "inference_p95_ms": self.inference_p95_ms,
            "memory_mb":        self.memory_mb,
            "f1_delta":         self.f1_delta,
            "latency_delta":    self.latency_delta,
            "notes":            self.notes,
            "tags":             self.tags,
        }


@dataclass
class Experiment:
    """A named experiment grouping multiple runs."""
    experiment_id:   str  = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name:            str  = ""
    description:     str  = ""
    model_name:      str  = ""
    created_at:      float = field(default_factory=time.time)
    runs:            List[ExperimentRun] = field(default_factory=list)

    def best_run(self, metric: str = "macro_f1") -> Optional[ExperimentRun]:
        completed = [r for r in self.runs if r.status == RunStatus.COMPLETED]
        if not completed:
            return None
        return max(completed, key=lambda r: getattr(r, metric) or 0.0)

    def to_dict(self) -> Dict:
        best = self.best_run()
        return {
            "experiment_id": self.experiment_id,
            "name":          self.name,
            "description":   self.description,
            "model_name":    self.model_name,
            "created_at":    self.created_at,
            "total_runs":    len(self.runs),
            "best_f1":       best.macro_f1 if best else None,
            "best_run_id":   best.run_id if best else None,
            "runs":          [r.to_dict() for r in self.runs],
        }
