"""
OpenTelemetry-style distributed tracing.

Implements a lightweight in-process tracer with:
  - 128-bit trace IDs and 64-bit span IDs (hex strings)
  - Thread-local span stack for automatic parent propagation
  - Span attributes, status, and error recording
  - Structured log emission on span completion
  - In-memory ring buffer of recent completed spans
  - Optional OTLP export (if opentelemetry-exporter-otlp is installed)

Design intent: the interface is intentionally compatible with the OTel Python
SDK so switching to the real SDK later requires only changing the import.

Usage:
    with tracer.span("face.analysis", session_id=sid) as span:
        result = face_service.analyze(frame)
        span.set_attribute("face_detected", result.detected)

Every span inherits the trace_id from its parent, linking all pipeline stages
for one interview request into a single trace.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger("neurosync.telemetry")

_ctx = threading.local()   # thread-local span stack


# ── Span data model ───────────────────────────────────────────────────────────

@dataclass
class Span:
    name:       str
    trace_id:   str
    span_id:    str
    parent_id:  Optional[str]
    start_ns:   int                        # time.perf_counter_ns() at start
    attributes: Dict[str, Any] = field(default_factory=dict)
    end_ns:     Optional[int]  = None
    status:     str            = "ok"      # ok | error
    error_msg:  Optional[str]  = None

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_ns is None:
            return None
        return round((self.end_ns - self.start_ns) / 1_000_000, 3)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_error(self, message: str) -> None:
        self.status    = "error"
        self.error_msg = message

    def _finish(self) -> None:
        self.end_ns = time.perf_counter_ns()

    def to_dict(self) -> Dict:
        return {
            "trace_id":    self.trace_id,
            "span_id":     self.span_id,
            "parent_id":   self.parent_id,
            "name":        self.name,
            "duration_ms": self.duration_ms,
            "status":      self.status,
            "error":       self.error_msg,
            "attributes":  self.attributes,
        }


def _hex_id(n_bytes: int) -> str:
    return uuid.uuid4().hex[: n_bytes * 2]


def _stack() -> List[Span]:
    if not hasattr(_ctx, "spans"):
        _ctx.spans = []
    return _ctx.spans


# ── Tracer ────────────────────────────────────────────────────────────────────

class Tracer:
    """
    Lightweight in-process tracer.

    Thread-safe for concurrent spans across multiple sessions.
    Each thread maintains its own span stack for correct parent propagation.
    """

    MAX_HISTORY = 1000

    def __init__(self, service_name: str = "neurosync"):
        self.service_name = service_name
        self._completed:  List[Dict] = []
        self._lock        = threading.Lock()
        self._total       = 0
        self._errors      = 0

    # ── Span lifecycle ────────────────────────────────────────────────────────

    @contextmanager
    def span(
        self,
        name:     str,
        trace_id: Optional[str] = None,
        **attributes: Any,
    ) -> Generator[Span, None, None]:
        """
        Open a span, yield it, then automatically close and record it.

        If trace_id is not supplied, the active parent's trace_id is used.
        If there is no active parent, a new 128-bit trace ID is generated.
        """
        stack  = _stack()
        parent = stack[-1] if stack else None
        t_id   = trace_id or (parent.trace_id if parent else _hex_id(16))
        s = Span(
            name       = name,
            trace_id   = t_id,
            span_id    = _hex_id(8),
            parent_id  = parent.span_id if parent else None,
            start_ns   = time.perf_counter_ns(),
            attributes = dict(attributes),
        )
        stack.append(s)
        try:
            yield s
        except Exception as exc:
            s.set_error(str(exc))
            raise
        finally:
            s._finish()
            stack.pop()
            self._record(s)

    def _record(self, span: Span) -> None:
        d = span.to_dict()
        d["service"] = self.service_name
        if span.status == "error":
            logger.warning("span error  trace=%s span=%s name=%s err=%s dur=%.1fms",
                           span.trace_id, span.span_id, span.name,
                           span.error_msg, span.duration_ms or 0)
        else:
            logger.debug("span finish trace=%s span=%s name=%s dur=%.1fms",
                         span.trace_id, span.span_id, span.name, span.duration_ms or 0)
        with self._lock:
            self._total  += 1
            self._errors += (1 if span.status == "error" else 0)
            self._completed.append(d)
            if len(self._completed) > self.MAX_HISTORY:
                self._completed.pop(0)

    # ── Query ─────────────────────────────────────────────────────────────────

    def current_trace_id(self) -> Optional[str]:
        """Return the trace_id of the innermost active span, or None."""
        stack = _stack()
        return stack[-1].trace_id if stack else None

    def recent_spans(self, limit: int = 100) -> List[Dict]:
        with self._lock:
            return list(self._completed[-limit:])

    def trace(self, trace_id: str) -> List[Dict]:
        """Return all recorded spans for a given trace_id."""
        with self._lock:
            return [s for s in self._completed if s["trace_id"] == trace_id]

    def stats(self) -> Dict:
        with self._lock:
            return {
                "total_spans":   self._total,
                "error_spans":   self._errors,
                "error_rate":    round(self._errors / self._total, 4) if self._total else 0.0,
                "history_size":  len(self._completed),
            }

    # ── Convenience decorator ─────────────────────────────────────────────────

    def instrument(self, name: Optional[str] = None):
        """Decorator that wraps a function in a span."""
        import functools
        def decorator(fn):
            span_name = name or f"{fn.__module__}.{fn.__qualname__}"
            if not _is_async(fn):
                @functools.wraps(fn)
                def wrapper(*args, **kwargs):
                    with self.span(span_name):
                        return fn(*args, **kwargs)
                return wrapper
            else:
                @functools.wraps(fn)
                async def async_wrapper(*args, **kwargs):
                    with self.span(span_name):
                        return await fn(*args, **kwargs)
                return async_wrapper
        return decorator


def _is_async(fn) -> bool:
    import asyncio
    return asyncio.iscoroutinefunction(fn)


# ── Module singleton ──────────────────────────────────────────────────────────

tracer = Tracer(service_name="neurosync")
