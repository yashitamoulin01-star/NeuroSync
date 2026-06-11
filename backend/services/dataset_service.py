"""
Dataset persistence service.
Saves session analytics timelines, raw media references, and timestamps.json.
Auto-called when a session ends (if DATASET_AUTO_SAVE=True).
"""

import json
import time
import logging
from pathlib import Path
from typing import Optional, List

from backend.models.schemas import FusedAnalytics, SessionSummary
from backend.core.config import settings

logger = logging.getLogger(__name__)


class DatasetService:
    def __init__(self):
        self.base = Path(settings.DATASET_DIR)
        self._bootstrap_dirs()

    def _bootstrap_dirs(self):
        for sub in [
            "raw/sessions",
            "processed/sessions",
            "labeled/sessions",
            "embeddings/sessions",
            "splits",
            "exports/deberta",
            "exports/fusion",
        ]:
            (self.base / sub).mkdir(parents=True, exist_ok=True)

    # ── Save ──────────────────────────────────────────────────────────────────

    def save_session(
        self,
        session_id: str,
        summary: SessionSummary,
        timeline: List[FusedAnalytics],
        config: dict,
        sync_logger=None,       # SessionSyncLogger | None
        media_result: Optional[dict] = None,
    ) -> Path:
        session_dir = self.base / "processed" / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Fused timeline (alias: metrics.jsonl)
        with open(session_dir / "fused_timeline.jsonl", "w", encoding="utf-8") as f:
            for frame in timeline:
                f.write(frame.model_dump_json() + "\n")

        # Per-modality JSONL
        faces  = [a.face  for a in timeline if a.face]
        audios = [a.audio for a in timeline if a.audio]
        nlps   = [a.nlp   for a in timeline if a.nlp]

        for name, rows in [
            ("face_metrics",  faces),
            ("audio_metrics", audios),
            ("nlp_metrics",   nlps),
        ]:
            with open(session_dir / f"{name}.jsonl", "w", encoding="utf-8") as f:
                for row in rows:
                    f.write(row.model_dump_json() + "\n")

        # Plain-text transcript
        if summary.transcript:
            (session_dir / "transcript.txt").write_text(summary.transcript, encoding="utf-8")

        # timestamps.json — multimodal sync file
        media_res = media_result or {}
        if sync_logger is not None:
            try:
                from backend.services.media_service import _DEFAULT_FPS
                recorder = None
                try:
                    from backend.services.session_manager import _media_service
                    # recorder already finalized; get stats from media_result
                except Exception:
                    pass

                sync_logger.save(
                    path=session_dir / "timestamps.json",
                    duration=summary.duration,
                    video_frame_timestamps=media_res.get("frame_timestamps", []),
                    audio_chunk_meta=media_res.get("audio_chunk_meta", []),
                    video_fps=_DEFAULT_FPS,
                    audio_sample_rate=16000,
                )
            except Exception as e:
                logger.warning("timestamps.json generation failed: %s", e)

        # Metadata
        raw_dir = self.base / "raw" / "sessions" / session_id
        has_video = (raw_dir / "video.mp4").exists()
        has_audio = (raw_dir / "audio.wav").exists()

        meta = {
            "session_id": session_id,
            "saved_at": time.time(),
            "duration": summary.duration,
            "config": config,
            "media": {
                "has_video": has_video,
                "has_audio": has_audio,
                "video_frames": media_res.get("total_frames", 0),
                "audio_chunks": media_res.get("total_audio_chunks", 0),
            },
            "stats": {
                "total_frames": len(timeline),
                "face_frames": len(faces),
                "audio_frames": len(audios),
                "nlp_frames": len(nlps),
                "total_filler_words": summary.total_filler_words,
                "avg_speaking_pace": summary.avg_speaking_pace,
            },
            "summary": summary.model_dump(),
            "label_status": "unlabeled",
        }
        with open(session_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        logger.info(
            "Session %s persisted → %d frames | video=%s audio=%s",
            session_id[:8], len(timeline), has_video, has_audio,
        )
        return session_dir

    # ── Query ─────────────────────────────────────────────────────────────────

    def list_sessions(
        self,
        label_status: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[dict]:
        """Return paginated session metadata. Does not sort to handle large datasets."""
        sessions_dir = self.base / "processed" / "sessions"
        if not sessions_dir.exists():
            return []
        rows = []
        skipped = 0
        for d in sessions_dir.iterdir():
            if not d.is_dir():
                continue
            meta_path = d / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                continue
            if label_status and meta.get("label_status") != label_status:
                continue
            if skipped < offset:
                skipped += 1
                continue
            rows.append(meta)
            if len(rows) >= limit:
                break
        return rows

    def get_session_path(self, session_id: str) -> Optional[Path]:
        p = self.base / "processed" / "sessions" / session_id
        return p if p.exists() else None

    def update_label_status(self, session_id: str, status: str):
        meta_path = self.base / "processed" / "sessions" / session_id / "metadata.json"
        if not meta_path.exists():
            return
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        meta["label_status"] = status
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Fast stats by counting directories rather than reading all metadata."""
        proc_dir    = self.base / "processed" / "sessions"
        labeled_dir = self.base / "labeled" / "sessions"

        total   = sum(1 for d in proc_dir.iterdir()    if d.is_dir()) if proc_dir.exists()    else 0
        labeled = sum(1 for d in labeled_dir.iterdir() if d.is_dir()) if labeled_dir.exists() else 0

        return {
            "total_sessions": total,
            "unlabeled": max(0, total - labeled),
            "in_progress": 0,
            "labeled": labeled,
            "total_duration_minutes": 0.0,
            "sessions_with_video": 0,
        }


dataset_service = DatasetService()
