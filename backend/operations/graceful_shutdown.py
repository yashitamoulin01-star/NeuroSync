"""
Graceful shutdown handler.

Called from the lifespan context manager's teardown phase (after yield).
Ensures that when SIGTERM/SIGINT is received:

  1. Active sessions are finalized (within timeout)
  2. In-memory evidence buffers are flushed to the repository
  3. Background worker tasks are cancelled cleanly
  4. Pending metrics are flushed
  5. A final status log line is emitted for monitoring systems

This avoids orphaned sessions, lost evidence data, and resource leaks
on shutdown — critical for containerized deployments with rolling restarts.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List

logger = logging.getLogger("neurosync.shutdown")


async def _drain_sessions(timeout_s: float) -> int:
    """
    Best-effort graceful termination of all active interview sessions.
    Returns the number of sessions that were terminated.
    """
    try:
        from backend.services.session_manager import session_manager
        session_ids = list(session_manager._sessions.keys())
        if not session_ids:
            return 0
        logger.info("Draining %d active session(s) (timeout %.0fs)…", len(session_ids), timeout_s)
        deadline = time.time() + timeout_s
        drained  = 0
        for sid in session_ids:
            if time.time() > deadline:
                remaining = len(session_ids) - session_ids.index(sid)
                logger.warning("Drain timeout — %d session(s) not cleanly terminated", remaining)
                break
            try:
                session_manager.end_session(sid)
                drained += 1
            except Exception as exc:
                logger.debug("Could not drain session %s: %s", sid, exc)
        return drained
    except Exception as exc:
        logger.error("Session drain error: %s", exc)
        return 0


async def _flush_evidence() -> None:
    """Flush per-session in-memory evidence ring buffers."""
    try:
        from backend.repositories.evidence_repo import evidence_repository
        from backend.services.session_manager import session_manager
        for sid in list(session_manager._sessions.keys()):
            try:
                evidence_repository.flush(sid)
            except Exception:
                pass
        logger.debug("Evidence buffers flushed")
    except Exception as exc:
        logger.warning("Evidence flush skipped: %s", exc)


async def _cancel_workers(tasks: List[asyncio.Task]) -> None:
    """Cancel asyncio background tasks and await their termination."""
    active = [t for t in tasks if not t.done()]
    if not active:
        return
    for t in active:
        t.cancel()
    results = await asyncio.gather(*active, return_exceptions=True)
    cancelled = sum(1 for r in results if isinstance(r, asyncio.CancelledError))
    errors    = sum(1 for r in results if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError))
    logger.info("Workers cancelled: %d/%d (errors: %d)", cancelled, len(active), errors)


async def _flush_metrics() -> None:
    """Update system resource metrics one final time before shutdown."""
    try:
        import os, psutil
        from backend.monitoring.metrics import system_memory_used_bytes, system_cpu_percent
        proc = psutil.Process(os.getpid())
        system_memory_used_bytes.set(proc.memory_info().rss)
        system_cpu_percent.set(proc.cpu_percent(interval=None))
    except Exception:
        pass


async def run_graceful_shutdown(worker_tasks: List[asyncio.Task]) -> None:
    """
    Full graceful shutdown sequence.

    Call this from the lifespan context manager after yield:
        async with lifespan(app):
            yield
        await run_graceful_shutdown(cleanup_tasks)
    """
    logger.info("── Graceful shutdown initiated ───────────────────────────")
    t0 = time.time()

    # Order matters: drain sessions before flushing evidence (need session IDs)
    drained = await _drain_sessions(timeout_s=10.0)
    await _flush_evidence()
    await _flush_metrics()
    await _cancel_workers(worker_tasks)

    elapsed = time.time() - t0
    logger.info(
        "── Graceful shutdown complete — sessions_drained=%d elapsed=%.1fs ─",
        drained, elapsed,
    )
