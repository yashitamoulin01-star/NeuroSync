from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

_SILENCE_ENERGY  = 0.008   # RMS below this → silence
_HISTORY_FRAMES  = 60      # rolling window length


@dataclass
class VoiceAnalysisResult:
    pitch_mean: float      = 0.0
    pitch_variance: float  = 0.0
    pause_ratio: float     = 0.0
    energy_level: float    = 0.0
    vocal_stability: float = 0.5
    voice_stress_score: float = 0.0
    is_speaking: bool      = False


class VoiceAnalyzer:
    def __init__(self, sample_rate: int = 16000) -> None:
        self._sr = sample_rate
        self._energy_buf: deque[float] = deque(maxlen=_HISTORY_FRAMES)
        self._pitch_buf:  deque[float] = deque(maxlen=_HISTORY_FRAMES)
        self._total_frames  = 0
        self._silence_frames = 0

    # ── public ────────────────────────────────────────────────────────────────

    def analyze_chunk(self, audio_f32: np.ndarray) -> VoiceAnalysisResult:
        if audio_f32 is None or len(audio_f32) == 0:
            return VoiceAnalysisResult()

        self._total_frames += 1

        # ── Energy ───────────────────────────────────────────────────────────
        rms = float(np.sqrt(np.mean(audio_f32 ** 2) + 1e-12))
        self._energy_buf.append(rms)
        is_speaking = rms > _SILENCE_ENERGY
        if not is_speaking:
            self._silence_frames += 1

        energy_level = float(np.clip(rms / 0.1, 0.0, 1.0))   # normalise to ~0-1

        # ── Pitch proxy (ZCR-based) ───────────────────────────────────────────
        zc = int(np.sum(np.diff(np.sign(audio_f32)) != 0))
        pitch_hz = float(np.clip(zc * self._sr / (2.0 * len(audio_f32)), 0.0, 600.0))
        if is_speaking:
            self._pitch_buf.append(pitch_hz)

        if len(self._pitch_buf) >= 2:
            pa = np.array(self._pitch_buf)
            pitch_mean     = float(np.mean(pa))
            pitch_variance = float(np.var(pa))
        else:
            pitch_mean = pitch_hz
            pitch_variance = 0.0

        # ── Pause ratio ───────────────────────────────────────────────────────
        pause_ratio = float(self._silence_frames / max(self._total_frames, 1))

        # ── Vocal stability (low energy variance = stable) ────────────────────
        if len(self._energy_buf) >= 2:
            ea = np.array(self._energy_buf)
            stability = float(np.clip(1.0 - np.std(ea) / (np.mean(ea) + 1e-6), 0.0, 1.0))
        else:
            stability = 0.5

        # ── Voice stress (high ZCR variance + high pause + low energy) ────────
        norm_pitch_var = float(np.clip(pitch_variance / 15000.0, 0.0, 1.0))
        stress = float(np.clip(
            norm_pitch_var * 0.4 + pause_ratio * 0.3 + (1.0 - stability) * 0.3,
            0.0, 1.0,
        ))

        return VoiceAnalysisResult(
            pitch_mean=round(pitch_mean, 2),
            pitch_variance=round(pitch_variance, 2),
            pause_ratio=round(pause_ratio, 4),
            energy_level=round(energy_level, 4),
            vocal_stability=round(stability, 4),
            voice_stress_score=round(stress, 4),
            is_speaking=is_speaking,
        )

    def get_speaking_pace_wpm(self, total_words: int, elapsed_seconds: float) -> float:
        if elapsed_seconds < 0.5:
            return 0.0
        return round(total_words / elapsed_seconds * 60.0, 1)
