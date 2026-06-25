"""ATS adapter registry — @register, lookup, list_available()."""

from __future__ import annotations

import logging
from typing import Dict, List, Type

from backend.ats.base import ATSConnector

logger = logging.getLogger("neurosync.ats.registry")


class ATSRegistry:
    def __init__(self) -> None:
        self._adapters: Dict[str, ATSConnector] = {}

    def register(self, cls: Type[ATSConnector]) -> Type[ATSConnector]:
        key = cls.provider.value
        self._adapters[key] = cls()
        logger.info("ATS adapter registered: %s (%s)", key, cls.display_name)
        return cls

    def get(self, provider: str) -> ATSConnector:
        if provider not in self._adapters:
            raise KeyError(f"Unknown ATS provider: {provider}")
        return self._adapters[provider]

    def has(self, provider: str) -> bool:
        return provider in self._adapters

    def list_available(self) -> List[dict]:
        return [
            {
                "provider":     a.provider.value,
                "display_name": a.display_name,
                "capabilities": a.capabilities.to_dict(),
                "scopes":       list(a.oauth.scopes),
            }
            for a in self._adapters.values()
        ]


ats_registry = ATSRegistry()


def register(cls: Type[ATSConnector]) -> Type[ATSConnector]:
    return ats_registry.register(cls)
