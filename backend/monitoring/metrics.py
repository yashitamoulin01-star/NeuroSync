"""
Prometheus-compatible metrics registry.

Implements counters, gauges, and histograms in pure Python with no external
dependency on prometheus_client. The text exposition format (version 0.0.4)
is simple enough to render natively.

Usage:
    from backend.monitoring.metrics import sessions_active, inference_latency
    sessions_active.set(3)
    inference_latency.observe(0.045, labels={"component": "face"})

Scrape endpoint: GET /metrics  (text/plain; version=0.0.4)
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ── Internal types ────────────────────────────────────────────────────────────

@dataclass
class _Sample:
    labels: Tuple  # sorted (k, v) pairs
    value:  float


# ── Metric implementations ────────────────────────────────────────────────────

class Counter:
    def __init__(self, name: str, help_text: str = ""):
        self.name      = name
        self.help_text = help_text
        self._lock     = threading.Lock()
        self._values: Dict[Tuple, float] = defaultdict(float)

    def increment(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[key] += amount

    def samples(self) -> List[_Sample]:
        with self._lock:
            return [_Sample(k, v) for k, v in self._values.items()]


class Gauge:
    def __init__(self, name: str, help_text: str = ""):
        self.name      = name
        self.help_text = help_text
        self._lock     = threading.Lock()
        self._values: Dict[Tuple, float] = defaultdict(float)

    def set(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[key] = value

    def increment(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[key] += amount

    def decrement(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment(-amount, labels)

    def samples(self) -> List[_Sample]:
        with self._lock:
            return [_Sample(k, v) for k, v in self._values.items()]


class Histogram:
    """
    Prometheus-style histogram with configurable buckets.
    Exposes *_bucket, *_count, *_sum metrics.
    """
    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(self, name: str, help_text: str = "", buckets: Optional[Tuple] = None):
        self.name      = name
        self.help_text = help_text
        self.buckets   = sorted(buckets or self.DEFAULT_BUCKETS)
        self._lock     = threading.Lock()
        # per-label-key: [bucket_counts[], total_count, total_sum]
        self._data: Dict[Tuple, list] = {}

    def _key(self, labels: Optional[Dict]) -> Tuple:
        return tuple(sorted((labels or {}).items()))

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        key = self._key(labels)
        with self._lock:
            if key not in self._data:
                self._data[key] = [[0] * len(self.buckets), 0, 0.0]
            entry = self._data[key]
            for i, b in enumerate(self.buckets):
                if value <= b:
                    entry[0][i] += 1
            entry[1] += 1
            entry[2] += value

    def snapshot(self) -> Dict:
        """Return simple dict summary for API responses."""
        with self._lock:
            all_values: List[float] = []
            for counts, total, s in self._data.values():
                # Reconstruct approximate values from buckets for percentile calc
                all_values.extend([s / total] * total if total > 0 else [])
            total_obs = sum(e[1] for e in self._data.values())
            total_sum = sum(e[2] for e in self._data.values())
            return {
                "total_observations": total_obs,
                "total_sum":          round(total_sum, 6),
                "mean":               round(total_sum / total_obs, 6) if total_obs else 0.0,
            }


# ── Registry ──────────────────────────────────────────────────────────────────

class MetricsRegistry:
    """Central registry — holds all metrics and renders Prometheus text."""

    def __init__(self):
        self._lock    = threading.Lock()
        self._metrics: Dict[str, object] = {}

    def counter(self, name: str, help_text: str = "") -> Counter:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Counter(name, help_text)
            return self._metrics[name]  # type: ignore

    def gauge(self, name: str, help_text: str = "") -> Gauge:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Gauge(name, help_text)
            return self._metrics[name]  # type: ignore

    def histogram(self, name: str, help_text: str = "", buckets: Optional[Tuple] = None) -> Histogram:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Histogram(name, help_text, buckets)
            return self._metrics[name]  # type: ignore

    def render_text(self) -> str:
        """Render all metrics in Prometheus text exposition format (v0.0.4)."""
        lines: List[str] = [f"# NeuroSync metrics — {time.strftime('%Y-%m-%dT%H:%M:%SZ')}"]
        with self._lock:
            snapshot = list(self._metrics.values())

        for m in snapshot:
            if isinstance(m, Counter):
                lines += [f"# HELP {m.name}_total {m.help_text}",
                          f"# TYPE {m.name}_total counter"]
                for s in m.samples():
                    lines.append(_fmt(m.name + "_total", s))

            elif isinstance(m, Gauge):
                lines += [f"# HELP {m.name} {m.help_text}",
                          f"# TYPE {m.name} gauge"]
                for s in m.samples():
                    lines.append(_fmt(m.name, s))

            elif isinstance(m, Histogram):
                lines += [f"# HELP {m.name} {m.help_text}",
                          f"# TYPE {m.name} histogram"]
                with m._lock:
                    for label_key, (counts, total, s) in m._data.items():
                        cumulative = 0
                        for b, c in zip(m.buckets, counts):
                            cumulative += c
                            bl = dict(label_key) | {"le": str(b)}
                            lines.append(_fmt(m.name + "_bucket", _Sample(tuple(sorted(bl.items())), cumulative)))
                        bl_inf = dict(label_key) | {"le": "+Inf"}
                        lines.append(_fmt(m.name + "_bucket", _Sample(tuple(sorted(bl_inf.items())), total)))
                        lines.append(_fmt(m.name + "_count", _Sample(label_key, total)))
                        lines.append(_fmt(m.name + "_sum",   _Sample(label_key, s)))

        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Return all metrics as a nested dict for JSON API responses."""
        result: Dict = {}
        with self._lock:
            snapshot = list(self._metrics.values())
        for m in snapshot:
            if isinstance(m, Counter):
                result[m.name] = {
                    "type":    "counter",
                    "samples": [{"labels": dict(s.labels), "value": s.value} for s in m.samples()],
                }
            elif isinstance(m, Gauge):
                result[m.name] = {
                    "type":    "gauge",
                    "samples": [{"labels": dict(s.labels), "value": s.value} for s in m.samples()],
                }
            elif isinstance(m, Histogram):
                result[m.name] = {"type": "histogram", **m.snapshot()}
        return result


def _fmt(name: str, s: _Sample) -> str:
    if not s.labels:
        return f"{name} {_fv(s.value)}"
    lbl = ",".join(f'{k}="{v}"' for k, v in s.labels)
    return f"{name}{{{lbl}}} {_fv(s.value)}"


def _fv(v: float) -> str:
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return repr(v)


# ── Singleton registry ────────────────────────────────────────────────────────

registry = MetricsRegistry()

# ── Platform metric declarations ──────────────────────────────────────────────

# Sessions
sessions_active       = registry.gauge(   "neurosync_sessions_active",         "Active interview sessions")
sessions_created      = registry.counter( "neurosync_sessions_created",         "Interview sessions created since startup")
sessions_completed    = registry.counter( "neurosync_sessions_completed",        "Interview sessions completed successfully")
sessions_error        = registry.counter( "neurosync_sessions_error",            "Sessions terminated with error")

# Frames
frames_processed      = registry.counter( "neurosync_frames_processed",          "Video/audio frames processed")
frames_dropped        = registry.counter( "neurosync_frames_dropped",            "Frames dropped due to queue pressure")

# Inference latency histograms (seconds)
inference_latency     = registry.histogram(
    "neurosync_inference_duration_seconds",
    "Per-component inference latency",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
reasoning_latency     = registry.histogram(
    "neurosync_reasoning_duration_seconds",
    "Reasoning pipeline latency",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
)

# Evidence & reports
evidence_generated    = registry.counter( "neurosync_evidence_generated",        "Behavioral evidence items produced")
reports_generated     = registry.counter( "neurosync_reports_generated",         "Session reports generated")

# WebSocket
ws_connections_active = registry.gauge(   "neurosync_ws_connections_active",     "Open WebSocket connections")
ws_messages_total     = registry.counter( "neurosync_ws_messages",               "WebSocket messages received")
ws_errors_total       = registry.counter( "neurosync_ws_errors",                 "WebSocket errors")
ws_disconnects_total  = registry.counter( "neurosync_ws_disconnects",            "WebSocket unexpected disconnections")

# HTTP
http_requests_total   = registry.counter( "neurosync_http_requests",             "HTTP requests by method and status")
http_request_duration = registry.histogram(
    "neurosync_http_request_duration_seconds",
    "HTTP request duration",
    buckets=(0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
http_errors_total     = registry.counter( "neurosync_http_errors",               "HTTP 5xx responses")

# AI platform
golden_suite_pass_rate    = registry.gauge("neurosync_golden_suite_pass_rate",   "Golden test suite pass rate (0–1)")
golden_suite_duration_ms  = registry.gauge("neurosync_golden_suite_duration_ms", "Last golden suite run duration ms")
stability_suite_pass_rate = registry.gauge("neurosync_stability_suite_pass_rate","Stability suite pass rate (0–1)")

# System resources (updated periodically by background worker)
system_memory_used_bytes  = registry.gauge("neurosync_system_memory_used_bytes", "RSS memory used by process")
system_cpu_percent        = registry.gauge("neurosync_system_cpu_percent",       "Process CPU utilisation %")
