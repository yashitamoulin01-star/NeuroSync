"""
ConnectorRegistry — the pluggability mechanism.

Built-in and future connectors register themselves with @register at import
time. Lookup is by ConnectorProvider value, so the service/router/UI discover
new providers automatically.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Type

from backend.connectors.base import BaseConnector

logger = logging.getLogger("neurosync.connectors.registry")


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: Dict[str, BaseConnector] = {}

    def register(self, cls: Type[BaseConnector]) -> Type[BaseConnector]:
        """Class decorator: register a connector instance under its provider key."""
        key = cls.provider.value
        if key in self._connectors:
            logger.warning("Connector %s already registered — overwriting", key)
        self._connectors[key] = cls()
        logger.info("Connector registered: %s (%s)", key, cls.display_name)
        return cls

    def get(self, provider: str) -> BaseConnector:
        if provider not in self._connectors:
            raise KeyError(f"Unknown connector provider: {provider}")
        return self._connectors[provider]

    def has(self, provider: str) -> bool:
        return provider in self._connectors

    def list_available(self) -> List[dict]:
        """Catalog of every registered provider — drives the management UI."""
        return [
            {
                "provider":     c.provider.value,
                "display_name": c.display_name,
                "capabilities": c.capabilities.to_dict(),
                "scopes":       list(c.oauth.scopes),
            }
            for c in self._connectors.values()
        ]


registry = ConnectorRegistry()


def register(cls: Type[BaseConnector]) -> Type[BaseConnector]:
    """Module-level decorator shorthand: @register above a BaseConnector subclass."""
    return registry.register(cls)
