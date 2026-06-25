"""
Pipeline Benchmark — P50/P95/P99 latency profiling for reasoning components.

Measures the pure reasoning stack (no ML models) to isolate architectural
performance from model inference time. These numbers demonstrate that the
reasoning layer adds negligible overhead on top of the ML models.

Accessible via GET /system/benchmark
"""

from __future__ import annotations

import statistics
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class BenchmarkResult:
    name:               str
    iterations:         int
    p50_ms:             float
    p95_ms:             float
    p99_ms:             float
    min_ms:             float
    max_ms:             float
    throughput_per_sec: float

    def to_dict(self) -> Dict:
        return {
            "name":               self.name,
            "iterations":         self.iterations,
            "p50_ms":             round(self.p50_ms, 3),
            "p95_ms":             round(self.p95_ms, 3),
            "p99_ms":             round(self.p99_ms, 3),
            "min_ms":             round(self.min_ms, 3),
            "max_ms":             round(self.max_ms, 3),
            "throughput_per_sec": round(self.throughput_per_sec, 1),
        }


def _measure(fn: Callable, iterations: int) -> List[float]:
    """Run fn() iterations times and return wall-clock times in milliseconds."""
    latencies: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        latencies.append((time.perf_counter() - t0) * 1000.0)
    return latencies


def _summarize(name: str, latencies: List[float]) -> BenchmarkResult:
    n = len(latencies)
    s = sorted(latencies)
    return BenchmarkResult(
        name               = name,
        iterations         = n,
        p50_ms             = statistics.median(s),
        p95_ms             = s[int(n * 0.95)],
        p99_ms             = s[int(n * 0.99)],
        min_ms             = s[0],
        max_ms             = s[-1],
        throughput_per_sec = 1000.0 / statistics.median(s) if statistics.median(s) > 0 else 0,
    )


# ── Benchmark scenarios ───────────────────────────────────────────────────────

def _bench_evidence_graph(iterations: int = 200) -> BenchmarkResult:
    from backend.models.evidence import (
        BehavioralEvidence, EvidenceDimension, EvidencePolarity,
    )
    from backend.reasoning.graph.evidence_graph import EvidenceGraph

    evidence = [
        BehavioralEvidence(id=f"e{i}", dimension=list(EvidenceDimension)[i % 5],
                           polarity=EvidencePolarity.POSITIVE if i % 2 == 0 else EvidencePolarity.NEGATIVE,
                           description=f"test evidence {i}",
                           source_modalities=["face" if i % 3 == 0 else "audio"],
                           contribution=0.2)
        for i in range(12)
    ]

    def run():
        EvidenceGraph().add_many(evidence).build()

    return _summarize("evidence_graph_build", _measure(run, iterations))


def _bench_temporal_analysis(iterations: int = 200) -> BenchmarkResult:
    from backend.reasoning.timeline.temporal_engine import ScoreSnapshot, analyze_temporal

    snapshots = [
        ScoreSnapshot(i, i * 15.0, 0.45 + i * 0.03, 0.60 - i * 0.03,
                      0.55, 0.60, 0.65, "medium")
        for i in range(20)
    ]

    def run():
        analyze_temporal(snapshots)

    return _summarize("temporal_analysis", _measure(run, iterations))


def _bench_behavioral_state(iterations: int = 500) -> BenchmarkResult:
    from backend.reasoning.state_machine.behavioral_state import BehavioralState, next_state

    def run():
        next_state(BehavioralState.SETTLING, 90.0, 0.65, 0.30, 0.60, 0.58, "stable")

    return _summarize("behavioral_state_transition", _measure(run, iterations))


def _bench_context_rules(iterations: int = 200) -> BenchmarkResult:
    from backend.models.evidence import BehavioralEvidence, EvidenceDimension, EvidencePolarity
    from backend.reasoning.graph.evidence_graph import EvidenceGraph
    from backend.reasoning.state_machine.behavioral_state import BehavioralState
    from backend.reasoning.rules.context_rules import RuleContext, evaluate_rules

    evidence = [
        BehavioralEvidence(id=f"e{i}", dimension=list(EvidenceDimension)[i % 5],
                           polarity=EvidencePolarity.POSITIVE,
                           description="test", source_modalities=["face"],
                           contribution=0.2)
        for i in range(8)
    ]
    graph = EvidenceGraph().add_many(evidence).build()

    def run():
        ctx = RuleContext(
            state=BehavioralState.STRESSED, graph=graph,
            elapsed_seconds=90.0, confidence=0.45, stress=0.70,
            communication=0.65, engagement=0.55, consistency=0.60,
            segment="technical_discussion",
        )
        evaluate_rules(ctx)

    return _summarize("context_rules_evaluation", _measure(run, iterations))


def _bench_calibration(iterations: int = 200) -> BenchmarkResult:
    from backend.models.evidence import ModalityQuality, PredictionReliability
    from backend.reasoning.calibration.confidence_engine import calibrate

    quality = ModalityQuality(
        face_available=True, face_quality=0.78,
        audio_available=True, audio_quality=0.72,
        nlp_available=True, nlp_quality=0.65,
        transcript_words=45, evidence_coverage=0.8,
    )
    scores = {"confidence": 0.72, "stress": 0.31, "communication": 0.68,
              "engagement": 0.61, "consistency": 0.74}

    def run():
        calibrate(
            scores=scores, reliability=PredictionReliability.HIGH,
            modality_quality=quality, conflict_score=0.1,
            cross_modal_agreement=0.85, evidence_count=11,
            rule_adjustments={}, elapsed_seconds=90.0,
        )

    return _summarize("confidence_calibration", _measure(run, iterations))


# ── Public API ────────────────────────────────────────────────────────────────

def run_quick_benchmark() -> Dict[str, Any]:
    """
    Run all reasoning benchmarks and return structured results.

    This runs in ~1-2 seconds and tests only pure Python logic —
    no ML model inference is invoked.
    """
    t_start = time.perf_counter()

    results = [
        _bench_evidence_graph(),
        _bench_temporal_analysis(),
        _bench_behavioral_state(),
        _bench_context_rules(),
        _bench_calibration(),
    ]

    total_ms = (time.perf_counter() - t_start) * 1000

    return {
        "benchmark_suite": "reasoning_pipeline",
        "total_duration_ms": round(total_ms, 1),
        "results": [r.to_dict() for r in results],
        "summary": {
            "fastest_p50_ms": round(min(r.p50_ms for r in results), 3),
            "slowest_p50_ms": round(max(r.p50_ms for r in results), 3),
            "combined_throughput": "see individual results",
        },
    }
