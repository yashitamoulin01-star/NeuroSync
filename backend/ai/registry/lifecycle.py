"""
Model Lifecycle Management — versioning, deployment tracking, rollback.

Extends the core ModelRegistry with full production lifecycle semantics.
Every model version gets a deployment record; rollbacks are first-class.

This module answers:
  - "Which version is currently serving production traffic?"
  - "What were the metrics of every version we've deployed?"
  - "If 2.0.0 regresses, how do we roll back to 1.2.0 instantly?"
  - "Who approved this deployment and when?"
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class DeploymentStatus(str, Enum):
    CANDIDATE   = "candidate"    # registered, not deployed
    STAGING     = "staging"      # in staging / benchmarking
    PRODUCTION  = "production"   # actively serving
    SHADOW      = "shadow"       # running in parallel for comparison
    DEPRECATED  = "deprecated"   # replaced by newer version
    ROLLED_BACK = "rolled_back"  # explicitly rolled back


@dataclass
class ModelVersion:
    """One specific version of a named model."""
    model_name:     str
    version:        str                     # semver: "1.0.0"
    task:           str
    framework:      str
    checkpoint_path: str
    parameter_count: Optional[int]  = None

    # Training provenance
    training_dataset:         Optional[str]   = None
    training_dataset_version: Optional[str]   = None
    training_date:            Optional[str]   = None
    training_config:          Optional[Dict]  = None

    # Evaluation metrics (populated after eval run)
    macro_f1:   Optional[float] = None
    precision:  Optional[float] = None
    recall:     Optional[float] = None
    accuracy:   Optional[float] = None

    # Performance
    inference_latency_p50_ms: Optional[float] = None
    inference_latency_p95_ms: Optional[float] = None
    inference_latency_p99_ms: Optional[float] = None
    memory_mb:                Optional[float] = None

    # Lifecycle
    deployment_status: DeploymentStatus = DeploymentStatus.CANDIDATE
    registered_at:     float            = field(default_factory=time.time)
    registered_by:     str              = "system"

    # Documentation
    description:       str        = ""
    known_limitations: List[str]  = field(default_factory=list)
    supported_tasks:   List[str]  = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.model_name}@{self.version}"

    def to_dict(self) -> Dict:
        return {
            "model_name":           self.model_name,
            "version":              self.version,
            "full_name":            self.full_name,
            "task":                 self.task,
            "framework":            self.framework,
            "checkpoint_path":      self.checkpoint_path,
            "parameter_count":      self.parameter_count,
            "training_dataset":     self.training_dataset,
            "training_dataset_version": self.training_dataset_version,
            "training_date":        self.training_date,
            "macro_f1":             self.macro_f1,
            "precision":            self.precision,
            "recall":               self.recall,
            "accuracy":             self.accuracy,
            "inference_latency_p50_ms": self.inference_latency_p50_ms,
            "inference_latency_p95_ms": self.inference_latency_p95_ms,
            "inference_latency_p99_ms": self.inference_latency_p99_ms,
            "memory_mb":            self.memory_mb,
            "deployment_status":    self.deployment_status.value,
            "registered_at":        self.registered_at,
            "registered_by":        self.registered_by,
            "description":          self.description,
            "known_limitations":    self.known_limitations,
            "supported_tasks":      self.supported_tasks,
        }


@dataclass
class DeploymentEvent:
    """Immutable record of every deployment action (deploy, rollback, deprecate)."""
    event_id:       str   = field(default_factory=lambda: str(uuid.uuid4())[:8])
    model_name:     str   = ""
    from_version:   Optional[str] = None
    to_version:     str   = ""
    action:         str   = "deploy"      # "deploy" | "rollback" | "deprecate"
    triggered_by:   str   = "system"
    timestamp:      float = field(default_factory=time.time)
    reason:         str   = ""
    regression_gate_result: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return {
            "event_id":     self.event_id,
            "model_name":   self.model_name,
            "from_version": self.from_version,
            "to_version":   self.to_version,
            "action":       self.action,
            "triggered_by": self.triggered_by,
            "timestamp":    self.timestamp,
            "reason":       self.reason,
            "gate_result":  self.regression_gate_result,
        }


class ModelLifecycleRegistry:
    """
    Full lifecycle registry for all AI model versions.

    Each model name maps to multiple versions.
    One version is "production" at a time.
    Rollback is O(1) — just change the production pointer.
    """

    def __init__(self) -> None:
        self._versions: Dict[str, Dict[str, ModelVersion]] = {}
        self._production: Dict[str, str] = {}     # model_name → current production version
        self._events: List[DeploymentEvent] = []

    # ── Registration ──────────────────────────────────────────────────────────

    def register_version(self, version: ModelVersion) -> None:
        if version.model_name not in self._versions:
            self._versions[version.model_name] = {}
        self._versions[version.model_name][version.version] = version

    def get_version(self, model_name: str, version: str) -> Optional[ModelVersion]:
        return self._versions.get(model_name, {}).get(version)

    def get_all_versions(self, model_name: str) -> List[ModelVersion]:
        return list(self._versions.get(model_name, {}).values())

    def list_models(self) -> List[str]:
        return list(self._versions.keys())

    # ── Deployment ────────────────────────────────────────────────────────────

    def deploy(
        self,
        model_name:   str,
        version:      str,
        triggered_by: str = "system",
        reason:       str = "",
        gate_result:  Optional[Dict] = None,
    ) -> DeploymentEvent:
        mv = self.get_version(model_name, version)
        if mv is None:
            raise ValueError(f"Model version {model_name}@{version} not registered")

        from_version = self._production.get(model_name)

        # Deprecate previous production version
        if from_version and from_version != version:
            prev = self.get_version(model_name, from_version)
            if prev:
                prev.deployment_status = DeploymentStatus.DEPRECATED

        mv.deployment_status = DeploymentStatus.PRODUCTION
        self._production[model_name] = version

        event = DeploymentEvent(
            model_name=model_name,
            from_version=from_version,
            to_version=version,
            action="deploy",
            triggered_by=triggered_by,
            reason=reason,
            regression_gate_result=gate_result,
        )
        self._events.append(event)
        return event

    def rollback(
        self,
        model_name:   str,
        to_version:   str,
        triggered_by: str = "system",
        reason:       str = "",
    ) -> DeploymentEvent:
        mv = self.get_version(model_name, to_version)
        if mv is None:
            raise ValueError(f"Cannot rollback: {model_name}@{to_version} not registered")

        from_version = self._production.get(model_name)
        if from_version:
            current = self.get_version(model_name, from_version)
            if current:
                current.deployment_status = DeploymentStatus.ROLLED_BACK

        mv.deployment_status = DeploymentStatus.PRODUCTION
        self._production[model_name] = to_version

        event = DeploymentEvent(
            model_name=model_name,
            from_version=from_version,
            to_version=to_version,
            action="rollback",
            triggered_by=triggered_by,
            reason=reason,
        )
        self._events.append(event)
        return event

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_production(self, model_name: str) -> Optional[ModelVersion]:
        version = self._production.get(model_name)
        if version:
            return self.get_version(model_name, version)
        return None

    def deployment_history(self, model_name: Optional[str] = None) -> List[Dict]:
        events = self._events
        if model_name:
            events = [e for e in events if e.model_name == model_name]
        return [e.to_dict() for e in reversed(events)]

    def summary(self) -> Dict:
        result = []
        for name in self.list_models():
            prod = self.get_production(name)
            all_versions = self.get_all_versions(name)
            result.append({
                "model_name":        name,
                "production_version": prod.version if prod else None,
                "total_versions":    len(all_versions),
                "versions":          [v.to_dict() for v in all_versions],
            })
        return {
            "total_models":      len(self.list_models()),
            "total_deployments": len(self._events),
            "models":            result,
        }


# Singleton
lifecycle_registry = ModelLifecycleRegistry()


# ── Pre-populate known models ─────────────────────────────────────────────────

lifecycle_registry.register_version(ModelVersion(
    model_name         = "behavioral_reasoner",
    version            = "3.0.0",
    task               = "behavioral_scoring",
    framework          = "Custom Python (asymptotic pull + evidence graph)",
    checkpoint_path    = "built-in",
    deployment_status  = DeploymentStatus.PRODUCTION,
    training_dataset   = "behavioral_interview_annotations",
    training_date      = "2025-Q4",
    description        = "13-stage reasoning pipeline: evidence graph → state machine → calibration",
    supported_tasks    = ["confidence", "stress", "communication", "engagement", "consistency"],
    known_limitations  = [
        "Requires ≥15s of session data before producing reliable estimates",
        "STRESS dimension uses inverted polarity semantics",
        "Cross-modal calibration assumes temporal alignment between face and audio",
    ],
))
lifecycle_registry._production["behavioral_reasoner"] = "3.0.0"

lifecycle_registry.register_version(ModelVersion(
    model_name         = "mediapipe_face_mesh",
    version            = "0.10.x",
    task               = "facial_landmark_detection",
    framework          = "MediaPipe",
    checkpoint_path    = "built-in (468-landmark)",
    deployment_status  = DeploymentStatus.PRODUCTION,
    inference_latency_p50_ms = 12.0,
    memory_mb          = 40.0,
    supported_tasks    = ["eye_contact", "gaze", "head_stability", "blink_rate"],
))
lifecycle_registry._production["mediapipe_face_mesh"] = "0.10.x"

lifecycle_registry.register_version(ModelVersion(
    model_name         = "deberta_v3_behavioral",
    version            = "1.0.0",
    task               = "behavioral_nlp",
    framework          = "HuggingFace Transformers + LoRA",
    checkpoint_path    = "microsoft/deberta-v3-base",
    deployment_status  = DeploymentStatus.PRODUCTION,
    training_dataset   = "behavioral_interview_annotations",
    training_date      = "2025-Q4",
    memory_mb          = 740.0,
    parameter_count    = 184_000_000,
    supported_tasks    = ["confidence_language", "hesitation", "clarity", "filler_detection"],
))
lifecycle_registry._production["deberta_v3_behavioral"] = "1.0.0"
