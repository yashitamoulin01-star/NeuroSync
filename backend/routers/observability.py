"""
Observability Router — /metrics, /health/*, /system/alerts, /system/resources.

Serves Prometheus-compatible metrics, detailed health reports, and alert status
for production monitoring integrations (Grafana, PagerDuty, Datadog, etc.).

Endpoints:
  GET  /metrics                  — Prometheus text exposition (scrape target)
  GET  /metrics/json             — Same data as JSON
  GET  /health/live              — Liveness probe  (always 200 while process runs)
  GET  /health/ready             — Readiness probe (200 | 503)
  GET  /health/full              — Full multi-component health report
  GET  /health/dependencies      — External dependency status
  GET  /system/alerts            — Active alert evaluation
  GET  /system/resources         — Live system resource utilisation
"""

from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, JSONResponse

router = APIRouter(tags=["Observability"])


# ── Prometheus scrape endpoint ────────────────────────────────────────────────

@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Prometheus text metrics scrape endpoint",
    include_in_schema=True,
)
async def prometheus_metrics() -> PlainTextResponse:
    """
    Standard Prometheus text exposition format (version 0.0.4).
    Add this URL as a scrape target in prometheus.yml.
    """
    _refresh_resource_metrics()
    from backend.monitoring.metrics import registry
    return PlainTextResponse(
        content=registry.render_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/metrics/json", summary="Metrics as JSON (for dashboards without Prometheus)")
async def metrics_json() -> Dict[str, Any]:
    _refresh_resource_metrics()
    from backend.monitoring.metrics import registry
    return registry.to_dict()


# ── Health probes ─────────────────────────────────────────────────────────────

@router.get("/health/live", summary="Liveness probe — always 200 while process is alive")
async def health_liveness():
    return {"alive": True, "timestamp": time.time()}


@router.get("/health/ready", summary="Readiness probe — 200 when ready, 503 when not")
async def health_readiness():
    from backend.health.checker import health_checker
    ready = health_checker.check_readiness()
    status_code = 200 if ready else 503
    return JSONResponse(
        status_code=status_code,
        content={"ready": ready, "timestamp": time.time()},
    )


@router.get("/health/full", summary="Full multi-component health report")
async def health_full():
    from backend.health.checker import health_checker
    report = health_checker.check_all()
    return report.to_dict()


@router.get("/health/dependencies", summary="External dependency connectivity status")
async def health_dependencies():
    from backend.health.checker import health_checker
    return health_checker.check_dependencies()


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.get("/system/alerts", summary="Active alert evaluation — firing rules and levels")
async def system_alerts():
    from backend.monitoring.alerts import alert_manager
    report = alert_manager.evaluate()
    return {
        "evaluated_at":  report.evaluated_at,
        "total_rules":   report.total_rules,
        "firing":        report.firing,
        "healthy":       report.healthy,
        "alerts": [
            {
                "name":        a.name,
                "level":       a.level.value,
                "message":     a.message,
                "fired_at":    a.fired_at,
                "age_seconds": int(time.time() - a.fired_at),
            }
            for a in report.alerts
        ],
    }


# ── Resource snapshot ─────────────────────────────────────────────────────────

@router.get("/system/resources", summary="Live system resource utilisation snapshot")
async def system_resources():
    """
    Returns CPU, memory, disk, and process-level resource usage.
    Does not require the Prometheus scrape cycle — useful for ad-hoc checks.
    """
    result: Dict[str, Any] = {"timestamp": time.time()}
    try:
        import os, psutil
        mem  = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        proc = psutil.Process(os.getpid())

        result["system"] = {
            "cpu_percent":        psutil.cpu_percent(interval=None),
            "cpu_count":          psutil.cpu_count(logical=True),
            "memory_total_mb":    round(mem.total    / 1e6, 1),
            "memory_used_mb":     round(mem.used     / 1e6, 1),
            "memory_available_mb": round(mem.available / 1e6, 1),
            "memory_percent":     mem.percent,
            "disk_total_gb":      round(disk.total / 1e9, 1),
            "disk_used_gb":       round(disk.used  / 1e9, 1),
            "disk_free_gb":       round(disk.free  / 1e9, 1),
            "disk_percent":       disk.percent,
        }
        result["process"] = {
            "pid":          proc.pid,
            "memory_rss_mb": round(proc.memory_info().rss / 1e6, 1),
            "memory_vms_mb": round(proc.memory_info().vms / 1e6, 1),
            "cpu_percent":  proc.cpu_percent(interval=None),
            "threads":      proc.num_threads(),
            "open_files":   len(proc.open_files()),
        }
    except ImportError:
        result["error"] = "psutil not installed — pip install psutil"
    except Exception as exc:
        result["error"] = str(exc)

    return result


# ── Private helpers ───────────────────────────────────────────────────────────

def _refresh_resource_metrics() -> None:
    """Update system resource gauges before each scrape."""
    try:
        import os, psutil
        from backend.monitoring.metrics import system_memory_used_bytes, system_cpu_percent
        proc = psutil.Process(os.getpid())
        system_memory_used_bytes.set(proc.memory_info().rss)
        system_cpu_percent.set(proc.cpu_percent(interval=None))
    except Exception:
        pass
