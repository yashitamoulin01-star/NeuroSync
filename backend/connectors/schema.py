"""
Connector table DDL. Lives in the shared nuanceai.db (WAL), consistent with
every other enterprise table. Safe to call repeatedly (IF NOT EXISTS).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from backend.core.config import settings

logger = logging.getLogger("neurosync.connectors.schema")

_DB_PATH = Path(settings.DATASET_DIR) / "nuanceai.db"

_CONNECTOR_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS connectors (
    connector_id      TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL,
    org_id            TEXT,
    provider          TEXT NOT NULL,
    name              TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'disconnected',
    access_token_enc  TEXT,
    refresh_token_enc TEXT,
    token_expires_at  REAL,
    scopes_json       TEXT NOT NULL DEFAULT '[]',
    capabilities_json TEXT NOT NULL DEFAULT '{}',
    last_sync         REAL,
    last_error        TEXT,
    created_by        TEXT NOT NULL DEFAULT '',
    created_at        REAL NOT NULL DEFAULT (unixepoch()),
    updated_at        REAL NOT NULL DEFAULT (unixepoch()),
    UNIQUE(org_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_connectors_tenant ON connectors(tenant_id, status);
"""


def init_connectors_db() -> None:
    con = sqlite3.connect(str(_DB_PATH), timeout=10)
    try:
        con.executescript(_CONNECTOR_DDL)
        con.commit()
        logger.info("Connector schema initialised (%s)", _DB_PATH)
    except Exception as exc:
        logger.error("Connector DB init failed: %s", exc)
        raise
    finally:
        con.close()
