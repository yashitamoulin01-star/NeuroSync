"""
WebSocket router — real-time communication channel.

Message protocol (JSON):
  Client → Server:
    { "type": "frame",   "session_id": "...", "payload": { "image_b64": "..." } }
    { "type": "audio",   "session_id": "...", "payload": { "pcm_b64": "...", "sample_rate": 16000 } }
    { "type": "ping",    "session_id": "..." }
    { "type": "end",     "session_id": "..." }

  Server → Client:
    { "type": "analytics_update",  "session_id": "...", "payload": { ...FusedAnalytics } }
    { "type": "transcript_update", "session_id": "...", "payload": { "text": "...", "full": "..." } }
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
from backend.models.schemas import WSMessageType

logger = logging.getLogger(__name__)
router = APIRouter()

ANALYTICS_INTERVAL = 0.5   # push fused analytics every 500ms


@router.websocket("/ws/session/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = session_manager.get_session(session_id)
    if not session:
        await websocket.send_json({
            "type": WSMessageType.ERROR,
            "session_id": session_id,
            "payload": {"message": "Session not found. POST /api/session first."},
        })
        await websocket.close()
        return

    last_analytics_push = 0.0
    transcript_seg_start = session.started_at   # track segment start for sync

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

                        loop = asyncio.get_event_loop()
                        face_metrics = await loop.run_in_executor(
                            None,
                            session.face_service.process_frame_b64,
                            image_b64,
                        )
                        session.fusion_bridge.push_face(face_metrics)

                        # Non-blocking media record
                        if session.media_recorder:
                            session.media_recorder.write_frame(frame_bytes, now)

                        # Sync: log gaze events
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
                        loop = asyncio.get_event_loop()

                        # Voice metrics
                        audio_metrics = await loop.run_in_executor(
                            None,
                            session.audio_service.process_audio_chunk,
                            audio_bytes,
                            sample_rate,
                        )
                        session.fusion_bridge.push_audio(audio_metrics)

                        # Non-blocking media record
                        if session.media_recorder:
                            session.media_recorder.write_audio(audio_bytes, sample_rate, now)

                        # Sync: log audio events
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

                        # Transcription
                        transcript_chunk = await loop.run_in_executor(
                            None,
                            session.audio_service.process_audio_for_transcript,
                            audio_bytes,
                        )
                        if transcript_chunk and transcript_chunk.text:
                            seg_end = time.time()
                            nlp_metrics = await loop.run_in_executor(
                                None,
                                session.nlp_service.analyze_transcript_chunk,
                                transcript_chunk.text,
                                2.0,
                            )
                            session.fusion_bridge.push_nlp(nlp_metrics)

                            # Log transcript segment for sync
                            if session.sync_logger:
                                session.sync_logger.log_transcript_segment(
                                    text=transcript_chunk.text,
                                    start_abs=transcript_seg_start,
                                    end_abs=seg_end,
                                )
                                # Log NLP events
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
                                    "text": transcript_chunk.text,
                                    "full": session.audio_service.get_full_transcript(),
                                    "word_count": transcript_chunk.word_count,
                                    "filler_count": nlp_metrics.filler_word_count,
                                    "confidence_score": nlp_metrics.confidence_language_score,
                                    "hesitation_score": nlp_metrics.hesitation_score,
                                    "timestamp": time.time(),
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
                fused = session.fusion_bridge.get_fused()
                session.record_frame(fused)
                await websocket.send_json({
                    "type": WSMessageType.ANALYTICS_UPDATE,
                    "session_id": session_id,
                    "payload": fused.model_dump(),
                    "timestamp": now,
                })
                last_analytics_push = now

    except WebSocketDisconnect:
        logger.info("Client disconnected: %s", session_id)
    except Exception as e:
        logger.exception("WebSocket error for %s: %s", session_id, e)
        try:
            await websocket.send_json({
                "type": WSMessageType.ERROR,
                "session_id": session_id,
                "payload": {"message": str(e)},
            })
        except Exception:
            pass
