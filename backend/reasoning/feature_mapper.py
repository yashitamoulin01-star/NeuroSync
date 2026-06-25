"""
Feature mapper — converts per-modality metric objects into typed FeatureSets.

Each pipeline returns its own FeatureSet.  The mapper is a pure function:
it describes measurements, never conclusions.  No scores, no recommendations.

Confidence values are conservative estimates based on known MediaPipe / voice
analysis reliability characteristics.  They are not runtime-computed.
"""

import time
from typing import Optional

from backend.models.feature import FeatureSet, ObservationFeature, PipelineSource
from backend.models.schemas import AudioMetrics, FaceMetrics, NLPMetrics


def face_metrics_to_feature_set(metrics: Optional[FaceMetrics]) -> FeatureSet:
    """
    Vision pipeline output.

    No confidence, stress, or behavioral conclusions.
    Only geometric and physiological measurements from face mesh landmarks.
    """
    if metrics is None or not metrics.face_detected:
        return FeatureSet(
            source=PipelineSource.VISION,
            pipeline_quality=0.0,
            timestamp=time.time(),
        )

    ts = metrics.timestamp
    features = [
        ObservationFeature(
            name="eye_contact_score",
            value=metrics.eye_contact_score,
            unit="score",
            confidence=0.88,   # MediaPipe iris tracking is reliable under normal lighting
            quality=metrics.eye_contact_score,
            timestamp=ts,
            source=PipelineSource.VISION,
        ),
        ObservationFeature(
            name="gaze_direction",
            value=0.0,
            label=metrics.gaze_direction,
            unit="label",
            confidence=0.85,
            quality=0.9,
            timestamp=ts,
            source=PipelineSource.VISION,
        ),
        ObservationFeature(
            name="blink_rate",
            value=metrics.blink_rate,
            unit="bpm",
            confidence=0.80,   # blink detection can miss rapid blinks
            quality=0.85,
            timestamp=ts,
            source=PipelineSource.VISION,
            metadata={"normal_range_bpm": "10-25"},
        ),
        ObservationFeature(
            name="head_stability",
            value=metrics.head_stability,
            unit="score",
            confidence=0.92,
            quality=metrics.head_stability,
            timestamp=ts,
            source=PipelineSource.VISION,
        ),
        ObservationFeature(
            name="facial_tension",
            value=metrics.facial_tension,
            unit="score",
            confidence=0.75,   # expression inference has moderate reliability
            quality=0.80,
            timestamp=ts,
            source=PipelineSource.VISION,
            metadata={"expression_label": metrics.expression_label},
        ),
        ObservationFeature(
            name="face_visibility",
            value=1.0 if metrics.face_detected else 0.0,
            label="visible" if metrics.face_detected else "not_detected",
            unit="bool",
            confidence=0.99,   # presence/absence detection is near-certain
            quality=1.0,
            timestamp=ts,
            source=PipelineSource.VISION,
        ),
    ]

    # Pipeline quality: weighted average of the key quality indicators
    pipeline_quality = (
        metrics.eye_contact_score * 0.40 +
        metrics.head_stability    * 0.35 +
        (1.0 - metrics.facial_tension * 0.5) * 0.25  # low tension → better signal quality
    )

    return FeatureSet(
        source=PipelineSource.VISION,
        features=features,
        pipeline_quality=round(min(max(pipeline_quality, 0.0), 1.0), 3),
        timestamp=ts,
        window_seconds=0.5,
        sample_count=1,
    )


def audio_metrics_to_feature_set(metrics: Optional[AudioMetrics]) -> FeatureSet:
    """
    Audio pipeline output.

    Prosody extraction only.  No stress score interpretation.
    """
    if metrics is None or not metrics.is_speaking:
        return FeatureSet(
            source=PipelineSource.AUDIO,
            pipeline_quality=0.0,
            timestamp=time.time(),
        )

    ts = metrics.timestamp
    features = [
        ObservationFeature(
            name="speaking_pace",
            value=metrics.speaking_pace,
            unit="wpm",
            confidence=0.82,
            quality=0.85,
            timestamp=ts,
            source=PipelineSource.AUDIO,
            metadata={"normal_range_wpm": "120-180"},
        ),
        ObservationFeature(
            name="pitch_mean",
            value=metrics.pitch_mean,
            unit="hz",
            confidence=0.85,
            quality=min(metrics.energy_level * 2.0, 1.0),   # low energy → pitch unreliable
            timestamp=ts,
            source=PipelineSource.AUDIO,
        ),
        ObservationFeature(
            name="pitch_variance",
            value=metrics.pitch_variance,
            unit="score",
            confidence=0.80,
            quality=min(metrics.energy_level * 2.0, 1.0),
            timestamp=ts,
            source=PipelineSource.AUDIO,
        ),
        ObservationFeature(
            name="pause_ratio",
            value=metrics.pause_ratio,
            unit="%",
            confidence=0.90,
            quality=0.90,
            timestamp=ts,
            source=PipelineSource.AUDIO,
        ),
        ObservationFeature(
            name="energy_level",
            value=metrics.energy_level,
            unit="score",
            confidence=0.92,
            quality=metrics.energy_level,
            timestamp=ts,
            source=PipelineSource.AUDIO,
        ),
        ObservationFeature(
            name="vocal_stability",
            value=metrics.vocal_stability,
            unit="score",
            confidence=0.82,
            quality=metrics.vocal_stability,
            timestamp=ts,
            source=PipelineSource.AUDIO,
        ),
        ObservationFeature(
            name="voice_stress_indicators",
            value=metrics.voice_stress_score,
            unit="score",
            confidence=0.75,   # stress inference from prosody has meaningful uncertainty
            quality=metrics.energy_level,
            timestamp=ts,
            source=PipelineSource.AUDIO,
            metadata={"note": "prosodic features only; not a clinical stress measurement"},
        ),
    ]

    pipeline_quality = (
        metrics.energy_level    * 0.45 +
        metrics.vocal_stability * 0.35 +
        (1.0 - metrics.pause_ratio) * 0.20
    )

    return FeatureSet(
        source=PipelineSource.AUDIO,
        features=features,
        pipeline_quality=round(min(max(pipeline_quality, 0.0), 1.0), 3),
        timestamp=ts,
        window_seconds=0.5,
        sample_count=1,
    )


def nlp_metrics_to_feature_set(metrics: Optional[NLPMetrics]) -> FeatureSet:
    """
    NLP pipeline output.

    Sentence-level behavioral features.  No direct hiring conclusions.
    """
    if metrics is None or not metrics.transcript_chunk.strip():
        return FeatureSet(
            source=PipelineSource.NLP,
            pipeline_quality=0.0,
            timestamp=time.time(),
        )

    ts = metrics.timestamp
    word_count = max(metrics.words_per_chunk, 1)
    # Quality scales with word count — more words → more reliable language features
    word_quality = min(word_count / 15.0, 1.0)

    features = [
        ObservationFeature(
            name="language_confidence",
            value=metrics.confidence_language_score,
            unit="score",
            confidence=0.78 if word_count >= 8 else 0.55,
            quality=word_quality,
            timestamp=ts,
            source=PipelineSource.NLP,
        ),
        ObservationFeature(
            name="hesitation_level",
            value=metrics.hesitation_score,
            unit="score",
            confidence=0.82,   # rule-based + DeBERTa: reliable for common hesitation markers
            quality=word_quality,
            timestamp=ts,
            source=PipelineSource.NLP,
        ),
        ObservationFeature(
            name="clarity_score",
            value=metrics.clarity_score,
            unit="score",
            confidence=0.76,
            quality=word_quality,
            timestamp=ts,
            source=PipelineSource.NLP,
        ),
        ObservationFeature(
            name="filler_word_count",
            value=float(metrics.filler_word_count),
            unit="count",
            confidence=0.95,   # filler word detection is rule-based and highly reliable
            quality=1.0,
            timestamp=ts,
            source=PipelineSource.NLP,
        ),
        ObservationFeature(
            name="filler_rate",
            value=round(metrics.filler_word_count / word_count, 3),
            unit="ratio",
            confidence=0.95,
            quality=word_quality,
            timestamp=ts,
            source=PipelineSource.NLP,
        ),
        ObservationFeature(
            name="sentiment_polarity",
            value=metrics.sentiment_polarity,
            unit="score",           # -1 (negative) to +1 (positive)
            confidence=0.70,
            quality=word_quality,
            timestamp=ts,
            source=PipelineSource.NLP,
        ),
        ObservationFeature(
            name="word_count",
            value=float(word_count),
            unit="count",
            confidence=1.0,
            quality=1.0,
            timestamp=ts,
            source=PipelineSource.NLP,
        ),
    ]

    pipeline_quality = (
        word_quality                          * 0.50 +
        metrics.clarity_score                 * 0.30 +
        (1.0 - metrics.hesitation_score)      * 0.20
    )

    return FeatureSet(
        source=PipelineSource.NLP,
        features=features,
        pipeline_quality=round(min(max(pipeline_quality, 0.0), 1.0), 3),
        timestamp=ts,
        window_seconds=2.0,    # NLP windows are longer (Whisper chunks)
        sample_count=word_count,
    )
