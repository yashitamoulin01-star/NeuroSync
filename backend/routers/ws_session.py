"""
WebSocket router — real-time communication channel.

Responsibilities:
  - Transport only: receive frames/audio, push analytics, handle ping/pong.
  - Delegates ALL inference to per-modality services and fusion_bridge.
  - Delegates ALL lifecycle management to session_manager.

Message protocol (JSON):
  Client → Server:
    { "type": "frame",   "session_id": "...", "payload": { "image_b64": "..." } }
    { "type": "audio",   "session_id": "...", "payload": { "pcm_b64": "...", "sample_rate": 16000 } }
    { "type": "ping",    "session_id": "..." }
    { "type": "end",     "session_id": "..." }

  Server → Client:
    { "type": "analytics_update",  "session_id": "...", "payload": { ...FusedAnalytics } }
    { "type": "transcript_update", "session_id": "...", "payload": { "text": "...", "full": "..." } }
    { "type": "session_state",     "session_id": "...", "payload": { ...session live state } }
    { "type": "pong",              "session_id": "..." }
    { "type": "error",             "session_id": "...", "payload": { "message": "..." } }
"""

import asyncio
import base64
import json
import time
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from backend.services.session_manager import session_manager
from backend.services.metrics_service import metrics_service
from backend.models.schemas import WSMessageType, FaceMetrics, AudioMetrics
from backend.orchestrator.lifecycle import SessionStatus

logger = logging.getLogger(__name__)
router = APIRouter()

ANALYTICS_INTERVAL = 0.5   # push fused analytics every 500ms


@router.websocket("/ws/session/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()

    session = session_manager.get_session(session_id)
    if not session:
        await _send_error(websocket, session_id, "Session not found. POST /api/session first.")
        await websocket.close()
        return

    # Reject connections to completed/failed sessions
    if session.status in (SessionStatus.COMPLETED, SessionStatus.FAILED):
        await _send_error(websocket, session_id,
                          f"Session already {session.status.value} — cannot reconnect.")
        await websocket.close()
        return

    # Lifecycle: CREATED or PAUSED → STREAMING
    is_reconnect = session.status == SessionStatus.PAUSED
    reconnected = session_manager.on_ws_connect(session_id)
    if not reconnected:
        await _send_error(websocket, session_id, "Session could not transition to streaming state.")
        await websocket.close()
        return

    if is_reconnect:
        logger.info("Client reconnected to session %s (reconnect #%d)",
                    session_id, session.reconnect_count)
        # Notify client of reconnection so the UI can update its state indicator
        await websocket.send_json({
            "type": "session_state",
            "session_id": session_id,
            "payload": session.to_live_state(),
            "timestamp": time.time(),
        })

    last_analytics_push = 0.0
    transcript_seg_start = session.started_at

    try:
        while True:
            if websocket.client_state != WebSocketState.CONNECTED:
                break

            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                data = json.loads(raw)
            except asyncio.TimeoutError:
                data = None
            except Exception:
                break

            if data:
                metrics_service.record_ws_message()
                msg_type = data.get("type", "")

                # ── Ping ──────────────────────────────────────────────────────
                if msg_type == "ping":
                    await websocket.send_json({
                        "type": WSMessageType.PONG,
                        "session_id": session_id,
                        "timestamp": time.time(),
                    })

                # ── Video frame ───────────────────────────────────────────────
                elif msg_type == "frame":
                    image_b64 = data.get("payload", {}).get("image_b64", "")
                    if image_b64:
                        frame_bytes = base64.b64decode(image_b64)
                        now = time.time()
                        metrics_service.record_ws_frame()
                        session.frame_count += 1

                        loop = asyncio.get_running_loop()
                        _t0 = time.perf_counter()
                        try:
                            face_metrics = await asyncio.wait_for(
                                loop.run_in_executor(
                                    None,
                                    session.face_service.process_frame_b64,
                                    image_b64,
                                ),
                                timeout=3.0,
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Face processing timed out for %s — skipping frame", session_id)
                            face_metrics = FaceMetrics()
                        metrics_service.record("face", (time.perf_counter() - _t0) * 1000)
                        session.fusion_bridge.push_face(face_metrics)

                        # Device status from signal
                        if face_metrics.face_detected:
                            session.camera_status = "active"
                        elif session.camera_status == "unknown":
                            session.camera_status = "no_signal"

                        # Media recording
                        if session.media_recorder:
                            session.media_recorder.write_frame(frame_bytes, now)

                        # Sync: gaze events
                        if session.sync_logger and face_metrics.face_detected:
                            if face_metrics.eye_contact_score < 0.35:
                                session.sync_logger.log_event(
                                    "gaze_aversion", "face",
                                    severity=1.0 - face_metrics.eye_contact_score,
                                )
                            if face_metrics.facial_tension > 0.6:
                                session.sync_logger.log_event(
                                    "facial_tension_spike", "face",
                                    severity=face_metrics.facial_tension,
                                )

                # ── Audio chunk ───────────────────────────────────────────────
                elif msg_type == "audio":
                    payload = data.get("payload", {})
                    pcm_b64 = payload.get("pcm_b64", "")
                    sample_rate = payload.get("sample_rate", 16000)
                    if pcm_b64:
                        audio_bytes = base64.b64decode(pcm_b64)
                        now = time.time()
                        loop = asyncio.get_running_loop()
                        session.audio_chunk_count += 1

                        # Voice metrics
                        _t0 = time.perf_counter()
                        try:
                            audio_metrics = await asyncio.wait_for(
                                loop.run_in_executor(
                                    None,
                                    session.audio_service.process_audio_chunk,
                                    audio_bytes,
                                    sample_rate,
                                ),
                                timeout=4.0,
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Audio processing timed out for %s", session_id)
                            audio_metrics = AudioMetrics()
                        metrics_service.record("audio", (time.perf_counter() - _t0) * 1000)
                        session.fusion_bridge.push_audio(audio_metrics)

                        # Device status
                        if audio_metrics.is_speaking:
                            session.microphone_status = "active"
                        elif session.microphone_status == "unknown":
                            session.microphone_status = "no_signal"

                        # Media recording
                        if session.media_recorder:
                            session.media_recorder.write_audio(audio_bytes, sample_rate, now)

                        # Sync: audio events
                        if session.sync_logger:
                            if audio_metrics.voice_stress_score > 0.65:
                                session.sync_logger.log_event(
                                    "voice_stress_spike", "audio",
                                    severity=audio_metrics.voice_stress_score,
                                )
                            if audio_metrics.pause_ratio > 0.5:
                                session.sync_logger.log_event(
                                    "excessive_pause", "audio",
                                    severity=audio_metrics.pause_ratio,
                                )

                        # Transcription (Whisper)
                        try:
                            transcript_chunk = await asyncio.wait_for(
                                loop.run_in_executor(
                                    None,
                                    session.audio_service.process_audio_for_transcript,
                                    audio_bytes,
                                ),
                                timeout=10.0,
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Whisper transcription timed out for %s", session_id)
                            transcript_chunk = None

                        if transcript_chunk and transcript_chunk.text:
                            seg_end = time.time()
                            _t0 = time.perf_counter()
                            nlp_metrics = await loop.run_in_executor(
                                None,
                                session.nlp_service.analyze_transcript_chunk,
                                transcript_chunk.text,
                                2.0,
                            )
                            metrics_service.record("nlp", (time.perf_counter() - _t0) * 1000)
                            session.fusion_bridge.push_nlp(nlp_metrics)
                            session.transcript_status = "active"

                            # Sync: transcript + NLP events
                            if session.sync_logger:
                                session.sync_logger.log_transcript_segment(
                                    text=transcript_chunk.text,
                                    start_abs=transcript_seg_start,
                                    end_abs=seg_end,
                                )
                                if nlp_metrics.hesitation_score > 0.6:
                                    session.sync_logger.log_event(
                                        "hesitation_burst", "nlp",
                                        severity=nlp_metrics.hesitation_score,
                                        text=transcript_chunk.text[:80],
                                    )
                                if nlp_metrics.filler_word_count > 0:
                                    session.sync_logger.log_event(
                                        "filler_words", "nlp",
                                        severity=min(nlp_metrics.filler_word_count / 5, 1.0),
                                        count=nlp_metrics.filler_word_count,
                                    )
                            transcript_seg_start = seg_end

                            await websocket.send_json({
                                "type": WSMessageType.TRANSCRIPT_UPDATE,
                                "session_id": session_id,
                                "payload": {
                                    "text":              transcript_chunk.text,
                                    "full":              session.audio_service.get_full_transcript(),
                                    "word_count":        transcript_chunk.word_count,
                                    "filler_count":      nlp_metrics.filler_word_count,
                                    "confidence_score":  nlp_metrics.confidence_language_score,
                                    "hesitation_score":  nlp_metrics.hesitation_score,
                                    "timestamp":         time.time(),
                                },
                                "timestamp": time.time(),
                            })

                # ── Session end ───────────────────────────────────────────────
                elif msg_type == "end":
                    summary = session_manager.end_session(session_id)
                    await websocket.send_json({
                        "type": WSMessageType.SESSION_END,
                        "session_id": session_id,
                        "payload": summary.model_dump() if summary else {},
                        "timestamp": time.time(),
                    })
                    break

            # ── Periodic analytics push ───────────────────────────────────────
            now = time.time()
            if now - last_analytics_push >= ANALYTICS_INTERVAL:
                temporal = session.get_temporal_context()
                fused = session.fusion_bridge.get_fused(**temporal)
                session.record_frame(fused)

                payload = fused.model_dump()
                # Prune heavy fields from WS payload (available via REST)
                payload.pop("evidence", None)
                payload.pop("explanation", None)    # large — REST only
                payload.pop("decision_trace", None) # large — REST only

                await websocket.send_json({
                    "type": WSMessageType.ANALYTICS_UPDATE,
                    "session_id": session_id,
                    "payload": payload,
                    "timestamp": now,
                })
                last_analytics_push = now

    except WebSocketDisconnect:
        logger.info("Client disconnected: %s", session_id)
    except Exception as e:
        logger.exception("WebSocket error for %s: %s", session_id, e)
        try:
            await _send_error(websocket, session_id, str(e))
        except Exception:
            pass
    finally:
        # Preserve session in PAUSED state — client can reconnect
        session_manager.on_ws_disconnect(session_id)


async def _send_error(ws: WebSocket, session_id: str, message: str):
    try:
        await ws.send_json({
            "type": WSMessageType.ERROR,
            "session_id": session_id,
            "payload": {"message": message},
        })
    except Exception:
        pass
