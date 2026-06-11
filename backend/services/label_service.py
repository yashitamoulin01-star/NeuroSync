"""
Label management service.
CRUD for behavioral session labels used by the internal labeling dashboard.
"""

import json
import time
import logging
from pathlib import Path
from typing import Optional, List

from backend.models.label_schemas import SessionLabel, LabelSubmitRequest
from backend.services.dataset_service import dataset_service
from backend.core.config import settings

logger = logging.getLogger(__name__)


class LabelService:
    def __init__(self):
        self.base = Path(settings.DATASET_DIR) / "labeled" / "sessions"
        self.base.mkdir(parents=True, exist_ok=True)

    def _label_path(self, session_id: str) -> Path:
        return self.base / session_id / "labels.json"

    # ── Read ──────────────────────────────────────────────────────────────────

    def get(self, session_id: str) -> Optional[SessionLabel]:
        path = self._label_path(session_id)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return SessionLabel(**json.load(f))

    def get_session_for_labeling(self, session_id: str) -> Optional[dict]:
        session_path = dataset_service.get_session_path(session_id)
        if not session_path:
            return None

        result: dict = {}

        meta_path = session_path / "metadata.json"
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                result["metadata"] = json.load(f)

        transcript_path = session_path / "transcript.txt"
        if transcript_path.exists():
            result["transcript"] = transcript_path.read_text(encoding="utf-8")
        else:
            result["transcript"] = ""

        # Fused timeline for the labeling timeline view
        timeline_path = session_path / "fused_timeline.jsonl"
        timeline = []
        if timeline_path.exists():
            with open(timeline_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        timeline.append(json.loads(line))
        result["timeline"] = timeline

        existing = self.get(session_id)
        result["existing_label"] = existing.model_dump() if existing else None
        return result

    # ── Write ─────────────────────────────────────────────────────────────────

    def save(self, label: SessionLabel) -> SessionLabel:
        label_dir = self.base / label.session_id
        label_dir.mkdir(parents=True, exist_ok=True)
        (label_dir / "labels.json").write_text(
            label.model_dump_json(indent=2), encoding="utf-8"
        )
        status = "labeled" if label.is_complete else "in_progress"
        dataset_service.update_label_status(label.session_id, status)
        logger.info("Label saved for session %s (complete=%s)", label.session_id, label.is_complete)
        return label

    def submit(self, session_id: str, req: LabelSubmitRequest) -> SessionLabel:
        label = SessionLabel(
            session_id=session_id,
            labeled_at=time.time(),
            labeled_by=req.labeled_by,
            overall=req.overall,
            temporal_labels=req.temporal_labels,
            is_complete=True,
        )
        return self.save(label)

    def delete(self, session_id: str):
        path = self._label_path(session_id)
        if path.exists():
            path.unlink()
        dataset_service.update_label_status(session_id, "unlabeled")

    # ── Lists ─────────────────────────────────────────────────────────────────

    def list_unlabeled(self) -> List[dict]:
        return dataset_service.list_sessions(label_status="unlabeled")

    def list_in_progress(self) -> List[dict]:
        return dataset_service.list_sessions(label_status="in_progress")

    def list_labeled(self) -> List[dict]:
        return dataset_service.list_sessions(label_status="labeled")


label_service = LabelService()
