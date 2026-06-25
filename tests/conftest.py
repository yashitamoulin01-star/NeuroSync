"""
Shared pytest fixtures for all NeuroSync backend tests.
"""

from __future__ import annotations

import pytest

from backend.models.evidence import (
    BehavioralEvidence,
    EvidenceDimension,
    EvidencePolarity,
    ModalityQuality,
    PredictionReliability,
)


@pytest.fixture
def full_quality() -> ModalityQuality:
    return ModalityQuality(
        face_available=True,  face_quality=0.85,
        audio_available=True, audio_quality=0.80,
        nlp_available=True,   nlp_quality=0.75,
        transcript_words=60,  evidence_coverage=0.90,
    )


@pytest.fixture
def minimal_quality() -> ModalityQuality:
    return ModalityQuality(
        face_available=True,   face_quality=0.50,
        audio_available=False, audio_quality=0.0,
        nlp_available=False,   nlp_quality=0.0,
        transcript_words=0,    evidence_coverage=0.30,
    )


@pytest.fixture
def positive_evidence_set() -> list:
    return [
        BehavioralEvidence(
            id=f"ev{i}",
            dimension=dim,
            polarity=EvidencePolarity.POSITIVE,
            description=f"positive {dim.value} signal",
            source_modalities=["face"],
            contribution=0.25,
        )
        for i, dim in enumerate(EvidenceDimension)
    ]


@pytest.fixture
def mixed_evidence_set() -> list:
    items = []
    for i, dim in enumerate(EvidenceDimension):
        polarity = EvidencePolarity.POSITIVE if i % 2 == 0 else EvidencePolarity.NEGATIVE
        items.append(BehavioralEvidence(
            id=f"ev{i}",
            dimension=dim,
            polarity=polarity,
            description=f"mixed {dim.value} signal",
            source_modalities=["face" if i % 3 == 0 else "audio"],
            contribution=0.20,
        ))
    return items
