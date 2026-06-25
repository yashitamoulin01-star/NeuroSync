"""
Session manager — stateful interview session lifecycle management.

Every interview is a persistent, recoverable stateful object.
The session moves through a formal lifecycle defined in orchestrator/lifecycle.py.

State machine:
    CREATED → STREAMING ↔ PAUSED → FINISHING → COMPLETED
    Any state → FAILED (terminal)
"""

import uuid
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from collections import deque
from dataclasses import dataclass, field

from backend.services.face_service import FaceAnalysisService
from backend.services.audio_service import AudioAnalysisService
from backend.services.nlp_service import NLPAnalysisService
from backend.ml_bridge.fusion_bridge import FusionBridge
from backend.models.schemas import SessionConfig, SessionSummary, FusedAnalytics
from backend.core.interfaces.session import ISessionManager
from backend.models.feature import FeatureSet
from backend.orchestrator.lifecycle import SessionStatus, can_transition, is_terminal
from backend.core.config import settings
from backend.services.media_service import MediaService, SessionMediaRecorder
from backend.services.sync_service import SessionSyncLogger
import backend.services.db_service as db

logger = logging.getLogger(__name__)

_raw_dir = Path(settings.DATASET_DIR) / "raw" / "sessions"
_media_service = MediaService(raw_dir=_raw_dir)

_DB_FRAME_EVERY = 4   # persist one DB frame every N analytics frames (~2s)


@dataclass
class ActiveSession:
    """
    A live interview session with full lifecycle and observability state.

    Every field is read-only from outside this class; mutation goes through
    the lifecycle methods on SessionManager.
    """
    session_id:  str
    config:      SessionConfig

    # ── Per-modality analysis services ───────────────────────────────────────
    face_service:  FaceAnalysisService = field(default_factory=FaceAnalysisService)
    audio_service: AudioAnalysisService = field(default_factory=AudioAnalysisService)
    nlp_service:   NLPAnalysisService   = field(default_factory=NLPAnalysisService)
    fusion_bridge: "FusionBridge" = None

    # ── Lifecycle state ───────────────────────────────────────────────────────
    status:           SessionStatus = field(default=SessionStatus.CREATED)
    started_at:       float = field(default_factory=time.time)
    last_ws_connect:  Optional[float] = None
    last_ws_disconnect: Optional[float] = None

    # ── Device + pipeline status ──────────────────────────────────────────────
    # Tracks what each pipeline can actually see.
    # "active" | "no_signal" | "unavailable" | "denied" | "unknown"
    camera_status:     str = "unknown"
    microphone_status: str = "unknown"
    transcript_status: str = "inactive"

    # ── Observability counters ────────────────────────────────────────────────
    frame_count:        int = 0
    audio_chunk_count:  int = 0
    inference_count:    int = 0    # how many times run_reasoning_pipeline was called
    evidence_count:     int = 0    # cumulative evidence items produced across all fuse() calls
    reconnect_count:    int = 0

    # ── Analytics state ───────────────────────────────────────────────────────
    last_analytics:      Optional[FusedAnalytics] = None
    analytics_timeline:  List[FusedAnalytics] = field(default_factory=list)
    recent_feature_sets: deque = field(default_factory=lambda: deque(maxlen=10))

    # ── Phase 3: temporal intelligence state ──────────────────────────────────
    score_history:    deque = field(default_factory=lambda: deque(maxlen=50))
    behavioral_state: str   = "warming_up"   # BehavioralState.value
    window_index:     int   = 0
    decision_traces:  deque = field(default_factory=lambda: deque(maxlen=100))
    reasoning_metrics: object = None  # ReasoningMetrics, set in __post_init__

    # ── Dataset / media recording ─────────────────────────────────────────────
    media_recorder: Optional["SessionMediaRecorder"] = None
    sync_logger:    Optional[SessionSyncLogger] = None

    _frame_counter: int = field(default=0, repr=False)

    def __post_init__(self):
        from backend.ml_bridge.fusion_bridge import FusionBridge
        from backend.reasoning.observability.metrics import ReasoningMetrics
        self.fusion_bridge = FusionBridge(session_id=self.session_id)
        self.reasoning_metrics = ReasoningMetrics(session_id=self.session_id)

        if settings.DATASET_AUTO_SAVE:
            try:
                self.media_recorder = _media_service.start(self.session_id)
                self.sync_logger = SessionSyncLogger(
                    session_id=self.session_id,
                    started_at=self.started_at,
                )
            except Exception as exc:
                logger.warning("Media/sync logger setup failed for %s: %s", self.session_id, exc)

        try:
            db.create_session_record(
                session_id=self.session_id,
                name=self.config.session_name,
                mode=self.config.mode,
                user_id=self.config.user_id,
                started_at=self.started_at,
            )
        except Exception as exc:
            logger.error("DB create_session_record failed for %s: %s", self.session_id, exc)

    # ── Analytics recording ───────────────────────────────────────────────────

    def get_temporal_context(self) -> dict:
        """Return Phase 3 temporal context for passing into the reasoning pipeline."""
        return {
            "score_history":    list(self.score_history),
            "behavioral_state": self.behavioral_state,
            "window_index":     self.window_index,
        }

    def record_frame(self, frame: FusedAnalytics):
        self.last_analytics = frame
        self.analytics_timeline.append(frame)
        self.inference_count += 1

        # Accumulate evidence count from the reasoning layer
        if frame.score_breakdown:
            self.evidence_count += frame.score_breakdown.evidence_count

        # Phase 3: maintain temporal state
        from backend.reasoning.timeline.temporal_engine import ScoreSnapshot
        snapshot = ScoreSnapshot(
            window_index    = self.window_index,
            elapsed_seconds = frame.session_duration,
            confidence      = frame.overall_confidence,
            stress          = frame.stress_level,
            communication   = frame.communication_quality,
            engagement      = frame.engagement_score,
            consistency     = frame.behavioral_consistency,
            reliability     = (
                frame.score_breakdown.reliability.value
                if frame.score_breakdown else "insufficient"
            ),
        )
        self.score_history.append(snapshot)
        self.window_index += 1

        if frame.behavioral_state:
            self.behavioral_state = frame.behavioral_state

        if frame.decision_trace:
            self.decision_traces.append(frame.decision_trace)

        # Update observability metrics
        if self.reasoning_metrics and frame.calibration:
            self.reasoning_metrics.record_window(
                evidence_count        = len(frame.evidence),
                conflict_count        = frame.conflict_count,
                prediction_confidence = frame.calibration.get("prediction_confidence", 0.0),
                latency_ms            = 0.0,  # latency tracked inside pipeline
                rules_fired           = len(frame.calibration.get("calibration_notes", [])),
                missing_modalities    = (
                    3 - sum([
                        1 if frame.data_quality and frame.data_quality.face_available  else 0,
                        1 if frame.data_quality and frame.data_quality.audio_available else 0,
                        1 if frame.data_quality and frame.data_quality.nlp_available   else 0,
                    ])
                ) if frame.data_quality else 0,
                state_changed         = bool(
                    frame.decision_trace and frame.decision_trace.get("state_changed")
                ),
                calibration_applied   = bool(frame.calibration and frame.calibration.get("calibration_notes")),
            )

        # Update device status from the reasoning layer's quality assessment
        if frame.data_quality:
            dq = frame.data_quality
            if dq.face_available:
                self.camera_status = "active"
            elif self.camera_status == "unknown":
                self.camera_status = "no_signal"

            if dq.audio_available:
                self.microphone_status = "active"
                if dq.nlp_available:
                    self.transcript_status = "active"
            elif self.microphone_status == "unknown":
                self.microphone_status = "no_signal"

        # Behavioral insight sync logging
        if self.sync_logger and frame.insights:
            for ins in frame.insights:
                self.sync_logger.log_behavioral_insight(
                    insight_type=ins.type,
                    description=ins.description,
                    severity=ins.severity,
                    modalities=[m.value for m in ins.modalities_involved],
                )

        # Sampled DB persistence (~every 2s)
        self._frame_counter += 1
        if self._frame_counter % _DB_FRAME_EVERY == 0:
            try:
                eye = frame.face.eye_contact_score if frame.face else 0.0
                speaking = frame.audio.is_speaking if frame.audio else False
                db.record_frame(
                    session_id=self.session_id,
                    ts=frame.timestamp - self.started_at,
                    confidence=frame.overall_confidence,
                    stress=frame.stress_level,
                    engagement=frame.engagement_score,
                    communication=frame.communication_quality,
                    consistency=frame.behavioral_consistency,
                    eye_contact=eye,
                    is_speaking=speaking,
                )
            except Exception as e:
                logger.debug("DB frame write failed: %s", e)

    def record_feature_set(self, fs: FeatureSet):
        """Store recent feature sets for live inspection."""
        self.recent_feature_sets.append(fs)

    def compute_summary_averages(self):
        timeline = self.analytics_timeline
        if not timeline:
            return {
                "avg_confidence": 0.0, "avg_stress": 0.0, "avg_engagement": 0.0,
                "avg_communication": 0.0, "avg_consistency": 0.0, "avg_eye_contact": 0.0,
            }
        n = len(timeline)
        return {
            "avg_confidence":    sum(f.overall_confidence     for f in timeline) / n,
            "avg_stress":        sum(f.stress_level           for f in timeline) / n,
            "avg_engagement":    sum(f.engagement_score       for f in timeline) / n,
            "avg_communication": sum(f.communication_quality  for f in timeline) / n,
            "avg_consistency":   sum(f.behavioral_consistency for f in timeline) / n,
            "avg_eye_contact":   sum(
                f.face.eye_contact_score if f.face else 0.0 for f in timeline
            ) / n,
        }

    def to_live_state(self) -> dict:
        """Snapshot of all observable session state for the /api/sessions/{id}/live endpoint."""
        last = self.last_analytics
        reliability = None
        current_scores = None
        if last and last.score_breakdown:
            sb = last.score_breakdown
            reliability = sb.reliability.value
            current_scores = {
                "confidence":    last.overall_confidence,
                "stress":        last.stress_level,
                "communication": last.communication_quality,
                "engagement":    last.engagement_score,
                "consistency":   last.behavioral_consistency,
            }

        return {
            "session_id":         self.session_id,
            "status":             self.status.value,
            "duration":           round(time.time() - self.started_at, 1),
            "camera_status":      self.camera_status,
            "microphone_status":  self.microphone_status,
            "transcript_status":  self.transcript_status,
            "frame_count":        self.frame_count,
            "audio_chunk_count":  self.audio_chunk_count,
            "inference_count":    self.inference_count,
            "evidence_count":     self.evidence_count,
            "reconnect_count":    self.reconnect_count,
            "reliability":        reliability,
            "current_scores":     current_scores,
            "last_ws_connect":    self.last_ws_connect,
            "last_ws_disconnect": self.last_ws_disconnect,
            # Phase 3
            "behavioral_state":   self.behavioral_state,
            "window_index":       self.window_index,
            "reasoning_metrics":  (
                self.reasoning_metrics.to_dict() if self.reasoning_metrics else None
            ),
        }


class SessionManager(ISessionManager):
    def __init__(self):
        self._sessions: Dict[str, ActiveSession] = {}

    # ── Lifecycle management ──────────────────────────────────────────────────

    def create_session(self, config: SessionConfig) -> str:
        session_id = str(uuid.uuid4())
        try:
            self._sessions[session_id] = ActiveSession(
                session_id=session_id,
                config=config,
            )
        except Exception as exc:
            logger.error("Session init failed for %s: %s", session_id, exc)
            raise
        logger.info(
            "Session created: %s  mode=%s  name=%r",
            session_id, config.mode, config.session_name,
        )
        return session_id

    def on_ws_connect(self, session_id: str) -> bool:
        """
        Called when a WebSocket connects to a session.
        Transitions CREATED or PAUSED → STREAMING.
        Returns True on success, False if the session is terminal or missing.
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        if is_terminal(session.status):
            return False
        if can_transition(session.status, SessionStatus.STREAMING):
            if session.status == SessionStatus.PAUSED:
                session.reconnect_count += 1
                logger.info(
                    "Session resumed (reconnect #%d): %s",
                    session.reconnect_count, session_id,
                )
            session.status = SessionStatus.STREAMING
            session.last_ws_connect = time.time()
            return True
        return False

    def on_ws_disconnect(self, session_id: str):
        """
        Called when a WebSocket disconnects.
        Transitions STREAMING → PAUSED (session preserved for reconnection).
        """
        session = self._sessions.get(session_id)
        if not session:
            return
        if can_transition(session.status, SessionStatus.PAUSED):
            session.status = SessionStatus.PAUSED
            session.last_ws_disconnect = time.time()
            logger.info("Session paused (client disconnected): %s", session_id)

    def get_session(self, session_id: str) -> Optional[ActiveSession]:
        return self._sessions.get(session_id)

    def end_session(self, session_id: str) -> Optional[SessionSummary]:
        session = self._sessions.pop(session_id, None)
        if not session:
            return None

        session.status = SessionStatus.FINISHING
        ended_at = time.time()
        duration = ended_at - session.started_at
        averages = session.compute_summary_averages()

        last = session.last_analytics
        insights = last.insights[:5] if last else []
        transcript = session.audio_service.get_full_transcript()
        total_filler = session.nlp_service.session_filler_total
        avg_pace = last.avg_speaking_pace if last else 0.0

        summary = SessionSummary(
            session_id=session_id,
            duration=round(duration, 1),
            avg_confidence=averages["avg_confidence"],
            avg_eye_contact=averages["avg_eye_contact"],
            avg_stress=averages["avg_stress"],
            total_filler_words=total_filler,
            avg_speaking_pace=avg_pace,
            avg_communication_quality=averages["avg_communication"],
            top_insights=insights,
            transcript=transcript,
        )

        try:
            db.finalize_session(
                session_id=session_id,
                ended_at=ended_at,
                duration=duration,
                avg_confidence=averages["avg_confidence"],
                avg_stress=averages["avg_stress"],
                avg_engagement=averages["avg_engagement"],
                avg_communication=averages["avg_communication"],
                avg_consistency=averages["avg_consistency"],
                avg_eye_contact=averages["avg_eye_contact"],
                avg_speaking_pace=avg_pace,
                total_filler_words=total_filler,
                total_words=last.total_words_spoken if last else 0,
                transcript=transcript,
                insights=[i.model_dump() for i in insights],
            )
            session.status = SessionStatus.COMPLETED
            logger.info(
                "Session completed: %s  duration=%.0fs  frames=%d  evidence=%d",
                session_id, duration, session.frame_count, session.evidence_count,
            )
        except Exception as e:
            session.status = SessionStatus.FAILED
            logger.error("DB finalize failed for %s: %s", session_id, e)

        if settings.DATASET_AUTO_SAVE:
            try:
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
        stale = [
            sid for sid, s in self._sessions.items()
            if now - s.started_at > max_age_seconds
        ]
        for sid in stale:
            logger.warning("Cleaning up stale session: %s  status=%s", sid, self._sessions[sid].status.value)
            session = self._sessions.pop(sid, None)
            if session and session.media_recorder:
                _media_service.stop(sid)


session_manager = SessionManager()
