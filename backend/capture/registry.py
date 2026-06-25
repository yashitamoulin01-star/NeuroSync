"""
Capture source registry — discovery for the Universal Meeting Launcher.

Lists every capture source the deployment knows about, with capabilities and a
runtime `available` flag. The launcher renders this directly so new sources
appear without frontend changes.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from backend.capture.models import CaptureSourceInfo, CaptureSourceType

logger = logging.getLogger("neurosync.capture.registry")


class CaptureRegistry:
    def __init__(self) -> None:
        self._sources: Dict[str, CaptureSourceInfo] = {}

    def register(self, info: CaptureSourceInfo) -> None:
        self._sources[info.source_type.value] = info
        logger.debug("Capture source registered: %s (available=%s)", info.source_type.value, info.available)

    def get(self, source_type: str) -> CaptureSourceInfo:
        return self._sources[source_type]

    def has(self, source_type: str) -> bool:
        return source_type in self._sources

    def list_sources(self) -> List[dict]:
        # Available sources first, then by display name.
        items = sorted(self._sources.values(), key=lambda s: (not s.available, s.display_name))
        return [s.to_dict() for s in items]


capture_registry = CaptureRegistry()
