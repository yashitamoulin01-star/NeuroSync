"""
In-process event bus — decoupled pub/sub for backend components.

This is NOT Kafka. It is a synchronous in-process dispatcher.
Components publish events without knowing who handles them.
Handlers register for the events they care about.

Why this matters:
  Modular monolith → the same code could be split into microservices
  by replacing this bus with a real message broker (Redis Streams, Kafka)
  without touching business logic.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from backend.core.events.types import BackendEvent, EventType

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[EventType, List[Callable[[BackendEvent], None]]] = defaultdict(list)
        self._async_handlers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._published: int = 0
        self._errors: int = 0

    # ── Subscription ──────────────────────────────────────────────────────────

    def subscribe(self, event_type: EventType, handler: Callable[[BackendEvent], None]) -> None:
        """Register a synchronous handler for an event type."""
        self._handlers[event_type].append(handler)

    def subscribe_async(self, event_type: EventType, handler: Callable) -> None:
        """Register an async handler for an event type."""
        self._async_handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        self._handlers[event_type] = [h for h in self._handlers[event_type] if h is not handler]

    # ── Publishing ────────────────────────────────────────────────────────────

    def publish(self, event: BackendEvent) -> None:
        """Publish an event synchronously. Handlers run in registration order."""
        self._published += 1
        for handler in self._handlers.get(event.type, []):
            try:
                handler(event)
            except Exception:
                self._errors += 1
                logger.exception(
                    "Event handler error: type=%s handler=%s session=%s",
                    event.type, handler.__name__, event.session_id,
                )

    async def publish_async(self, event: BackendEvent) -> None:
        """Publish an event, running sync handlers + awaiting async handlers."""
        self.publish(event)
        for handler in self._async_handlers.get(event.type, []):
            try:
                await handler(event)
            except Exception:
                self._errors += 1
                logger.exception(
                    "Async event handler error: type=%s session=%s",
                    event.type, event.session_id,
                )

    # ── Observability ─────────────────────────────────────────────────────────

    @property
    def published_count(self) -> int:
        return self._published

    @property
    def error_count(self) -> int:
        return self._errors

    def subscriber_counts(self) -> Dict[str, int]:
        return {
            et.value: len(handlers) + len(self._async_handlers.get(et, []))
            for et, handlers in self._handlers.items()
        }

    def stats(self) -> Dict:
        return {
            "published": self._published,
            "errors":    self._errors,
            "subscribers": self.subscriber_counts(),
        }


# Singleton — the application's single event bus
event_bus = EventBus()
