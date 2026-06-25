"""ATS connection + export-log DDL (shared nuanceai.db, WAL)."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from backend.core.config import settings

logger = logging.getLogger("neurosync.ats.schema")

_DB_PATH = Path(settings.DATASET_DIR) / "nuanceai.db"

_ATS_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS ats_connections (
    connection_id     TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL,
    org_id            TEXT,
    provider          TEXT NOT NULL,
    name              TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'disconnected',
    access_token_enc  TEXT,
    refresh_token_enc TEXT,
    token_expires_at  REAL,
    capabilities_json TEXT NOT NULL DEFAULT '{}',
    last_sync         REAL,
    last_error        TEXT,
    created_by        TEXT NOT NULL DEFAULT '',
    created_at        REAL NOT NULL DEFAULT (unixepoch()),
    updated_at        REAL NOT NULL DEFAULT (unixepoch()),
    UNIQUE(org_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_ats_tenant ON ats_connections(tenant_id, status);

CREATE TABLE IF NOT EXISTS ats_exports (
    export_id     TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL,
    tenant_id     TEXT NOT NULL,
    session_id    TEXT NOT NULL,
    provider      TEXT NOT NULL,
    external_ref  TEXT,
    ok            INTEGER NOT NULL DEFAULT 0,
    message       TEXT,
    created_at    REAL NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_ats_exports ON ats_exports(tenant_id, created_at DESC);
"""


def init_ats_db() -> None:
    con = sqlite3.connect(str(_DB_PATH), timeout=10)
    try:
        con.executescript(_ATS_DDL)
        con.commit()
        logger.info("ATS schema initialised (%s)", _DB_PATH)
    except Exception as exc:
        logger.error("ATS DB init failed: %s", exc)
        raise
    finally:
        con.close()
