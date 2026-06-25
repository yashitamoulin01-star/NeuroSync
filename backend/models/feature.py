"""
Feature contract — uniform output schema for every signal pipeline.

Design rules:
  - Each pipeline (vision, audio, nlp) returns a FeatureSet, never raw scores.
  - Every ObservationFeature carries its own quality and confidence.
  - No cross-pipeline references: vision doesn't know about language features.
  - The Evidence Engine is the only layer that combines features across pipelines.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List
from enum import Enum
import time


class PipelineSource(str, Enum):
    VISION = "vision"
    AUDIO  = "audio"
    NLP    = "nlp"


class ObservationFeature(BaseModel):
    """
    An atomic, measurable observation from one pipeline.

    Every feature is independently interpretable — it describes a measurement,
    not a behavioral conclusion.  Conclusions live in the Evidence Engine.
    """
    name:       str                        # e.g. "eye_contact_score", "vocal_stability"
    value:      float = 0.0               # numeric reading
    label:      str   = ""                # categorical / string reading (if applicable)
    unit:       str   = "score"           # "score" | "bpm" | "wpm" | "°" | "%" | "bool"
    confidence: float = 1.0              # measurement reliability [0-1]
    quality:    float = 1.0              # signal quality for this feature [0-1]
    timestamp:  float = Field(default_factory=time.time)
    source:     PipelineSource = PipelineSource.VISION
    metadata:   Dict[str, Any] = Field(default_factory=dict)


class FeatureSet(BaseModel):
    """
    The complete structured output of one pipeline for one time window.

    pipeline_quality summarises the overall signal quality for this window.
    A value < 0.3 means the pipeline could not produce reliable observations
    and downstream consumers should treat results with low confidence.
    """
    source:           PipelineSource
    features:         List[ObservationFeature] = Field(default_factory=list)
    pipeline_quality: float = 0.0              # 0 = no signal, 1 = perfect signal
    timestamp:        float = Field(default_factory=time.time)
    window_seconds:   float = 0.5
    sample_count:     int   = 1                # frames / chunks contributing to this set

    def get(self, name: str) -> ObservationFeature | None:
        """Convenience accessor by feature name."""
        return next((f for f in self.features if f.name == name), None)

    def value(self, name: str, default: float = 0.0) -> float:
        f = self.get(name)
        return f.value if f is not None else default
