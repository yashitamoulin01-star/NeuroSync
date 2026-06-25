"""
CBIP — SQLite persistence layer.

All CBIP tables live in the same nuanceai.db as behavioral_memory,
keeping the persistence footprint minimal and the schema consistent.
"""

from __future__ import annotations
import json
import logging
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.config import settings
from backend.behavioral_knowledge.models import (
    ValidationEvent, PatternObservation, BehavioralPattern,
    CoachingRecord, OrgProfile, SEED_PATTERNS, VALIDATION_CONFIDENCE,
    ValidationLevel,
)

logger = logging.getLogger(__name__)

_DB_PATH = Path(settings.DATASET_DIR) / "nuanceai.db"

_DDL = """
CREATE TABLE IF NOT EXISTS cbip_validation_events (
    event_id     TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    candidate_id TEXT,
    org_id       TEXT,
    level        TEXT NOT NULL,
    signal       TEXT NOT NULL,
    confidence   REAL NOT NULL,
    metadata_json TEXT DEFAULT '{}',
    recorded_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cve_session   ON cbip_validation_events(session_id);
CREATE INDEX IF NOT EXISTS idx_cve_level     ON cbip_validation_events(level);
CREATE INDEX IF NOT EXISTS idx_cve_org       ON cbip_validation_events(org_id);

CREATE TABLE IF NOT EXISTS cbip_pattern_observations (
    obs_id                TEXT PRIMARY KEY,
    session_id            TEXT NOT NULL,
    candidate_id          TEXT,
    org_id                TEXT,
    avg_confidence        REAL DEFAULT 0,
    avg_engagement        REAL DEFAULT 0,
    avg_communication     REAL DEFAULT 0,
    avg_stress            REAL DEFAULT 0,
    avg_consistency       REAL DEFAULT 0,
    overall_score         REAL DEFAULT 0,
    validation_confidence REAL DEFAULT 0.20,
    recorded_at           REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cpo_session ON cbip_pattern_observations(session_id);

CREATE TABLE IF NOT EXISTS cbip_patterns (
    pattern_id        TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    description       TEXT NOT NULL,
    dimensions_json   TEXT NOT NULL,
    threshold         REAL NOT NULL,
    observation_count INTEGER DEFAULT 0,
    validated_count   INTEGER DEFAULT 0,
    confidence        REAL DEFAULT 0,
    first_seen_at     REAL NOT NULL,
    updated_at        REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS cbip_coaching_records (
    record_id            TEXT PRIMARY KEY,
    candidate_id         TEXT NOT NULL,
    session_id           TEXT NOT NULL,
    dimension            TEXT NOT NULL,
    coaching_text        TEXT NOT NULL,
    delivered_at         REAL NOT NULL,
    follow_up_session_id TEXT,
    improvement_delta    REAL,
    outcome              TEXT
);
CREATE INDEX IF NOT EXISTS idx_ccr_candidate ON cbip_coaching_records(candidate_id);
CREATE INDEX IF NOT EXISTS idx_ccr_dimension ON cbip_coaching_records(dimension);

CREATE TABLE IF NOT EXISTS cbip_org_signals (
    signal_id        TEXT PRIMARY KEY,
    org_id           TEXT NOT NULL,
    session_id       TEXT NOT NULL,
    metrics_json     TEXT NOT NULL,
    recommendation   TEXT NOT NULL,
    validation_level TEXT NOT NULL,
    recorded_at      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cos_org ON cbip_org_signals(org_id);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(str(_DB_PATH), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_cbip_db() -> None:
    with _conn() as con:
        con.executescript(_DDL)
    _seed_patterns()
    logger.info("CBIP knowledge DB schema ready")


def _seed_patterns() -> None:
    with _conn() as con:
        for p in SEED_PATTERNS:
            now = time.time()
            con.execute("""
                INSERT OR IGNORE INTO cbip_patterns
                    (pattern_id, name, description, dimensions_json, threshold,
                     observation_count, validated_count, confidence, first_seen_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?, ?)
            """, (
                p["pattern_id"], p["name"], p["description"],
                json.dumps(p["dimensions"]), p["threshold"], now, now,
            ))


# ── Validation events ─────────────────────────────────────────────────────────

def insert_validation_event(event: ValidationEvent) -> None:
    with _conn() as con:
        con.execute("""
            INSERT OR IGNORE INTO cbip_validation_events
                (event_id, session_id, candidate_id, org_id, level, signal,
                 confidence, metadata_json, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_id, event.session_id, event.candidate_id, event.org_id,
            event.level, event.signal, event.confidence,
            json.dumps(event.metadata), event.recorded_at,
        ))


def list_validation_events(
    level: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    clauses, params = [], []
    if level:
        clauses.append("level = ?"); params.append(level)
    if session_id:
        clauses.append("session_id = ?"); params.append(session_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"SELECT * FROM cbip_validation_events {where} ORDER BY recorded_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [dict(r) for r in rows]


def count_validation_events_by_level() -> Dict[str, int]:
    with _conn() as con:
        rows = con.execute(
            "SELECT level, COUNT(*) as cnt FROM cbip_validation_events GROUP BY level"
        ).fetchall()
    return {r["level"]: r["cnt"] for r in rows}


def get_session_validation_confidence(session_id: str) -> float:
    """Return the highest validation confidence recorded for a session."""
    with _conn() as con:
        row = con.execute(
            "SELECT MAX(confidence) as mc FROM cbip_validation_events WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return float(row["mc"] or 0.20)


# ── Pattern observations ──────────────────────────────────────────────────────

def insert_pattern_observation(obs: PatternObservation) -> None:
    with _conn() as con:
        con.execute("""
            INSERT OR IGNORE INTO cbip_pattern_observations
                (obs_id, session_id, candidate_id, org_id,
                 avg_confidence, avg_engagement, avg_communication,
                 avg_stress, avg_consistency, overall_score,
                 validation_confidence, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            obs.obs_id, obs.session_id, obs.candidate_id, obs.org_id,
            obs.avg_confidence, obs.avg_engagement, obs.avg_communication,
            obs.avg_stress, obs.avg_consistency, obs.overall_score,
            obs.validation_confidence, obs.recorded_at,
        ))


def count_total_observations() -> int:
    with _conn() as con:
        row = con.execute("SELECT COUNT(*) as n FROM cbip_pattern_observations").fetchone()
    return int(row["n"] or 0)


def get_all_observations(limit: int = 5000) -> List[Dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM cbip_pattern_observations ORDER BY recorded_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Patterns ──────────────────────────────────────────────────────────────────

def get_all_patterns() -> List[BehavioralPattern]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM cbip_patterns ORDER BY confidence DESC, observation_count DESC"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["dimensions"] = json.loads(d.pop("dimensions_json", "[]"))
        out.append(BehavioralPattern(**d))
    return out


def update_pattern_stats(
    pattern_id: str, observation_count: int, validated_count: int, confidence: float
) -> None:
    with _conn() as con:
        con.execute("""
            UPDATE cbip_patterns
               SET observation_count = ?,
                   validated_count   = ?,
                   confidence        = ?,
                   updated_at        = ?
             WHERE pattern_id = ?
        """, (observation_count, validated_count, confidence, time.time(), pattern_id))


# ── Coaching records ──────────────────────────────────────────────────────────

def insert_coaching_record(rec: CoachingRecord) -> None:
    with _conn() as con:
        con.execute("""
            INSERT OR IGNORE INTO cbip_coaching_records
                (record_id, candidate_id, session_id, dimension,
                 coaching_text, delivered_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            rec.record_id, rec.candidate_id, rec.session_id,
            rec.dimension, rec.coaching_text, rec.delivered_at,
        ))


def update_coaching_outcome(
    candidate_id: str, dimension: str, follow_up_session_id: str,
    improvement_delta: float, outcome: str,
) -> None:
    with _conn() as con:
        con.execute("""
            UPDATE cbip_coaching_records
               SET follow_up_session_id = ?,
                   improvement_delta    = ?,
                   outcome              = ?
             WHERE candidate_id = ?
               AND dimension    = ?
               AND outcome IS NULL
             ORDER BY delivered_at DESC
             LIMIT 1
        """, (follow_up_session_id, improvement_delta, outcome, candidate_id, dimension))


def get_coaching_effectiveness() -> Dict[str, Dict[str, Any]]:
    """Return effectiveness stats per dimension: delivered, improved, rate."""
    with _conn() as con:
        rows = con.execute("""
            SELECT dimension,
                   COUNT(*) as delivered,
                   SUM(CASE WHEN outcome = 'improved' THEN 1 ELSE 0 END) as improved
            FROM cbip_coaching_records
            WHERE outcome IS NOT NULL
            GROUP BY dimension
        """).fetchall()
    result = {}
    for r in rows:
        delivered = r["delivered"] or 0
        improved  = r["improved"]  or 0
        result[r["dimension"]] = {
            "delivered": delivered,
            "improved":  improved,
            "rate":      round(improved / delivered, 3) if delivered > 0 else None,
        }
    return result


def get_coaching_records_for_candidate(candidate_id: str) -> List[Dict[str, Any]]:
    with _conn() as con:
        rows = con.execute("""
            SELECT * FROM cbip_coaching_records
            WHERE candidate_id = ?
            ORDER BY delivered_at DESC
        """, (candidate_id,)).fetchall()
    return [dict(r) for r in rows]


def count_coaching_records() -> int:
    with _conn() as con:
        row = con.execute("SELECT COUNT(*) as n FROM cbip_coaching_records").fetchone()
    return int(row["n"] or 0)


# ── Org signals ───────────────────────────────────────────────────────────────

def insert_org_signal(
    org_id: str, session_id: str, metrics: Dict[str, float],
    recommendation: str, validation_level: str,
) -> None:
    with _conn() as con:
        con.execute("""
            INSERT OR IGNORE INTO cbip_org_signals
                (signal_id, org_id, session_id, metrics_json,
                 recommendation, validation_level, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), org_id, session_id,
            json.dumps(metrics), recommendation, validation_level, time.time(),
        ))


def get_org_signals(org_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    with _conn() as con:
        rows = con.execute("""
            SELECT * FROM cbip_org_signals WHERE org_id = ?
            ORDER BY recorded_at DESC LIMIT ?
        """, (org_id, limit)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["metrics"] = json.loads(d.pop("metrics_json", "{}"))
        result.append(d)
    return result


def count_orgs() -> int:
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(DISTINCT org_id) as n FROM cbip_org_signals"
        ).fetchone()
    return int(row["n"] or 0)
