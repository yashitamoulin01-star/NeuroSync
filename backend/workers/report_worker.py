"""
Report Worker — async report generation that doesn't block inference.

Heavy post-processing (report generation, analytics aggregation,
evidence persistence) runs here so the inference loop stays low-latency.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks

from backend.core.events.bus import event_bus
from backend.core.events.types import BackendEvent, EventType

logger = logging.getLogger(__name__)


async def generate_session_report(session_id: str, summary: Dict[str, Any]) -> None:
    """
    Post-process a completed session asynchronously.

    This runs after the WebSocket closes and the session is finalized,
    so it has no impact on interview latency.
    """
    try:
        start = time.perf_counter()

        # Persist evidence traces if evidence repo has data
        try:
            from backend.repositories.evidence_repo import evidence_repository
            traces = evidence_repository.flush(session_id)
            if traces:
                logger.info(
                    "Persisted %d decision traces for session %s",
                    len(traces), session_id,
                )
        except Exception:
            logger.warning("Evidence trace flush failed for %s", session_id, exc_info=True)

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "Report post-processing complete: session=%s duration=%.1fms",
            session_id, elapsed,
        )

        event_bus.publish(BackendEvent(
            type       = EventType.BENCHMARK_COMPLETED,
            session_id = session_id,
            payload    = {"report_generation_ms": round(elapsed, 2)},
        ))

    except Exception:
        logger.exception("Report generation failed for session %s", session_id)


def schedule_report(background_tasks: BackgroundTasks, session_id: str, summary: Dict) -> None:
    """Enqueue async report generation using FastAPI's background task system."""
    background_tasks.add_task(generate_session_report, session_id, summary)
