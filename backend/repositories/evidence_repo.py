"""
Evidence Repository — stores and retrieves decision traces and evidence pools.

Evidence data enables:
  - Post-session inspection of every reasoning decision
  - Offline debugging of score anomalies
  - Future retraining signal collection
  - Benchmark comparisons across model versions

Currently stored in-memory (ring buffer per session).
Future: persist to SQLite / PostgreSQL for long-term storage.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List

from backend.core.interfaces.storage import IEvidenceRepository

logger = logging.getLogger(__name__)


class InMemoryEvidenceRepository(IEvidenceRepository):
    """
    In-memory evidence trace store.

    Traces are kept per-session in a ring buffer. On session end,
    callers can extract and persist to long-term storage.
    """

    def __init__(self, max_traces_per_session: int = 200) -> None:
        self._traces: Dict[str, List[Dict]] = defaultdict(list)
        self._max   = max_traces_per_session

    def save_traces(self, session_id: str, traces: List[Dict]) -> None:
        buf = self._traces[session_id]
        buf.extend(traces)
        if len(buf) > self._max:
            self._traces[session_id] = buf[-self._max:]

    def get_traces(self, session_id: str) -> List[Dict]:
        return list(self._traces.get(session_id, []))

    def flush(self, session_id: str) -> List[Dict]:
        """Return all traces for a session and clear the buffer."""
        traces = self.get_traces(session_id)
        self._traces.pop(session_id, None)
        return traces

    def session_count(self) -> int:
        return len(self._traces)


evidence_repository = InMemoryEvidenceRepository()
