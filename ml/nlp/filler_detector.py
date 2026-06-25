from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List

import numpy as np

logger = logging.getLogger(__name__)

# ── Word lists ─────────────────────────────────────────────────────────────────

_FILLERS: list[str] = [
    "um", "uh", "er", "ah", "hmm",
    "you know", "i mean", "sort of", "kind of",
    "basically", "literally", "actually", "honestly",
    "right", "okay", "like", "well", "anyway",
    "you see", "so yeah",
]

_CONFIDENCE_WORDS: set[str] = {
    "definitely", "certainly", "absolutely", "clearly", "obviously",
    "confident", "sure", "positive", "strong", "effective",
    "demonstrate", "achieve", "succeed", "lead", "drive",
    "commit", "deliver", "proven", "capable", "excellent",
}

_HEDGE_WORDS: set[str] = {
    "maybe", "perhaps", "possibly", "might", "could",
    "sort of", "kind of", "i think", "i guess", "i suppose",
    "not sure", "uncertain", "unclear", "difficult", "try",
    "attempt", "hope", "wish", "probably",
}

_POSITIVE_WORDS: set[str] = {
    "great", "good", "excellent", "positive", "happy",
    "success", "love", "best", "wonderful", "fantastic",
    "achieve", "proud", "excited", "motivated",
}

_NEGATIVE_WORDS: set[str] = {
    "bad", "fail", "wrong", "hate", "terrible",
    "awful", "worst", "problem", "issue", "difficult",
    "struggle", "worried", "anxious", "frustrated",
}


@dataclass
class FillerEvent:
    word: str
    timestamp: float
    start_char: int


@dataclass
class FillerAnalysisResult:
    filler_events: List[FillerEvent] = field(default_factory=list)
    filler_count: int = 0
    confidence_language_score: float = 0.5
    hesitation_score: float = 0.0
    clarity_score: float = 0.5
    sentiment_polarity: float = 0.0
    word_count: int = 0


class FillerWordDetector:
    def __init__(self) -> None:
        self._session_total = 0
        # Pre-compile patterns sorted longest-first to match multi-word fillers first
        self._patterns = [
            (w, re.compile(r'(?<!\w)' + re.escape(w) + r'(?!\w)', re.IGNORECASE))
            for w in sorted(_FILLERS, key=len, reverse=True)
        ]

    # ── public ────────────────────────────────────────────────────────────────

    def analyze(self, text: str, chunk_duration: float = 2.0) -> FillerAnalysisResult:
        if not text or not text.strip():
            return FillerAnalysisResult()

        word_count = len(text.split())
        text_lower = text.lower()
        total_chars = max(len(text), 1)

        # ── Filler events ─────────────────────────────────────────────────────
        events: List[FillerEvent] = []
        covered = set()   # char ranges already matched (avoid double-counting)
        for word, pat in self._patterns:
            for m in pat.finditer(text):
                span = range(m.start(), m.end())
                if any(c in covered for c in span):
                    continue
                covered.update(span)
                ts = (m.start() / total_chars) * chunk_duration
                events.append(FillerEvent(word=word, timestamp=round(ts, 3), start_char=m.start()))

        events.sort(key=lambda e: e.start_char)
        filler_count = len(events)
        self._session_total += filler_count

        # ── Scoring ───────────────────────────────────────────────────────────
        filler_ratio = filler_count / max(word_count, 1)

        conf_hits  = sum(1 for w in _CONFIDENCE_WORDS if w in text_lower)
        hedge_hits = sum(1 for w in _HEDGE_WORDS      if w in text_lower)

        confidence_score = float(np.clip(
            0.5 + conf_hits * 0.08 - hedge_hits * 0.07 - filler_ratio * 0.4,
            0.0, 1.0,
        ))
        hesitation_score = float(np.clip(
            filler_ratio * 2.5 + hedge_hits * 0.06,
            0.0, 1.0,
        ))
        clarity_score = float(np.clip(1.0 - filler_ratio * 1.8, 0.0, 1.0))

        pos = sum(1 for w in _POSITIVE_WORDS if w in text_lower)
        neg = sum(1 for w in _NEGATIVE_WORDS if w in text_lower)
        sentiment = float(np.clip((pos - neg) / max(word_count * 0.2, 1), -1.0, 1.0))

        return FillerAnalysisResult(
            filler_events=events,
            filler_count=filler_count,
            confidence_language_score=round(confidence_score, 4),
            hesitation_score=round(hesitation_score, 4),
            clarity_score=round(clarity_score, 4),
            sentiment_polarity=round(sentiment, 4),
            word_count=word_count,
        )

    @property
    def session_filler_total(self) -> int:
        return self._session_total

    def reset(self) -> None:
        self._session_total = 0
