"""
SQLite persistence for behavioral profiles.

Two tables are appended to the existing nuanceai.db:
  behavioral_profiles  — one row per candidate, profile stored as JSON blob
  behavioral_history   — one row per interview, lightweight metrics snapshot
"""

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.config import settings
from backend.behavioral_memory.models import CandidateProfile, InterviewHistoryEntry

logger = logging.getLogger(__name__)

_DB_PATH = Path(settings.DATASET_DIR) / "nuanceai.db"

_DDL = """
CREATE TABLE IF NOT EXISTS behavioral_profiles (
    candidate_id    TEXT PRIMARY KEY,
    profile_json    TEXT NOT NULL DEFAULT '{}',
    total_interviews INTEGER DEFAULT 0,
    first_seen_at   REAL NOT NULL,
    updated_at      REAL NOT NULL,
    learning_paused INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS behavioral_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id     TEXT NOT NULL,
    session_id       TEXT NOT NULL,
    conducted_at     REAL NOT NULL,
    duration         REAL DEFAULT 0,
    overall_score    REAL DEFAULT 0,
    avg_confidence   REAL DEFAULT 0,
    avg_stress       REAL DEFAULT 0,
    avg_engagement   REAL DEFAULT 0,
    avg_communication REAL DEFAULT 0,
    avg_consistency  REAL DEFAULT 0,
    recommendation   TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_bh_candidate ON behavioral_history(candidate_id);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(str(_DB_PATH), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_behavioral_db() -> None:
    with _conn() as con:
        con.executescript(_DDL)
    logger.info("Behavioral memory DB schema ready")


# ── Profile CRUD ──────────────────────────────────────────────────────────────

def get_profile(candidate_id: str) -> Optional[CandidateProfile]:
    with _conn() as con:
        row = con.execute(
            "SELECT profile_json, learning_paused FROM behavioral_profiles WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["profile_json"])
        profile = CandidateProfile(**data)
        profile.learning_paused = bool(row["learning_paused"])
        return profile
    except Exception as exc:
        logger.warning("Corrupt profile for %s: %s", candidate_id, exc)
        return None


def upsert_profile(profile: CandidateProfile) -> None:
    now = time.time()
    profile.updated_at = now
    with _conn() as con:
        con.execute("""
            INSERT INTO behavioral_profiles
                (candidate_id, profile_json, total_interviews, first_seen_at, updated_at, learning_paused)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                profile_json     = excluded.profile_json,
                total_interviews = excluded.total_interviews,
                updated_at       = excluded.updated_at,
                learning_paused  = excluded.learning_paused
        """, (
            profile.candidate_id,
            profile.model_dump_json(),
            profile.total_interviews,
            profile.first_seen_at,
            now,
            int(profile.learning_paused),
        ))


def delete_profile(candidate_id: str) -> bool:
    with _conn() as con:
        cur = con.execute(
            "DELETE FROM behavioral_profiles WHERE candidate_id = ?", (candidate_id,)
        )
        con.execute(
            "DELETE FROM behavioral_history WHERE candidate_id = ?", (candidate_id,)
        )
    return cur.rowcount > 0


def set_learning_paused(candidate_id: str, paused: bool) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE behavioral_profiles SET learning_paused = ? WHERE candidate_id = ?",
            (int(paused), candidate_id),
        )


# ── History CRUD ──────────────────────────────────────────────────────────────

def append_history(candidate_id: str, entry: InterviewHistoryEntry) -> None:
    with _conn() as con:
        con.execute("""
            INSERT OR IGNORE INTO behavioral_history
                (candidate_id, session_id, conducted_at, duration, overall_score,
                 avg_confidence, avg_stress, avg_engagement, avg_communication,
                 avg_consistency, recommendation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            candidate_id,
            entry.session_id,
            entry.conducted_at,
            entry.duration,
            entry.overall_score,
            entry.avg_confidence,
            entry.avg_stress,
            entry.avg_engagement,
            entry.avg_communication,
            entry.avg_consistency,
            entry.recommendation,
        ))


def list_history(candidate_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with _conn() as con:
        rows = con.execute("""
            SELECT session_id, conducted_at, duration, overall_score,
                   avg_confidence, avg_stress, avg_engagement,
                   avg_communication, avg_consistency, recommendation
            FROM behavioral_history
            WHERE candidate_id = ?
            ORDER BY conducted_at DESC
            LIMIT ?
        """, (candidate_id, limit)).fetchall()
    return [dict(r) for r in rows]
