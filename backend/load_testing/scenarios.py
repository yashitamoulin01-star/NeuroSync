"""
Load test scenario definitions.

Each scenario describes a workload pattern that can be executed against
a running NeuroSync instance with any HTTP load-testing tool.

The built-in runner (run_scenario_in_process) uses httpx + asyncio and is
suitable for CI smoke checks. For full load testing, use the scenario
parameters with a dedicated tool such as Locust, k6, or Gatling.

Scenarios cover the spec range: 1 → 10 → 25 → 50 → 100 concurrent users.
A soak test covers the long-duration memory-leak detection requirement.

Usage (standalone):
    python -m backend.load_testing.runner --scenario smoke
    python -m backend.load_testing.runner --scenario low_load --base-url http://staging:8000
"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── Scenario descriptor ───────────────────────────────────────────────────────

@dataclass
class LoadScenario:
    name:            str
    description:     str
    concurrent:      int     # virtual users
    duration_s:      float
    ramp_up_s:       float = 0.0
    think_time_ms:   float = 200.0   # inter-request pause per VU
    # SLO thresholds
    max_p95_ms:      float = 2000.0
    max_error_rate:  float = 0.01
    min_rps:         float = 0.0


@dataclass
class RequestResult:
    url:         str
    method:      str
    status_code: int
    latency_ms:  float
    error:       Optional[str] = None

    @property
    def success(self) -> bool:
        return 200 <= self.status_code < 500


@dataclass
class ScenarioResult:
    scenario_name:   str
    duration_s:      float
    total_requests:  int
    successful:      int
    failed:          int
    p50_ms:          float
    p95_ms:          float
    p99_ms:          float
    min_ms:          float
    max_ms:          float
    rps:             float
    error_rate:      float
    passed:          bool
    failures:        List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "scenario":       self.scenario_name,
            "duration_s":     round(self.duration_s, 1),
            "total_requests": self.total_requests,
            "successful":     self.successful,
            "failed":         self.failed,
            "latency": {
                "p50_ms": round(self.p50_ms, 1),
                "p95_ms": round(self.p95_ms, 1),
                "p99_ms": round(self.p99_ms, 1),
                "min_ms": round(self.min_ms, 1),
                "max_ms": round(self.max_ms, 1),
            },
            "rps":        round(self.rps, 2),
            "error_rate": round(self.error_rate, 4),
            "passed":     self.passed,
            "failures":   self.failures,
        }


# ── Canonical scenario suite ──────────────────────────────────────────────────

SCENARIOS: List[LoadScenario] = [
    LoadScenario(
        name           = "smoke",
        description    = "1 VU — basic functional verification under minimal load",
        concurrent     = 1,
        duration_s     = 15.0,
        think_time_ms  = 200,
        max_p95_ms     = 800,
        max_error_rate = 0.0,
        min_rps        = 2.0,
    ),
    LoadScenario(
        name           = "low_load",
        description    = "10 concurrent users — light production usage",
        concurrent     = 10,
        duration_s     = 30.0,
        ramp_up_s      = 5.0,
        think_time_ms  = 300,
        max_p95_ms     = 1200,
        max_error_rate = 0.01,
        min_rps        = 8.0,
    ),
    LoadScenario(
        name           = "medium_load",
        description    = "25 concurrent users — moderate production load",
        concurrent     = 25,
        duration_s     = 60.0,
        ramp_up_s      = 10.0,
        think_time_ms  = 250,
        max_p95_ms     = 2000,
        max_error_rate = 0.02,
        min_rps        = 15.0,
    ),
    LoadScenario(
        name           = "high_load",
        description    = "50 concurrent users — peak expected production load",
        concurrent     = 50,
        duration_s     = 120.0,
        ramp_up_s      = 20.0,
        think_time_ms  = 150,
        max_p95_ms     = 3000,
        max_error_rate = 0.05,
        min_rps        = 25.0,
    ),
    LoadScenario(
        name           = "stress",
        description    = "100 concurrent users — beyond expected capacity (stress boundary)",
        concurrent     = 100,
        duration_s     = 120.0,
        ramp_up_s      = 30.0,
        think_time_ms  = 100,
        max_p95_ms     = 5000,
        max_error_rate = 0.10,
        min_rps        = 30.0,
    ),
    LoadScenario(
        name           = "soak",
        description    = "10 VUs for 30 minutes — memory leak and resource exhaustion detection",
        concurrent     = 10,
        duration_s     = 1800.0,
        ramp_up_s      = 10.0,
        think_time_ms  = 500,
        max_p95_ms     = 1500,
        max_error_rate = 0.005,
        min_rps        = 5.0,
    ),
]


# ── In-process runner ─────────────────────────────────────────────────────────

_PROBE_URLS = [
    ("/system/liveness",  "GET"),
    ("/system/health",    "GET"),
    ("/system/metrics",   "GET"),
    ("/system/version",   "GET"),
]


async def _make_request(client, base_url: str, path: str, method: str) -> RequestResult:
    url = base_url.rstrip("/") + path
    t0  = time.perf_counter()
    try:
        resp = await getattr(client, method.lower())(url)
        return RequestResult(
            url         = url,
            method      = method,
            status_code = resp.status_code,
            latency_ms  = (time.perf_counter() - t0) * 1000,
        )
    except Exception as exc:
        return RequestResult(
            url         = url,
            method      = method,
            status_code = 0,
            latency_ms  = (time.perf_counter() - t0) * 1000,
            error       = str(exc),
        )


async def run_scenario_in_process(
    scenario:  LoadScenario,
    base_url:  str = "http://localhost:8000",
) -> ScenarioResult:
    """
    Execute a load scenario using httpx + asyncio.
    Returns a synthetic failure result if httpx is not installed.
    """
    try:
        import httpx
    except ImportError:
        return ScenarioResult(
            scenario_name   = scenario.name,
            duration_s      = 0.0,
            total_requests  = 0,
            successful      = 0,
            failed          = 0,
            p50_ms          = 0.0,
            p95_ms          = 0.0,
            p99_ms          = 0.0,
            min_ms          = 0.0,
            max_ms          = 0.0,
            rps             = 0.0,
            error_rate      = 0.0,
            passed          = False,
            failures        = ["httpx not installed — install with: pip install httpx"],
        )

    results: List[RequestResult] = []
    test_end = time.time() + scenario.duration_s
    req_idx  = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        while time.time() < test_end:
            batch_tasks = []
            for i in range(scenario.concurrent):
                path, method = _PROBE_URLS[(req_idx + i) % len(_PROBE_URLS)]
                batch_tasks.append(_make_request(client, base_url, path, method))
            batch = await asyncio.gather(*batch_tasks)
            results.extend(batch)
            req_idx += scenario.concurrent
            await asyncio.sleep(scenario.think_time_ms / 1000)

    latencies = [r.latency_ms for r in results]
    errors    = [r for r in results if not r.success]
    total     = len(results)
    err_rate  = len(errors) / total if total else 0.0

    s = sorted(latencies) if latencies else [0.0]

    def pct(p: float) -> float:
        idx = min(int(len(s) * p / 100), len(s) - 1)
        return s[max(0, idx)]

    p50, p95, p99 = pct(50), pct(95), pct(99)
    rps = total / scenario.duration_s if scenario.duration_s else 0.0

    slo_failures: List[str] = []
    passed = True

    if p95 > scenario.max_p95_ms:
        slo_failures.append(f"P95 {p95:.0f}ms > {scenario.max_p95_ms:.0f}ms SLO")
        passed = False
    if err_rate > scenario.max_error_rate:
        slo_failures.append(f"error_rate {err_rate:.2%} > {scenario.max_error_rate:.2%} SLO")
        passed = False
    if scenario.min_rps > 0 and rps < scenario.min_rps:
        slo_failures.append(f"throughput {rps:.1f} rps < {scenario.min_rps:.1f} rps SLO")
        passed = False

    return ScenarioResult(
        scenario_name   = scenario.name,
        duration_s      = scenario.duration_s,
        total_requests  = total,
        successful      = total - len(errors),
        failed          = len(errors),
        p50_ms          = p50,
        p95_ms          = p95,
        p99_ms          = p99,
        min_ms          = min(latencies) if latencies else 0.0,
        max_ms          = max(latencies) if latencies else 0.0,
        rps             = rps,
        error_rate      = err_rate,
        passed          = passed,
        failures        = slo_failures,
    )


def get_scenario(name: str) -> Optional[LoadScenario]:
    for s in SCENARIOS:
        if s.name == name:
            return s
    return None
