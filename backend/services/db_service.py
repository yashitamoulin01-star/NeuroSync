"""
SQLite-backed persistence for session history.

Schema:
  sessions         — one row per session
  session_frames   — sampled analytics frames (every ~2s)
  session_insights — behavioral insights per session
"""

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.config import settings

logger = logging.getLogger(__name__)

_DB_PATH = Path(settings.DATASET_DIR) / "nuanceai.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL DEFAULT '',
    mode             TEXT NOT NULL DEFAULT 'interview',
    user_id          TEXT,
    started_at       REAL NOT NULL,
    ended_at         REAL,
    duration         REAL,
    avg_confidence   REAL,
    avg_stress       REAL,
    avg_engagement   REAL,
    avg_communication REAL,
    avg_consistency  REAL,
    avg_eye_contact  REAL,
    avg_speaking_pace REAL,
    total_filler_words INTEGER DEFAULT 0,
    total_words      INTEGER DEFAULT 0,
    transcript       TEXT DEFAULT '',
    insights_json    TEXT DEFAULT '[]',
    created_at       REAL NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS session_frames (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    ts          REAL NOT NULL,
    confidence  REAL,
    stress      REAL,
    engagement  REAL,
    communication REAL,
    consistency REAL,
    eye_contact REAL,
    is_speaking INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_frames_session ON session_frames(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at DESC);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(str(_DB_PATH), timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    with _conn() as con:
        con.executescript(_DDL)
    logger.info("DB initialised at %s", _DB_PATH)


def create_session_record(
    session_id: str,
    name: str,
    mode: str,
    user_id: Optional[str],
    started_at: float,
) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO sessions (id, name, mode, user_id, started_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, name, mode, user_id, started_at),
        )


def record_frame(
    session_id: str,
    ts: float,
    confidence: float,
    stress: float,
    engagement: float,
    communication: float,
    consistency: float,
    eye_contact: float,
    is_speaking: bool,
) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO session_frames
              (session_id, ts, confidence, stress, engagement, communication, consistency, eye_contact, is_speaking)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, ts, confidence, stress, engagement, communication,
             consistency, eye_contact, int(is_speaking)),
        )


def finalize_session(
    session_id: str,
    ended_at: float,
    duration: float,
    avg_confidence: float,
    avg_stress: float,
    avg_engagement: float,
    avg_communication: float,
    avg_consistency: float,
    avg_eye_contact: float,
    avg_speaking_pace: float,
    total_filler_words: int,
    total_words: int,
    transcript: str,
    insights: List[Dict],
) -> None:
    with _conn() as con:
        con.execute(
            """
            UPDATE sessions SET
                ended_at=?, duration=?,
                avg_confidence=?, avg_stress=?, avg_engagement=?,
                avg_communication=?, avg_consistency=?, avg_eye_contact=?,
                avg_speaking_pace=?, total_filler_words=?, total_words=?,
                transcript=?, insights_json=?
            WHERE id=?
            """,
            (
                ended_at, duration,
                avg_confidence, avg_stress, avg_engagement,
                avg_communication, avg_consistency, avg_eye_contact,
                avg_speaking_pace, total_filler_words, total_words,
                transcript, json.dumps(insights),
                session_id,
            ),
        )


def get_session(session_id: str) -> Optional[Dict]:
    with _conn() as con:
        row = con.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None


def list_sessions(
    limit: int = 50,
    offset: int = 0,
    mode: Optional[str] = None,
) -> List[Dict]:
    with _conn() as con:
        if mode:
            rows = con.execute(
                "SELECT * FROM sessions WHERE mode=? AND ended_at IS NOT NULL ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (mode, limit, offset),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM sessions WHERE ended_at IS NOT NULL ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]


def get_connection() -> sqlite3.Connection:
    """Return a raw connection for ad-hoc queries. Caller is responsible for closing."""
    con = sqlite3.connect(str(_DB_PATH), timeout=10)
    con.row_factory = sqlite3.Row
    return con


def delete_session(session_id: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM session_frames WHERE session_id=?", (session_id,))
        con.execute("DELETE FROM sessions WHERE id=?", (session_id,))


def get_session_frames(session_id: str) -> List[Dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT ts, confidence, stress, engagement, communication, consistency, eye_contact, is_speaking "
            "FROM session_frames WHERE session_id=? ORDER BY ts",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def dashboard_stats() -> Dict[str, Any]:
    with _conn() as con:
        total = con.execute(
            "SELECT COUNT(*) FROM sessions WHERE ended_at IS NOT NULL"
        ).fetchone()[0]

        avgs = con.execute(
            """
            SELECT
                AVG(avg_confidence)    as confidence,
                AVG(avg_stress)        as stress,
                AVG(avg_engagement)    as engagement,
                AVG(avg_communication) as communication,
                AVG(avg_consistency)   as consistency,
                AVG(duration)          as duration,
                SUM(total_filler_words) as filler_words
            FROM sessions WHERE ended_at IS NOT NULL
            """
        ).fetchone()

        by_mode = con.execute(
            "SELECT mode, COUNT(*) as cnt FROM sessions WHERE ended_at IS NOT NULL GROUP BY mode"
        ).fetchall()

        recent = con.execute(
            """
            SELECT id, name, mode, started_at, duration, avg_confidence, avg_stress,
                   avg_engagement, avg_communication, avg_consistency, total_filler_words
            FROM sessions WHERE ended_at IS NOT NULL
            ORDER BY started_at DESC LIMIT 5
            """
        ).fetchall()

        return {
            "total_sessions": total,
            "avg_confidence":    round(avgs["confidence"]    or 0, 4),
            "avg_stress":        round(avgs["stress"]        or 0, 4),
            "avg_engagement":    round(avgs["engagement"]    or 0, 4),
            "avg_communication": round(avgs["communication"] or 0, 4),
            "avg_consistency":   round(avgs["consistency"]   or 0, 4),
            "avg_duration":      round(avgs["duration"]      or 0, 1),
            "total_filler_words": int(avgs["filler_words"] or 0),
            "by_mode": {r["mode"]: r["cnt"] for r in by_mode},
            "recent_sessions": [dict(r) for r in recent],
        }
