"""
Backup and recovery utilities.

Supports:
  - SQLite hot-backup (sqlite3 backup API — safe during WAL mode operation)
  - Configuration snapshot to JSON (secrets excluded)
  - AI lifecycle registry state export
  - Listing and rotating existing backups

Backups are written to {DATASET_DIR}/backups/ with ISO-8601 timestamps.
All operations are atomic: destination is written atomically (tmp → rename).

Usage:
    from backend.operations.backup import run_full_backup
    result = run_full_backup()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger("neurosync.backup")


def _backup_dir() -> Path:
    from backend.core.config import settings
    d = Path(settings.DATASET_DIR) / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ts() -> str:
    return time.strftime("%Y%m%dT%H%M%S")


# ── Database backup ───────────────────────────────────────────────────────────

def backup_database() -> str:
    """
    Online hot-backup of the SQLite database using the built-in backup API.
    Safe to call while the database is actively being written (WAL mode).
    Returns the path of the backup file.
    """
    from backend.core.config import settings
    db_path = Path(settings.DATASET_DIR) / "nuanceai.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    dest = _backup_dir() / f"sessions_{_ts()}.db"
    tmp  = dest.with_suffix(".db.tmp")
    try:
        src  = sqlite3.connect(str(db_path))
        bkup = sqlite3.connect(str(tmp))
        src.backup(bkup)
        bkup.close()
        src.close()
        tmp.rename(dest)
        logger.info("Database backup → %s", dest)
        return str(dest)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        logger.error("Database backup failed: %s", exc)
        raise


# ── Configuration snapshot ────────────────────────────────────────────────────

def backup_config() -> str:
    """
    Write a JSON snapshot of non-secret configuration settings.
    Returns the path of the snapshot file.
    """
    from backend.core.config import settings

    safe = {
        "APP_NAME":                   settings.APP_NAME,
        "APP_VERSION":                settings.APP_VERSION,
        "DEBUG":                      settings.DEBUG,
        "WHISPER_MODEL":              settings.WHISPER_MODEL,
        "WHISPER_DEVICE":             settings.WHISPER_DEVICE,
        "WINDOW_SIZE_SECONDS":        settings.WINDOW_SIZE_SECONDS,
        "ANALYTICS_FPS":              settings.ANALYTICS_FPS,
        "DATASET_DIR":                settings.DATASET_DIR,
        "DATASET_AUTO_SAVE":          settings.DATASET_AUTO_SAVE,
        "FACE_DETECTION_CONFIDENCE":  settings.FACE_DETECTION_CONFIDENCE,
        "FACE_TRACKING_CONFIDENCE":   settings.FACE_TRACKING_CONFIDENCE,
        "AUDIO_SAMPLE_RATE":          settings.AUDIO_SAMPLE_RATE,
        "AUDIO_CHUNK_DURATION":       settings.AUDIO_CHUNK_DURATION,
        "ALLOWED_ORIGINS":            settings.ALLOWED_ORIGINS,
        "snapshot_timestamp":         _ts(),
    }
    dest = _backup_dir() / f"config_{_ts()}.json"
    dest.write_text(json.dumps(safe, indent=2))
    logger.info("Config snapshot → %s", dest)
    return str(dest)


# ── Model registry export ─────────────────────────────────────────────────────

def backup_model_registry() -> str:
    """Export the AI lifecycle registry to JSON."""
    from backend.ai.registry.lifecycle import lifecycle_registry
    dest = _backup_dir() / f"model_registry_{_ts()}.json"
    data = lifecycle_registry.summary()
    data["snapshot_timestamp"] = _ts()
    dest.write_text(json.dumps(data, indent=2, default=str))
    logger.info("Model registry backup → %s", dest)
    return str(dest)


# ── Bulk backup ───────────────────────────────────────────────────────────────

def run_full_backup() -> Dict[str, str]:
    """
    Run all backup operations atomically.
    Returns a mapping of backup_type → file_path (or error message).
    """
    results: Dict[str, str] = {}
    for name, fn in [
        ("database",       backup_database),
        ("config",         backup_config),
        ("model_registry", backup_model_registry),
    ]:
        try:
            results[name] = fn()
        except Exception as exc:
            logger.error("Backup '%s' failed: %s", name, exc)
            results[name] = f"ERROR: {exc}"
    return results


# ── Listing + rotation ────────────────────────────────────────────────────────

def list_backups() -> Dict:
    d = _backup_dir()
    files = sorted(d.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "backup_dir": str(d),
        "count":      len(files),
        "files": [
            {
                "name":        f.name,
                "size_kb":     round(f.stat().st_size / 1024, 1),
                "modified_at": time.ctime(f.stat().st_mtime),
            }
            for f in files[:50]
        ],
    }


def rotate_backups(keep: int = 10) -> int:
    """
    Delete oldest backups keeping at most `keep` files of each type.
    Returns the number of files deleted.
    """
    d    = _backup_dir()
    deleted = 0
    for prefix in ("sessions_", "config_", "model_registry_"):
        files = sorted(
            [f for f in d.glob(f"{prefix}*")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in files[keep:]:
            try:
                old.unlink()
                deleted += 1
                logger.info("Rotated backup: %s", old.name)
            except Exception as exc:
                logger.warning("Could not delete backup %s: %s", old.name, exc)
    return deleted
