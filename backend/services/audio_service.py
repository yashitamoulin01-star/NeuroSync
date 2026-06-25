"""
Audio analysis service — wraps voice analyzer and transcriber.
Handles raw PCM audio chunks sent via WebSocket.
"""

import numpy as np
import time
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.models.schemas import AudioMetrics
from backend.core.config import settings

logger = logging.getLogger(__name__)

# ── Shared Whisper model singleton ────────────────────────────────────────────
# Whisper loads hundreds of MB — share one instance across all sessions.
# Each AudioAnalysisService gets its own buffer/state but reuses this model.

_shared_transcriber = None

def _get_shared_transcriber():
    global _shared_transcriber
    if _shared_transcriber is None:
        try:
            from ml.nlp.transcriber import WhisperTranscriber
            _shared_transcriber = WhisperTranscriber(
                model_size=settings.WHISPER_MODEL,
                device=settings.WHISPER_DEVICE,
                sample_rate=settings.AUDIO_SAMPLE_RATE,
            )
            logger.info("Shared Whisper transcriber loaded (model=%s device=%s)",
                        settings.WHISPER_MODEL, settings.WHISPER_DEVICE)
        except Exception as exc:
            logger.warning("Whisper unavailable — transcription disabled: %s", exc)
    return _shared_transcriber


class AudioAnalysisService:
    def __init__(self):
        self._initialized = False
        self._voice_analyzer = None
        self._transcriber = None
        self._session_start: float = time.time()
        try:
            from ml.audio.voice_analyzer import VoiceAnalyzer
            self._voice_analyzer = VoiceAnalyzer(sample_rate=settings.AUDIO_SAMPLE_RATE)
            self._transcriber = _get_shared_transcriber()
            self._initialized = bool(self._voice_analyzer)
            if self._initialized:
                logger.debug("AudioAnalysisService ready")
        except Exception as exc:
            logger.warning("AudioAnalysisService degraded — audio analysis disabled: %s", exc)

    def process_audio_chunk(self, audio_bytes: bytes, sample_rate: int = 16000) -> AudioMetrics:
        if not self._initialized or not self._voice_analyzer:
            return AudioMetrics()
        try:
            audio_i16 = np.frombuffer(audio_bytes, dtype=np.int16)
            audio_f32 = audio_i16.astype(np.float32) / 32768.0
            result = self._voice_analyzer.analyze_chunk(audio_f32)

            elapsed = time.time() - self._session_start
            words = self._transcriber.get_total_word_count() if self._transcriber else 0
            wpm = self._voice_analyzer.get_speaking_pace_wpm(words, elapsed)

            return AudioMetrics(
                timestamp=time.time(),
                pitch_mean=result.pitch_mean,
                pitch_variance=result.pitch_variance,
                speaking_pace=wpm,
                pause_ratio=result.pause_ratio,
                energy_level=result.energy_level,
                vocal_stability=result.vocal_stability,
                voice_stress_score=result.voice_stress_score,
                is_speaking=result.is_speaking,
            )
        except Exception:
            return AudioMetrics()

    def process_audio_for_transcript(self, audio_bytes: bytes):
        if not self._transcriber:
            return None
        try:
            audio_i16 = np.frombuffer(audio_bytes, dtype=np.int16)
            audio_f32 = audio_i16.astype(np.float32) / 32768.0
            return self._transcriber.add_audio(audio_f32)
        except Exception:
            return None

    def get_full_transcript(self) -> str:
        try:
            return self._transcriber.get_full_transcript() if self._transcriber else ""
        except Exception:
            return ""

    @property
    def session_filler_total(self) -> int:
        return 0

    def reset(self):
        try:
            if self._transcriber:
                self._transcriber.reset()
        except Exception:
            pass
        self._session_start = time.time()
