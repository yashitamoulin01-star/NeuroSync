"""
Session manager — tracks active WebSocket sessions and their analytics state.
"""

import uuid
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from backend.services.face_service import FaceAnalysisService
from backend.services.audio_service import AudioAnalysisService
from backend.services.nlp_service import NLPAnalysisService
from backend.ml_bridge.fusion_bridge import FusionBridge
from backend.models.schemas import SessionConfig, SessionSummary, FusedAnalytics
from backend.core.config import settings
from backend.services.media_service import MediaService, SessionMediaRecorder
from backend.services.sync_service import SessionSyncLogger

logger = logging.getLogger(__name__)

_raw_dir = Path(settings.DATASET_DIR) / "raw" / "sessions"
_media_service = MediaService(raw_dir=_raw_dir)


@dataclass
class ActiveSession:
    session_id: str
    config: SessionConfig
    face_service: FaceAnalysisService = field(default_factory=FaceAnalysisService)
    audio_service: AudioAnalysisService = field(default_factory=AudioAnalysisService)
    nlp_service: NLPAnalysisService = field(default_factory=NLPAnalysisService)
    fusion_bridge: "FusionBridge" = None
    started_at: float = field(default_factory=time.time)
    last_analytics: Optional[FusedAnalytics] = None
    analytics_timeline: List[FusedAnalytics] = field(default_factory=list)
    media_recorder: Optional[SessionMediaRecorder] = None
    sync_logger: Optional[SessionSyncLogger] = None

    def __post_init__(self):
        from backend.ml_bridge.fusion_bridge import FusionBridge
        self.fusion_bridge = FusionBridge(session_id=self.session_id)
        if settings.DATASET_AUTO_SAVE:
            self.media_recorder = _media_service.start(self.session_id)
            self.sync_logger = SessionSyncLogger(
                session_id=self.session_id,
                started_at=self.started_at,
            )

    def record_frame(self, frame: FusedAnalytics):
        self.last_analytics = frame
        self.analytics_timeline.append(frame)
        # Log behavioral insights as sync events
        if self.sync_logger and frame.insights:
            for ins in frame.insights:
                self.sync_logger.log_behavioral_insight(
                    insight_type=ins.type,
                    description=ins.description,
                    severity=ins.severity,
                    modalities=[m.value for m in ins.modalities_involved],
                )


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, ActiveSession] = {}

    def create_session(self, config: SessionConfig) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = ActiveSession(
            session_id=session_id,
            config=config,
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[ActiveSession]:
        return self._sessions.get(session_id)

    def end_session(self, session_id: str) -> Optional[SessionSummary]:
        session = self._sessions.pop(session_id, None)
        if not session:
            return None

        last = session.last_analytics
        if not last:
            # Finalize media even for empty sessions
            if session.media_recorder:
                _media_service.stop(session_id)
            return None

        summary = SessionSummary(
            session_id=session_id,
            duration=last.session_duration,
            avg_confidence=last.overall_confidence,
            avg_eye_contact=last.face.eye_contact_score if last.face else 0.0,
            avg_stress=last.stress_level,
            total_filler_words=last.total_filler_words,
            avg_speaking_pace=last.avg_speaking_pace,
            avg_communication_quality=last.communication_quality,
            top_insights=last.insights[:5],
            transcript=session.audio_service.get_full_transcript(),
        )

        if settings.DATASET_AUTO_SAVE:
            try:
                # Finalize media recording first
                media_result = _media_service.stop(session_id)

                from backend.services.dataset_service import dataset_service
                dataset_service.save_session(
                    session_id=session_id,
                    summary=summary,
                    timeline=session.analytics_timeline,
                    config={
                        "session_name": session.config.session_name,
                        "mode": session.config.mode,
                        "user_id": session.config.user_id,
                    },
                    sync_logger=session.sync_logger,
                    media_result=media_result,
                )
            except Exception as e:
                logger.error("Dataset auto-save failed for %s: %s", session_id, e)

        return summary

    def cleanup_stale(self, max_age_seconds: int = 3600):
        now = time.time()
        stale = [sid for sid, s in self._sessions.items()
                 if now - s.started_at > max_age_seconds]
        for sid in stale:
            session = self._sessions.pop(sid, None)
            if session and session.media_recorder:
                _media_service.stop(sid)


session_manager = SessionManager()
