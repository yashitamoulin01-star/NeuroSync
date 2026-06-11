"""
NLP analysis service.
Phase 2: rule-based filler detection (always available).
Phase 3: DeBERTa live inference enrichment (activated when model is trained).
"""

import time
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ml.nlp.filler_detector import FillerWordDetector
from ml.nlp.behavioral_nlp import BehavioralNLPInference
from backend.models.schemas import NLPMetrics, FillerWordEvent

logger = logging.getLogger(__name__)

# Singleton — loads DeBERTa lazily on first call (won't block startup)
_behavioral_nlp = BehavioralNLPInference()


class NLPAnalysisService:
    def __init__(self):
        self._detector = FillerWordDetector()

    def analyze_transcript_chunk(self, text: str, chunk_duration: float = 2.0) -> NLPMetrics:
        if not text or not text.strip():
            return NLPMetrics()

        # Rule-based (always runs, fast)
        rule = self._detector.analyze(text, chunk_duration)

        filler_events = [
            FillerWordEvent(
                word=fe.word,
                timestamp=fe.timestamp,
                position_in_transcript=fe.start_char,
            )
            for fe in rule.filler_events
        ]

        # DeBERTa enrichment — no-op until fine-tuned model exists
        try:
            ai = _behavioral_nlp.analyze(text)
            confidence_score = ai.confidence_score
            hesitation_score = ai.hesitation_level
            clarity_score    = ai.communication_quality
        except Exception as e:
            logger.debug("DeBERTa enrichment skipped: %s", e)
            confidence_score = rule.confidence_language_score
            hesitation_score = rule.hesitation_score
            clarity_score    = rule.clarity_score

        return NLPMetrics(
            timestamp=time.time(),
            transcript_chunk=text,
            filler_word_count=rule.filler_count,
            filler_words_detected=filler_events,
            confidence_language_score=confidence_score,
            hesitation_score=hesitation_score,
            clarity_score=clarity_score,
            sentiment_polarity=rule.sentiment_polarity,
            words_per_chunk=rule.word_count,
        )

    @property
    def session_filler_total(self) -> int:
        return self._detector.session_filler_total

    @property
    def deberta_active(self) -> bool:
        return _behavioral_nlp.is_deberta_active

    def reset(self):
        self._detector.reset()
