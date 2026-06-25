"""
System Router — /system/* endpoints for health, observability, and benchmarking.

These endpoints make NeuroSync look like production software to any engineer
who opens the API docs. They demonstrate:
  - Structured health checking with sub-component status
  - Model registry with version and latency metadata
  - Live observability metrics
  - In-process benchmark suite (P50/P95/P99)
  - Readiness and liveness probes (Kubernetes-compatible)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict

from fastapi import APIRouter

from backend.core.registry.model_registry import model_registry
from backend.core.config import settings

router = APIRouter(prefix="/system", tags=["System"])


def _db_check() -> Dict:
    try:
        import backend.services.db_service as db
        conn = db.get_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _memory_stats() -> Dict:
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "used_mb":      round((mem.total - mem.available) / 1e6, 1),
            "available_mb": round(mem.available / 1e6, 1),
            "percent":      mem.percent,
        }
    except ImportError:
        return {"status": "psutil_unavailable"}


def _process_stats() -> Dict:
    try:
        import psutil, os
        proc = psutil.Process(os.getpid())
        return {
            "pid":         proc.pid,
            "cpu_percent": proc.cpu_percent(interval=0.1),
            "memory_mb":   round(proc.memory_info().rss / 1e6, 1),
            "threads":     proc.num_threads(),
        }
    except Exception:
        return {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/health", summary="Detailed health check with sub-component status")
async def health():
    try:
        from backend.health.checker import health_checker
        report = health_checker.check_all()
        return report.to_dict()
    except Exception:
        # Fallback to legacy format if health module not yet available
        from backend.services.session_manager import session_manager
        db_status     = _db_check()
        mem_stats     = _memory_stats()
        proc_stats    = _process_stats()
        active_sessions = len(session_manager._sessions)
        models_ok     = all(m.status == "active" for m in model_registry.all())
        overall       = "healthy" if db_status["status"] == "ok" and models_ok else "degraded"
        return {
            "status":           overall,
            "timestamp":        time.time(),
            "version":          settings.APP_VERSION,
            "environment":      "development" if settings.DEBUG else "production",
            "database":         db_status,
            "reasoning_engine": "active",
            "models": {"total": len(model_registry.all()), "active": len(model_registry.active())},
            "sessions": {"active": active_sessions},
            "memory":   mem_stats,
            "process":  proc_stats,
        }


@router.get("/liveness", summary="Liveness probe — is the process alive?")
async def liveness():
    """Kubernetes-compatible liveness probe. Always 200 if process is running."""
    return {"alive": True, "timestamp": time.time()}


@router.get("/readiness", summary="Readiness probe — is the system ready to handle requests?")
async def readiness():
    """
    Kubernetes-compatible readiness probe.
    Returns 200 when database is reachable and models are loaded.
    Returns 503 when not ready.
    """
    from fastapi import HTTPException
    db_status = _db_check()
    models_ready = any(m.status == "active" for m in model_registry.all())

    if db_status["status"] != "ok" or not models_ready:
        raise HTTPException(
            status_code=503,
            detail={
                "ready":    False,
                "database": db_status,
                "models":   models_ready,
            },
        )
    return {"ready": True, "timestamp": time.time()}


@router.get("/version", summary="Application version and build metadata")
async def version():
    return {
        "name":      settings.APP_NAME,
        "version":   settings.APP_VERSION,
        "phase":     12,
        "engine":    "MBA (Multimodal Behavioral Analysis)",
        "reasoning": "Evidence Graph + Temporal Reasoning + Behavioral State Machine",
        "timestamp": time.time(),
    }


@router.get("/models", summary="Registered AI model catalog with version and latency metadata")
async def models():
    """
    Returns the model registry — every AI model in the system with:
      - version, framework, checkpoint
      - training dataset and date
      - macro F1 score (when available)
      - inference latency (EMA)
      - memory footprint
      - supported tasks
    """
    return model_registry.summary()


@router.get("/metrics", summary="Live system and pipeline observability metrics")
async def metrics():
    from backend.services.metrics_service import metrics_service
    return {
        "inference":  metrics_service.get_inference_stats(),
        "websocket":  metrics_service.get_websocket_stats(),
        "event_bus":  _event_bus_stats(),
        "sessions":   _session_stats(),
    }


@router.get("/config", summary="Active configuration (redacted)")
async def config():
    return {
        "whisper_model":  settings.WHISPER_MODEL,
        "whisper_device": settings.WHISPER_DEVICE,
        "window_seconds": settings.WINDOW_SIZE_SECONDS,
        "analytics_fps":  settings.ANALYTICS_FPS,
        "dataset_dir":    settings.DATASET_DIR,
        "dataset_auto_save": settings.DATASET_AUTO_SAVE,
        "allowed_origins": settings.ALLOWED_ORIGINS,
    }


@router.get("/benchmark", summary="Run in-process reasoning benchmark — P50/P95/P99 latency")
async def benchmark():
    """
    Runs the full reasoning benchmark suite without invoking ML models.
    Tests: evidence graph, temporal analysis, state machine, context rules, calibration.
    Typical total duration: 1-2 seconds.
    """
    from backend.benchmarks.pipeline_benchmark import run_quick_benchmark
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, run_quick_benchmark)
    return results


# ── Private helpers ───────────────────────────────────────────────────────────

def _event_bus_stats() -> Dict:
    try:
        from backend.core.events.bus import event_bus
        return event_bus.stats()
    except Exception:
        return {}


def _session_stats() -> Dict:
    try:
        from backend.services.session_manager import session_manager
        sessions = list(session_manager._sessions.values())
        return {
            "active_count": len(sessions),
            "states": {s.status.value: 1 for s in sessions},
        }
    except Exception:
        return {}
