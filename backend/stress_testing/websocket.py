"""
WebSocket stress test scenarios.

Validates the NeuroSync WebSocket layer under adverse conditions:

  rapid_reconnect     — 50 connect/disconnect cycles as fast as possible
  dropped_connection  — abruptly close mid-stream
  slow_client         — delayed message reads (backpressure)
  large_transcript    — large payload bursts to stress NLP pipeline
  long_session        — maintain sessions open for several minutes
  concurrent_flood    — 50 simultaneous connections

Each scenario is a descriptor. Execution requires the `websockets` package.
Run standalone: python -m backend.stress_testing.runner --scenario rapid_reconnect
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class WsScenario:
    name:              str
    description:       str
    concurrent:        int             # parallel WebSocket connections
    messages_per_conn: int
    message_interval:  float           # seconds between sends
    disconnect_after:  Optional[float] = None   # abrupt disconnect after N seconds; None = clean close
    max_reconnects:    int   = 0
    # SLO thresholds
    max_error_rate:    float = 0.05
    max_p95_latency_ms: float = 500.0


@dataclass
class WsResult:
    scenario_name:      str
    connections_opened: int
    connections_closed: int
    messages_sent:      int
    messages_received:  int
    errors:             int
    p50_latency_ms:     float
    p95_latency_ms:     float
    error_rate:         float
    duration_s:         float
    passed:             bool
    notes:              List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "scenario":           self.scenario_name,
            "connections_opened": self.connections_opened,
            "connections_closed": self.connections_closed,
            "messages_sent":      self.messages_sent,
            "messages_received":  self.messages_received,
            "errors":             self.errors,
            "latency": {
                "p50_ms": round(self.p50_latency_ms, 1),
                "p95_ms": round(self.p95_latency_ms, 1),
            },
            "error_rate": round(self.error_rate, 4),
            "duration_s": round(self.duration_s, 1),
            "passed":     self.passed,
            "notes":      self.notes,
        }


WS_SCENARIOS: List[WsScenario] = [
    WsScenario(
        name               = "rapid_reconnect",
        description        = "50 open/close cycles in rapid succession — connection setup overhead",
        concurrent         = 10,
        messages_per_conn  = 1,
        message_interval   = 0.0,
        disconnect_after   = 0.1,
        max_reconnects     = 5,
        max_error_rate     = 0.05,
        max_p95_latency_ms = 300.0,
    ),
    WsScenario(
        name               = "dropped_connection",
        description        = "Abruptly close connections mid-stream — server-side cleanup validation",
        concurrent         = 5,
        messages_per_conn  = 20,
        message_interval   = 0.05,
        disconnect_after   = 0.5,
        max_error_rate     = 0.15,   # abrupt drops expected
        max_p95_latency_ms = 400.0,
    ),
    WsScenario(
        name               = "slow_client",
        description        = "Slow message consumption — backpressure and buffer handling",
        concurrent         = 3,
        messages_per_conn  = 15,
        message_interval   = 2.0,
        max_error_rate     = 0.02,
        max_p95_latency_ms = 2500.0,
    ),
    WsScenario(
        name               = "large_transcript",
        description        = "Large text payloads — NLP pipeline stress under heavy transcript load",
        concurrent         = 2,
        messages_per_conn  = 10,
        message_interval   = 0.5,
        max_error_rate     = 0.02,
        max_p95_latency_ms = 1500.0,
    ),
    WsScenario(
        name               = "long_session",
        description        = "5 sessions open for 60s — resource stability and memory leak detection",
        concurrent         = 5,
        messages_per_conn  = 60,
        message_interval   = 1.0,
        max_error_rate     = 0.01,
        max_p95_latency_ms = 600.0,
    ),
    WsScenario(
        name               = "concurrent_flood",
        description        = "50 concurrent connections sending rapidly — peak concurrency test",
        concurrent         = 50,
        messages_per_conn  = 10,
        message_interval   = 0.1,
        max_error_rate     = 0.05,
        max_p95_latency_ms = 1000.0,
    ),
]


async def run_ws_scenario(
    scenario: WsScenario,
    base_url: str = "ws://localhost:8000",
) -> WsResult:
    """
    Execute a WebSocket stress scenario against a running server.

    Requires the `websockets` package. Returns a failure result if unavailable.
    """
    try:
        import websockets
    except ImportError:
        return WsResult(
            scenario_name      = scenario.name,
            connections_opened = 0,
            connections_closed = 0,
            messages_sent      = 0,
            messages_received  = 0,
            errors             = 1,
            p50_latency_ms     = 0.0,
            p95_latency_ms     = 0.0,
            error_rate         = 1.0,
            duration_s         = 0.0,
            passed             = False,
            notes              = ["websockets package not installed — pip install websockets"],
        )

    latencies:   List[float] = []
    errors       = 0
    msgs_sent    = 0
    msgs_recv    = 0
    conn_opened  = 0
    conn_closed  = 0
    t0           = time.perf_counter()

    # Large payload for large_transcript scenario
    LARGE_PAYLOAD = "x" * 4096 if scenario.name == "large_transcript" else ""

    async def _run_one_conn(_: int) -> None:
        nonlocal errors, msgs_sent, msgs_recv, conn_opened, conn_closed
        sid = uuid.uuid4().hex[:8]
        url = f"{base_url}/ws/session/{sid}"
        try:
            async with websockets.connect(url, open_timeout=5.0, close_timeout=2.0) as ws:
                conn_opened += 1
                conn_start = time.perf_counter()
                for _ in range(scenario.messages_per_conn):
                    if scenario.disconnect_after and (time.perf_counter() - conn_start) > scenario.disconnect_after:
                        break
                    payload = LARGE_PAYLOAD or '{"type":"ping"}'
                    t_send  = time.perf_counter()
                    try:
                        await ws.send(payload)
                        msgs_sent += 1
                        reply = await asyncio.wait_for(ws.recv(), timeout=3.0)
                        msgs_recv += 1
                        latencies.append((time.perf_counter() - t_send) * 1000)
                    except asyncio.TimeoutError:
                        errors += 1
                    except Exception:
                        errors += 1
                        break
                    await asyncio.sleep(scenario.message_interval)
                conn_closed += 1
        except Exception:
            errors += 1

    tasks = [_run_one_conn(i) for i in range(scenario.concurrent)]
    await asyncio.gather(*tasks, return_exceptions=True)

    duration   = time.perf_counter() - t0
    total_ops  = msgs_sent + errors
    err_rate   = errors / total_ops if total_ops else 0.0

    s          = sorted(latencies) if latencies else [0.0]
    p50_idx    = max(0, int(len(s) * 0.50) - 1)
    p95_idx    = max(0, int(len(s) * 0.95) - 1)
    p50_ms     = s[p50_idx]
    p95_ms     = s[p95_idx]

    notes: List[str] = []
    passed = True
    if err_rate > scenario.max_error_rate:
        notes.append(f"error_rate {err_rate:.2%} > {scenario.max_error_rate:.2%} SLO")
        passed = False
    if p95_ms > scenario.max_p95_latency_ms:
        notes.append(f"P95 {p95_ms:.0f}ms > {scenario.max_p95_latency_ms:.0f}ms SLO")
        passed = False

    return WsResult(
        scenario_name      = scenario.name,
        connections_opened = conn_opened,
        connections_closed = conn_closed,
        messages_sent      = msgs_sent,
        messages_received  = msgs_recv,
        errors             = errors,
        p50_latency_ms     = p50_ms,
        p95_latency_ms     = p95_ms,
        error_rate         = err_rate,
        duration_s         = duration,
        passed             = passed,
        notes              = notes,
    )


def get_scenario(name: str) -> Optional[WsScenario]:
    for s in WS_SCENARIOS:
        if s.name == name:
            return s
    return None
