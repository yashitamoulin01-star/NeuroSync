"""
Audio analysis service — wraps voice analyzer and transcriber.
Handles raw PCM audio chunks sent via WebSocket.
"""

import numpy as np
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ml.audio.voice_analyzer import VoiceAnalyzer
from ml.nlp.transcriber import WhisperTranscriber
from backend.models.schemas import AudioMetrics
from backend.core.config import settings


class AudioAnalysisService:
    def __init__(self):
        self._voice_analyzer = VoiceAnalyzer(sample_rate=settings.AUDIO_SAMPLE_RATE)
        self._transcriber = WhisperTranscriber(
            model_size=settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            sample_rate=settings.AUDIO_SAMPLE_RATE,
        )
        self._session_start: float = time.time()

    def process_audio_chunk(self, audio_bytes: bytes, sample_rate: int = 16000) -> AudioMetrics:
        """Process raw PCM int16 bytes and return audio metrics."""
        try:
            audio_i16 = np.frombuffer(audio_bytes, dtype=np.int16)
            audio_f32 = audio_i16.astype(np.float32) / 32768.0
            result = self._voice_analyzer.analyze_chunk(audio_f32)

            # Compute wpm from session word count and elapsed time
            elapsed = time.time() - self._session_start
            words = self._transcriber.get_total_word_count()
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
        """Add audio to Whisper buffer; returns TranscriptChunk or None."""
        try:
            audio_i16 = np.frombuffer(audio_bytes, dtype=np.int16)
            audio_f32 = audio_i16.astype(np.float32) / 32768.0
            return self._transcriber.add_audio(audio_f32)
        except Exception:
            return None

    def get_full_transcript(self) -> str:
        return self._transcriber.get_full_transcript()

    def reset(self):
        self._transcriber.reset()
        self._session_start = time.time()
