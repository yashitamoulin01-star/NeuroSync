"""
Benchmark History — persistent storage for P50/P95/P99 over time.

Stores every benchmark run so trend analysis is possible:
  - Is latency creeping up over time?
  - Did the last model update regress throughput?
  - What's the rolling P99 over the last 30 benchmark runs?

Each entry records the git hash and model versions so regressions
are traceable to a specific commit.
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from backend.core.config import settings

logger = logging.getLogger(__name__)

_HISTORY_PATH = Path(settings.DATASET_DIR) / "benchmark_history.jsonl"
_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
_MAX_IN_MEMORY = 500


@dataclass
class BenchmarkEntry:
    """One complete benchmark suite run."""
    run_id:        str
    timestamp:     float
    suite:         str
    model_versions: Dict[str, str]        # model_name → version
    pipeline_version: str
    git_hash:      Optional[str]
    results:       List[Dict]             # from BenchmarkResult.to_dict()
    total_ms:      float
    summary:       Dict

    def to_dict(self) -> Dict:
        return {
            "run_id":          self.run_id,
            "timestamp":       self.timestamp,
            "suite":           self.suite,
            "model_versions":  self.model_versions,
            "pipeline_version": self.pipeline_version,
            "git_hash":        self.git_hash,
            "results":         self.results,
            "total_ms":        self.total_ms,
            "summary":         self.summary,
        }


class BenchmarkHistory:
    """
    Write-append benchmark history backed by JSONL.

    JSONL is append-only, human-readable, and trivially importable into
    Pandas or any analytics tool for trend analysis.
    """

    def __init__(self) -> None:
        self._cache: deque = deque(maxlen=_MAX_IN_MEMORY)
        self._load_recent()

    def _load_recent(self) -> None:
        if not _HISTORY_PATH.exists():
            return
        try:
            lines = _HISTORY_PATH.read_text(encoding="utf-8").strip().splitlines()
            for line in lines[-_MAX_IN_MEMORY:]:
                entry = json.loads(line)
                self._cache.append(entry)
        except Exception as e:
            logger.warning("Could not load benchmark history: %s", e)

    def record(
        self,
        results:          List[Dict],
        total_ms:         float,
        suite:            str = "reasoning_pipeline",
        pipeline_version: str = "3.0.0",
        git_hash:         Optional[str] = None,
    ) -> BenchmarkEntry:
        import uuid
        from backend.core.registry.model_registry import model_registry

        model_versions = {
            m.name: m.version for m in model_registry.all()
        }

        fastest = min((r["p50_ms"] for r in results), default=0.0)
        slowest = max((r["p50_ms"] for r in results), default=0.0)

        entry = BenchmarkEntry(
            run_id           = str(uuid.uuid4())[:12],
            timestamp        = time.time(),
            suite            = suite,
            model_versions   = model_versions,
            pipeline_version = pipeline_version,
            git_hash         = git_hash,
            results          = results,
            total_ms         = round(total_ms, 2),
            summary          = {
                "fastest_p50_ms": round(fastest, 3),
                "slowest_p50_ms": round(slowest, 3),
            },
        )

        d = entry.to_dict()
        self._cache.append(d)

        try:
            with _HISTORY_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(d) + "\n")
        except Exception as e:
            logger.warning("Benchmark history write failed: %s", e)

        return entry

    def get_recent(self, n: int = 20) -> List[Dict]:
        return list(self._cache)[-n:]

    def trend(self, component: str, n: int = 20) -> Dict:
        """Return P50 trend for a named benchmark component across last N runs."""
        entries = self.get_recent(n)
        timestamps = []
        p50_values = []
        for entry in entries:
            for result in entry.get("results", []):
                if result.get("name") == component:
                    timestamps.append(entry["timestamp"])
                    p50_values.append(result.get("p50_ms"))
                    break

        if len(p50_values) < 2:
            return {"component": component, "trend": "insufficient_data", "values": p50_values}

        # Linear trend direction
        first_half = p50_values[:len(p50_values)//2]
        second_half = p50_values[len(p50_values)//2:]
        avg_first  = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = avg_second - avg_first
        trend = "stable"
        if delta > 0.5:
            trend = "degrading"
        elif delta < -0.5:
            trend = "improving"

        return {
            "component":   component,
            "trend":       trend,
            "avg_first_half_ms":  round(avg_first, 3),
            "avg_second_half_ms": round(avg_second, 3),
            "delta_ms":    round(delta, 3),
            "samples":     len(p50_values),
            "values":      [round(v, 3) for v in p50_values],
        }

    def stats(self) -> Dict:
        return {
            "total_runs_in_memory": len(self._cache),
            "history_file": str(_HISTORY_PATH),
            "file_exists":  _HISTORY_PATH.exists(),
        }


benchmark_history = BenchmarkHistory()
