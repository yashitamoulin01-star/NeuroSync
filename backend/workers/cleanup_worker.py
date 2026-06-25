"""
Cleanup Worker — background tasks for session maintenance.

These tasks run independently of request handling so they never
add latency to inference or WebSocket message processing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

_STALE_SESSION_AGE   = 3600   # 1 hour
_CLEANUP_INTERVAL    = 600    # run every 10 minutes
_RATE_LIMIT_INTERVAL = 120    # clean rate-limit records every 2 minutes


async def stale_session_cleanup_loop() -> None:
    """Evict sessions older than 1 hour from memory."""
    from backend.services.session_manager import session_manager
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL)
        try:
            session_manager.cleanup_stale(max_age_seconds=_STALE_SESSION_AGE)
        except Exception:
            logger.exception("Stale session cleanup error")


async def rate_limit_cleanup_loop(rate_records: dict, window: float = 60.0) -> None:
    """Periodically evict expired rate-limit records to prevent memory growth."""
    while True:
        await asyncio.sleep(_RATE_LIMIT_INTERVAL)
        try:
            now = time.time()
            expired = [ip for ip, ts_list in rate_records.items()
                       if not any(now - t < window for t in ts_list)]
            for ip in expired:
                del rate_records[ip]
            if expired:
                logger.debug("Rate-limit cleanup: removed %d expired records", len(expired))
        except Exception:
            logger.exception("Rate-limit cleanup error")


def create_cleanup_tasks() -> list:
    """Return background coroutines to be scheduled at startup."""
    return [
        stale_session_cleanup_loop(),
    ]
