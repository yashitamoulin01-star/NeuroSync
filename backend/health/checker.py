"""
Comprehensive health check subsystem.

Each component exposes a check function returning ComponentHealth.
HealthChecker aggregates all components into a platform-wide HealthReport.

Status precedence:
  unhealthy > degraded > unknown > healthy

Critical components (database, reasoning_engine, session_manager) drive
the top-level status. All others contribute DEGRADED at worst.

Usage:
    report = health_checker.check_all()
    report.to_dict()  # → structured dict for JSON response

GET /system/health           → full report (all components)
GET /health/live             → always 200 (liveness probe)
GET /health/ready            → 200 | 503 (readiness probe)
GET /health/dependencies     → external dependency statuses
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class Status(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN   = "unknown"


@dataclass
class ComponentHealth:
    name:       str
    status:     Status
    latency_ms: Optional[float]
    details:    Dict[str, Any] = field(default_factory=dict)
    error:      Optional[str]  = None

    def to_dict(self) -> Dict:
        return {
            "name":       self.name,
            "status":     self.status.value,
            "latency_ms": self.latency_ms,
            "details":    self.details,
            "error":      self.error,
        }


@dataclass
class HealthReport:
    status:      Status
    checked_at:  float
    duration_ms: float
    version:     str
    environment: str
    components:  List[ComponentHealth] = field(default_factory=list)

    def to_dict(self) -> Dict:
        summary = {
            "healthy":   sum(1 for c in self.components if c.status == Status.HEALTHY),
            "degraded":  sum(1 for c in self.components if c.status == Status.DEGRADED),
            "unhealthy": sum(1 for c in self.components if c.status == Status.UNHEALTHY),
            "unknown":   sum(1 for c in self.components if c.status == Status.UNKNOWN),
        }
        return {
            "status":      self.status.value,
            "checked_at":  self.checked_at,
            "duration_ms": round(self.duration_ms, 1),
            "version":     self.version,
            "environment": self.environment,
            "summary":     summary,
            "components":  [c.to_dict() for c in self.components],
        }


# ── Timing helper ─────────────────────────────────────────────────────────────

def _timed(fn: Callable) -> Tuple[Any, float]:
    t0     = time.perf_counter()
    result = fn()
    return result, round((time.perf_counter() - t0) * 1000, 2)


# ── Component checks ──────────────────────────────────────────────────────────

def _check_database() -> ComponentHealth:
    try:
        import backend.services.db_service as db
        def _run():
            conn = db.get_connection()
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            conn.close()
            return count
        count, ms = _timed(_run)
        return ComponentHealth("database", Status.HEALTHY, ms, {"session_rows": count, "engine": "SQLite WAL"})
    except Exception as exc:
        return ComponentHealth("database", Status.UNHEALTHY, None, error=str(exc))


def _check_reasoning_engine() -> ComponentHealth:
    try:
        from backend.reasoning.reasoner import reasoner
        from backend.models.evidence import ModalityQuality

        def _run():
            q = ModalityQuality(
                face_available=False, face_quality=0.0,
                audio_available=False, audio_quality=0.0,
                nlp_available=False, nlp_quality=0.0,
                transcript_words=0, evidence_coverage=0.0,
            )
            return reasoner.reason(evidence=[], quality=q, session_duration=0, total_words=0)

        _, ms = _timed(_run)
        return ComponentHealth("reasoning_engine", Status.HEALTHY, ms, {"type": "asymptotic_pull", "dimensions": 5})
    except Exception as exc:
        return ComponentHealth("reasoning_engine", Status.UNHEALTHY, None, error=str(exc))


def _check_model_registry() -> ComponentHealth:
    try:
        from backend.core.registry.model_registry import model_registry
        models, ms = _timed(model_registry.all)
        active = [m for m in models if m.status == "active"]
        status = Status.HEALTHY if active else Status.DEGRADED
        return ComponentHealth("model_registry", status, ms, {"total": len(models), "active": len(active)})
    except Exception as exc:
        return ComponentHealth("model_registry", Status.UNHEALTHY, None, error=str(exc))


def _check_session_manager() -> ComponentHealth:
    try:
        from backend.services.session_manager import session_manager
        count, ms = _timed(lambda: len(session_manager._sessions))
        return ComponentHealth("session_manager", Status.HEALTHY, ms, {"active_sessions": count})
    except Exception as exc:
        return ComponentHealth("session_manager", Status.UNHEALTHY, None, error=str(exc))


def _check_event_bus() -> ComponentHealth:
    try:
        from backend.core.events.bus import event_bus
        stats, ms = _timed(event_bus.stats)
        return ComponentHealth("event_bus", Status.HEALTHY, ms, stats)
    except Exception as exc:
        return ComponentHealth("event_bus", Status.DEGRADED, None, error=str(exc))


def _check_feature_store() -> ComponentHealth:
    try:
        from backend.ai.feature_store.store import feature_store
        stats, ms = _timed(feature_store.stats)
        return ComponentHealth("feature_store", Status.HEALTHY, ms, stats)
    except Exception as exc:
        return ComponentHealth("feature_store", Status.DEGRADED, None, error=str(exc))


def _check_ai_lifecycle() -> ComponentHealth:
    try:
        from backend.ai.registry.lifecycle import lifecycle_registry
        summary, ms = _timed(lifecycle_registry.summary)
        return ComponentHealth(
            "ai_lifecycle_registry", Status.HEALTHY, ms,
            {"models": summary.get("total_models", 0)},
        )
    except Exception as exc:
        return ComponentHealth("ai_lifecycle_registry", Status.DEGRADED, None, error=str(exc))


def _check_memory() -> ComponentHealth:
    try:
        import psutil
        def _run():
            mem = psutil.virtual_memory()
            return {"total_mb": round(mem.total / 1e6), "available_mb": round(mem.available / 1e6), "used_pct": mem.percent}
        info, ms = _timed(_run)
        status = Status.UNHEALTHY if info["used_pct"] > 95 else (Status.DEGRADED if info["used_pct"] > 85 else Status.HEALTHY)
        return ComponentHealth("memory", status, ms, info)
    except ImportError:
        return ComponentHealth("memory", Status.UNKNOWN, None, error="psutil not installed")
    except Exception as exc:
        return ComponentHealth("memory", Status.UNKNOWN, None, error=str(exc))


def _check_storage() -> ComponentHealth:
    try:
        import psutil
        def _run():
            d = psutil.disk_usage(".")
            return {"total_gb": round(d.total / 1e9, 1), "free_gb": round(d.free / 1e9, 1), "used_pct": d.percent}
        info, ms = _timed(_run)
        status = Status.UNHEALTHY if info["used_pct"] > 95 else (Status.DEGRADED if info["used_pct"] > 85 else Status.HEALTHY)
        return ComponentHealth("storage", status, ms, info)
    except ImportError:
        return ComponentHealth("storage", Status.UNKNOWN, None, error="psutil not installed")
    except Exception as exc:
        return ComponentHealth("storage", Status.UNKNOWN, None, error=str(exc))


# ── Aggregator ────────────────────────────────────────────────────────────────

# Components whose UNHEALTHY state drives top-level UNHEALTHY
_CRITICAL = {"database", "reasoning_engine", "session_manager"}

_ALL_CHECKS = [
    _check_database,
    _check_reasoning_engine,
    _check_model_registry,
    _check_session_manager,
    _check_event_bus,
    _check_feature_store,
    _check_ai_lifecycle,
    _check_memory,
    _check_storage,
]


class HealthChecker:
    """Runs all component checks and produces a structured HealthReport."""

    def check_all(self) -> HealthReport:
        from backend.core.config import settings
        t0         = time.perf_counter()
        components = [fn() for fn in _ALL_CHECKS]
        elapsed_ms = (time.perf_counter() - t0) * 1000

        critical_unhealthy = any(
            c.status == Status.UNHEALTHY and c.name in _CRITICAL
            for c in components
        )
        any_unhealthy = any(c.status == Status.UNHEALTHY for c in components)
        any_degraded  = any(c.status in (Status.DEGRADED, Status.UNKNOWN) for c in components)

        if critical_unhealthy:
            overall = Status.UNHEALTHY
        elif any_unhealthy or any_degraded:
            overall = Status.DEGRADED
        else:
            overall = Status.HEALTHY

        return HealthReport(
            status      = overall,
            checked_at  = time.time(),
            duration_ms = elapsed_ms,
            version     = settings.APP_VERSION,
            environment = "development" if settings.DEBUG else "production",
            components  = components,
        )

    def check_readiness(self) -> bool:
        """Fast check: is the system ready to serve requests?"""
        db = _check_database()
        re = _check_reasoning_engine()
        return (
            db.status == Status.HEALTHY and
            re.status in (Status.HEALTHY, Status.DEGRADED)
        )

    def check_dependencies(self) -> Dict:
        """External dependency statuses (DB, optional cloud services)."""
        deps: Dict[str, Dict] = {}

        # SQLite
        db = _check_database()
        deps["sqlite"] = {"status": db.status.value, "latency_ms": db.latency_ms, "error": db.error}

        # Supabase (optional)
        try:
            from backend.core.config import settings
            if settings.SUPABASE_URL:
                deps["supabase"] = {"status": "configured", "url_set": True}
            else:
                deps["supabase"] = {"status": "not_configured"}
        except Exception:
            deps["supabase"] = {"status": "unknown"}

        return {"dependencies": deps, "checked_at": time.time()}


health_checker = HealthChecker()
