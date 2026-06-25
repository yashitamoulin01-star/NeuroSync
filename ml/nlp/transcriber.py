from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

_MIN_CHUNK_SECONDS = 3.0   # accumulate this many seconds before transcribing


@dataclass
class TranscriptChunk:
    text: str
    start: float = 0.0
    end: float   = 0.0
    words: List[str] = field(default_factory=list)


class WhisperTranscriber:
    def __init__(
        self,
        model_size:  str = "base",
        device:      str = "cpu",
        sample_rate: int = 16000,
    ) -> None:
        self._model_size  = model_size
        self._device      = device
        self._sr          = sample_rate
        self._model       = None
        self._loaded      = False
        self._buffer      = np.array([], dtype=np.float32)
        self._transcript: List[str] = []
        self._total_words = 0

    # ── lazy model load ───────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            from faster_whisper import WhisperModel
            compute = "int8" if self._device == "cpu" else "float16"
            self._model = WhisperModel(self._model_size, device=self._device, compute_type=compute)
            self._loaded = True
            logger.info("WhisperTranscriber loaded: %s on %s", self._model_size, self._device)
        except Exception as exc:
            logger.warning("WhisperTranscriber load failed: %s", exc)

    # ── public ────────────────────────────────────────────────────────────────

    def add_audio(self, audio_f32: np.ndarray) -> Optional[TranscriptChunk]:
        self._load()
        if not self._loaded:
            return None

        self._buffer = np.concatenate([self._buffer, audio_f32])

        min_samples = int(_MIN_CHUNK_SECONDS * self._sr)
        if len(self._buffer) < min_samples:
            return None

        chunk = self._buffer.copy()
        self._buffer = np.array([], dtype=np.float32)

        try:
            segments, _ = self._model.transcribe(chunk, language="en", beam_size=1)
            texts = [seg.text.strip() for seg in segments if seg.text.strip()]
            if not texts:
                return None

            text  = " ".join(texts)
            words = text.split()
            self._total_words += len(words)
            self._transcript.append(text)
            return TranscriptChunk(text=text, words=words)
        except Exception as exc:
            logger.debug("WhisperTranscriber.add_audio error: %s", exc)
            return None

    def get_full_transcript(self) -> str:
        return " ".join(self._transcript)

    def get_total_word_count(self) -> int:
        return self._total_words

    def reset(self) -> None:
        self._buffer      = np.array([], dtype=np.float32)
        self._transcript  = []
        self._total_words = 0
