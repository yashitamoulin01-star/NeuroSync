"""
Dataset validation service.
Checks session completeness and returns per-session health status.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from backend.core.config import settings

logger = logging.getLogger(__name__)

BASE = Path(settings.DATASET_DIR)

# Health levels
HEALTH_READY = "ready"      # all critical files present, labeled
HEALTH_PARTIAL = "partial"  # some files missing or unlabeled
HEALTH_MISSING = "missing"  # critical files absent


class SessionHealth:
    __slots__ = ("session_id", "health", "checks", "label_status", "duration", "name")

    def __init__(
        self,
        session_id: str,
        health: str,
        checks: dict[str, bool],
        label_status: str,
        duration: float,
        name: str,
    ) -> None:
        self.session_id = session_id
        self.health = health
        self.checks = checks
        self.label_status = label_status
        self.duration = duration
        self.name = name

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "health": self.health,
            "checks": self.checks,
            "label_status": self.label_status,
            "duration": self.duration,
            "name": self.name,
        }


class ValidationService:
    def validate_session(self, session_id: str) -> SessionHealth:
        proc_dir = BASE / "processed" / "sessions" / session_id
        labeled_dir = BASE / "labeled" / "sessions" / session_id
        emb_dir = BASE / "embeddings" / "sessions" / session_id
        raw_dir = BASE / "raw" / "sessions" / session_id

        checks: dict[str, bool] = {
            "metadata": (proc_dir / "metadata.json").exists(),
            "timeline": self._jsonl_non_empty(proc_dir / "fused_timeline.jsonl"),
            "face_metrics": self._jsonl_non_empty(proc_dir / "face_metrics.jsonl"),
            "audio_metrics": self._jsonl_non_empty(proc_dir / "audio_metrics.jsonl"),
            "transcript": (proc_dir / "transcript.txt").exists(),
            "timestamps": (proc_dir / "timestamps.json").exists(),
            "label": (labeled_dir / "labels.json").exists(),
            "face_embedding": (emb_dir / "face.npy").exists(),
            "audio_embedding": (emb_dir / "audio.npy").exists(),
            "text_embedding": (emb_dir / "text.npy").exists(),
            "video": (raw_dir / "video.mp4").exists(),
        }

        label_status = "unlabeled"
        duration = 0.0
        name = session_id[:8]

        if checks["metadata"]:
            try:
                with open(proc_dir / "metadata.json", encoding="utf-8") as f:
                    meta = json.load(f)
                label_status = meta.get("label_status", "unlabeled")
                duration = meta.get("duration", 0.0)
                name = meta.get("config", {}).get("session_name", session_id[:8])
            except Exception:
                pass

        # Critical checks: metadata + timeline + at least one modality
        critical_ok = checks["metadata"] and checks["timeline"] and (
            checks["face_metrics"] or checks["audio_metrics"]
        )

        if not critical_ok:
            health = HEALTH_MISSING
        elif label_status == "labeled" and all([
            checks["face_embedding"], checks["audio_embedding"], checks["text_embedding"]
        ]):
            health = HEALTH_READY
        else:
            health = HEALTH_PARTIAL

        return SessionHealth(
            session_id=session_id,
            health=health,
            checks=checks,
            label_status=label_status,
            duration=duration,
            name=name,
        )

    def validate_all(self, limit: int = 200, offset: int = 0) -> list[dict]:
        """Return paginated health checks (default 200 per page, no sorting for speed)."""
        sessions_dir = BASE / "processed" / "sessions"
        if not sessions_dir.exists():
            return []
        results = []
        seen = 0
        for d in sessions_dir.iterdir():
            if not d.is_dir():
                continue
            if seen < offset:
                seen += 1
                continue
            results.append(self.validate_session(d.name).to_dict())
            seen += 1
            if len(results) >= limit:
                break
        return results

    def summary(self) -> dict:
        """Fast summary by counting files in labeled/ and embeddings/ directories."""
        proc_dir    = BASE / "processed" / "sessions"
        labeled_dir = BASE / "labeled"   / "sessions"
        emb_dir     = BASE / "embeddings" / "sessions"

        total    = sum(1 for d in proc_dir.iterdir()    if d.is_dir()) if proc_dir.exists()    else 0
        labeled  = sum(1 for d in labeled_dir.iterdir() if d.is_dir()) if labeled_dir.exists() else 0
        embedded = sum(
            1 for d in emb_dir.iterdir()
            if d.is_dir() and (d / "text.npy").exists()
        ) if emb_dir.exists() else 0

        # Sample first 100 to estimate ready/partial/missing ratios
        sample = self.validate_all(limit=100)
        n_sample = len(sample)
        if n_sample:
            ratio_ready   = sum(1 for s in sample if s["health"] == HEALTH_READY)   / n_sample
            ratio_partial = sum(1 for s in sample if s["health"] == HEALTH_PARTIAL) / n_sample
            ratio_missing = sum(1 for s in sample if s["health"] == HEALTH_MISSING) / n_sample
        else:
            ratio_ready = ratio_partial = ratio_missing = 0.0

        ready   = round(total * ratio_ready)
        partial = round(total * ratio_partial)
        missing = round(total * ratio_missing)

        return {
            "total": total,
            "ready": ready,
            "partial": partial,
            "missing": missing,
            "labeled": labeled,
            "fully_embedded": embedded,
            "sampled_from": n_sample,
            "milestone_progress": {
                "target": 20,
                "achieved": ready,
                "percent": round(ready / 20 * 100, 1) if ready else 0.0,
            },
        }

    @staticmethod
    def _jsonl_non_empty(path: Path) -> bool:
        if not path.exists():
            return False
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        return True
        except Exception:
            pass
        return False


validation_service = ValidationService()
