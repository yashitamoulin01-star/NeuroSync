"""
Operational alert system.

Alert rules are evaluated against live system state on demand.
Each rule is a callable that returns None (healthy) or a string (alert message).

Alert levels:
  INFO     — noteworthy, no action required
  WARNING  — investigate at next opportunity
  CRITICAL — requires immediate attention

Usage:
    report = alert_manager.evaluate()
    if not report.healthy:
        for alert in report.alerts:
            logger.critical("ALERT [%s] %s", alert.level, alert.message)

GET /system/alerts  exposes this report via the observability API.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional


class AlertLevel(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    name:        str
    level:       AlertLevel
    description: str
    check:       Callable[[], Optional[str]]   # None = healthy, str = alert message


@dataclass
class ActiveAlert:
    name:      str
    level:     AlertLevel
    message:   str
    fired_at:  float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "name":        self.name,
            "level":       self.level.value,
            "message":     self.message,
            "fired_at":    self.fired_at,
            "age_seconds": round(time.time() - self.fired_at),
        }


@dataclass
class AlertReport:
    evaluated_at: float
    total_rules:  int
    firing:       int
    healthy:      bool
    alerts:       List[ActiveAlert] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "evaluated_at": self.evaluated_at,
            "total_rules":  self.total_rules,
            "firing":       self.firing,
            "healthy":      self.healthy,
            "alerts":       [a.to_dict() for a in self.alerts],
        }


# ── Built-in alert checks ─────────────────────────────────────────────────────

def _check_database() -> Optional[str]:
    try:
        import backend.services.db_service as db
        conn = db.get_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception as exc:
        return f"Database unavailable: {exc}"
    return None


def _check_system_memory() -> Optional[str]:
    try:
        import psutil
        pct = psutil.virtual_memory().percent
        if pct > 95:
            return f"System memory critical: {pct:.1f}% used"
        if pct > 85:
            return f"System memory elevated: {pct:.1f}% used"
    except ImportError:
        pass
    return None


def _check_process_memory() -> Optional[str]:
    try:
        import os, psutil
        rss_mb = psutil.Process(os.getpid()).memory_info().rss / 1_000_000
        if rss_mb > 3000:
            return f"Process memory critical: {rss_mb:.0f} MB RSS"
        if rss_mb > 1500:
            return f"Process memory elevated: {rss_mb:.0f} MB RSS"
    except Exception:
        pass
    return None


def _check_inference_latency() -> Optional[str]:
    try:
        from backend.services.metrics_service import metrics_service
        stats = metrics_service.get_inference_stats()
        for component, data in stats.items():
            p95 = data.get("p95")
            if p95 is not None and p95 > 5_000:
                return f"Inference latency critical: {component} P95={p95:.0f} ms"
            if p95 is not None and p95 > 2_000:
                return f"Inference latency elevated: {component} P95={p95:.0f} ms"
    except Exception:
        pass
    return None


def _check_active_sessions() -> Optional[str]:
    try:
        from backend.services.session_manager import session_manager
        count = len(session_manager._sessions)
        if count > 200:
            return f"Excessive active sessions: {count} (possible leak)"
        if count > 100:
            return f"High active session count: {count}"
    except Exception:
        pass
    return None


def _check_golden_suite() -> Optional[str]:
    try:
        from backend.monitoring.metrics import golden_suite_pass_rate
        samples = golden_suite_pass_rate.samples()
        if samples:
            rate = samples[0].value
            if 0 < rate < 0.80:
                return f"Golden suite pass rate degraded: {rate:.1%} (< 80%)"
            if 0 < rate < 0.95:
                return f"Golden suite pass rate below target: {rate:.1%} (< 95%)"
    except Exception:
        pass
    return None


def _check_http_error_rate() -> Optional[str]:
    try:
        from backend.monitoring.metrics import http_errors_total, http_requests_total
        errors   = sum(s.value for s in http_errors_total.samples())
        requests = sum(s.value for s in http_requests_total.samples())
        if requests >= 50:
            rate = errors / requests
            if rate > 0.10:
                return f"HTTP 5xx error rate critical: {rate:.1%}"
            if rate > 0.02:
                return f"HTTP 5xx error rate elevated: {rate:.1%}"
    except Exception:
        pass
    return None


def _check_ws_error_rate() -> Optional[str]:
    try:
        from backend.monitoring.metrics import ws_errors_total, ws_messages_total
        errors = sum(s.value for s in ws_errors_total.samples())
        msgs   = sum(s.value for s in ws_messages_total.samples())
        if msgs >= 20 and errors / msgs > 0.15:
            return f"WebSocket error rate high: {errors/msgs:.1%}"
    except Exception:
        pass
    return None


def _check_disk_space() -> Optional[str]:
    try:
        import psutil
        disk = psutil.disk_usage(".")
        if disk.percent > 95:
            return f"Disk space critical: {disk.percent:.1f}% used ({disk.free // 2**30} GB free)"
        if disk.percent > 85:
            return f"Disk space low: {disk.percent:.1f}% used"
    except Exception:
        pass
    return None


# ── Alert manager ─────────────────────────────────────────────────────────────

class AlertManager:
    """
    Evaluates all registered alert rules and returns an AlertReport.

    Rules are evaluated synchronously — call from a background task for
    continuous monitoring, or on-demand from the /system/alerts endpoint.
    """

    def __init__(self):
        self._rules: List[AlertRule] = [
            AlertRule("database_unavailable",  AlertLevel.CRITICAL, "SQLite database unreachable",            _check_database),
            AlertRule("memory_critical",       AlertLevel.CRITICAL, "System memory usage critical",           _check_system_memory),
            AlertRule("process_memory_high",   AlertLevel.WARNING,  "Process RSS memory elevated",            _check_process_memory),
            AlertRule("inference_latency",     AlertLevel.WARNING,  "Inference pipeline P95 latency high",    _check_inference_latency),
            AlertRule("sessions_excessive",    AlertLevel.WARNING,  "Concurrent session count abnormally high", _check_active_sessions),
            AlertRule("golden_suite",          AlertLevel.CRITICAL, "Golden test suite pass rate degraded",   _check_golden_suite),
            AlertRule("http_error_rate",       AlertLevel.WARNING,  "HTTP 5xx error rate elevated",           _check_http_error_rate),
            AlertRule("ws_error_rate",         AlertLevel.WARNING,  "WebSocket error rate elevated",          _check_ws_error_rate),
            AlertRule("disk_space",            AlertLevel.WARNING,  "Disk space running low",                 _check_disk_space),
        ]

    def register(self, rule: AlertRule) -> None:
        """Register a custom alert rule."""
        self._rules.append(rule)

    def evaluate(self) -> AlertReport:
        """Run all rules and return an AlertReport."""
        alerts: List[ActiveAlert] = []
        for rule in self._rules:
            try:
                msg = rule.check()
                if msg:
                    alerts.append(ActiveAlert(name=rule.name, level=rule.level, message=msg))
            except Exception as exc:
                alerts.append(ActiveAlert(
                    name    = rule.name,
                    level   = AlertLevel.WARNING,
                    message = f"Alert check threw exception: {exc}",
                ))

        critical_firing = any(a.level == AlertLevel.CRITICAL for a in alerts)
        return AlertReport(
            evaluated_at = time.time(),
            total_rules  = len(self._rules),
            firing       = len(alerts),
            healthy      = not critical_firing,
            alerts       = alerts,
        )

    def rules_summary(self) -> List[Dict]:
        return [{"name": r.name, "level": r.level.value, "description": r.description}
                for r in self._rules]


alert_manager = AlertManager()
