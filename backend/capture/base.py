"""
CaptureAdapter — the source contract.

A capture adapter acquires media from one source and pushes it into an
InputNormalizer. It owns nothing about behavioral analysis; its only job is
acquire → normalize → deliver (Volume 2B §Engineering Philosophy).

Adapters are async generators of normalized windows so the live dashboard and
the upload worker can drive them identically.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from backend.capture.models import CaptureCapabilities, CaptureSourceType
from backend.capture.normalizer import InputNormalizer


class CaptureAdapter(ABC):
    source_type:  ClassVar[CaptureSourceType]
    display_name: ClassVar[str]
    capabilities: ClassVar[CaptureCapabilities]

    def __init__(self, normalizer: InputNormalizer) -> None:
        self._normalizer = normalizer

    @abstractmethod
    async def start(self) -> None:
        """Begin acquisition. Push media via self._normalizer.ingest_*()."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop acquisition and release source resources."""

    def get_capabilities(self) -> CaptureCapabilities:
        return self.capabilities
