"""
Evidence extractors — convert raw window-averaged metrics into BehavioralEvidence items.

Design rules:
  - Never emit evidence for a modality that is unavailable or returned zero-quality data.
  - Each extractor is independent. Missing modalities produce empty lists, not defaults.
  - Cross-modal evidence requires both source modalities to be present.
  - contribution is a pull factor [0–1] applied asymptotically by the reasoner.
"""

from typing import List, Optional

from backend.models.evidence import BehavioralEvidence, EvidencePolarity, EvidenceDimension
from backend.models.schemas import FaceMetrics, AudioMetrics, NLPMetrics


def extract_face_evidence(face: Optional[FaceMetrics]) -> List[BehavioralEvidence]:
    if not face or not face.face_detected:
        return []

    items: List[BehavioralEvidence] = []
    ts = face.timestamp

    # ── Eye contact → Confidence ──────────────────────────────────────────────
    if face.eye_contact_score >= 0.65:
        items.append(BehavioralEvidence(
            id="face.eye_contact.sustained",
            dimension=EvidenceDimension.CONFIDENCE,
            polarity=EvidencePolarity.POSITIVE,
            description=f"Sustained eye contact ({face.eye_contact_score:.0%})",
            measurement=face.eye_contact_score,
            source_modalities=["face"],
            timestamp=ts,
            contribution=face.eye_contact_score * 0.42,
        ))
    elif face.eye_contact_score < 0.35:
        items.append(BehavioralEvidence(
            id="face.eye_contact.reduced",
            dimension=EvidenceDimension.CONFIDENCE,
            polarity=EvidencePolarity.NEGATIVE,
            description=f"Reduced eye contact ({face.eye_contact_score:.0%})",
            measurement=face.eye_contact_score,
            source_modalities=["face"],
            timestamp=ts,
            contribution=(1.0 - face.eye_contact_score) * 0.42,
        ))

    # ── Eye contact → Engagement ──────────────────────────────────────────────
    if face.eye_contact_score >= 0.50:
        items.append(BehavioralEvidence(
            id="face.eye_contact.engagement",
            dimension=EvidenceDimension.ENGAGEMENT,
            polarity=EvidencePolarity.POSITIVE,
            description="Visual engagement maintained",
            measurement=face.eye_contact_score,
            source_modalities=["face"],
            timestamp=ts,
            contribution=face.eye_contact_score * 0.30,
        ))
    elif face.eye_contact_score < 0.25:
        items.append(BehavioralEvidence(
            id="face.eye_contact.disengaged",
            dimension=EvidenceDimension.ENGAGEMENT,
            polarity=EvidencePolarity.NEGATIVE,
            description="Low visual engagement",
            measurement=face.eye_contact_score,
            source_modalities=["face"],
            timestamp=ts,
            contribution=(1.0 - face.eye_contact_score) * 0.30,
        ))

    # ── Head stability → Consistency ─────────────────────────────────────────
    if face.head_stability >= 0.65:
        items.append(BehavioralEvidence(
            id="face.head_stability.stable",
            dimension=EvidenceDimension.CONSISTENCY,
            polarity=EvidencePolarity.POSITIVE,
            description="Stable head position throughout window",
            measurement=face.head_stability,
            source_modalities=["face"],
            timestamp=ts,
            contribution=face.head_stability * 0.25,
        ))
    elif face.head_stability < 0.35:
        items.append(BehavioralEvidence(
            id="face.head_stability.unstable",
            dimension=EvidenceDimension.CONSISTENCY,
            polarity=EvidencePolarity.NEGATIVE,
            description="Unstable head movement detected",
            measurement=face.head_stability,
            source_modalities=["face"],
            timestamp=ts,
            contribution=(1.0 - face.head_stability) * 0.25,
        ))

    # ── Facial tension → Stress ───────────────────────────────────────────────
    if face.facial_tension >= 0.60:
        items.append(BehavioralEvidence(
            id="face.facial_tension.elevated",
            dimension=EvidenceDimension.STRESS,
            polarity=EvidencePolarity.NEGATIVE,
            description=f"Elevated facial tension ({face.facial_tension:.0%})",
            measurement=face.facial_tension,
            source_modalities=["face"],
            timestamp=ts,
            contribution=face.facial_tension * 0.28,
        ))
    elif face.facial_tension < 0.28:
        items.append(BehavioralEvidence(
            id="face.facial_tension.relaxed",
            dimension=EvidenceDimension.STRESS,
            polarity=EvidencePolarity.POSITIVE,
            description="Relaxed facial expression",
            measurement=face.facial_tension,
            source_modalities=["face"],
            timestamp=ts,
            contribution=(1.0 - face.facial_tension) * 0.28,
        ))

    # ── Elevated blink rate → Stress (above 25 bpm is clinically elevated) ───
    if face.blink_rate > 25:
        severity = min((face.blink_rate - 25) / 20.0, 1.0)
        items.append(BehavioralEvidence(
            id="face.blink_rate.elevated",
            dimension=EvidenceDimension.STRESS,
            polarity=EvidencePolarity.NEGATIVE,
            description=f"Elevated blink rate ({face.blink_rate:.0f} bpm)",
            measurement=face.blink_rate,
            source_modalities=["face"],
            timestamp=ts,
            contribution=severity * 0.14,
        ))

    return items


def extract_audio_evidence(audio: Optional[AudioMetrics]) -> List[BehavioralEvidence]:
    if not audio or not audio.is_speaking:
        return []

    items: List[BehavioralEvidence] = []
    ts = audio.timestamp

    # ── Vocal stability → Confidence ──────────────────────────────────────────
    if audio.vocal_stability >= 0.65:
        items.append(BehavioralEvidence(
            id="audio.vocal_stability.stable",
            dimension=EvidenceDimension.CONFIDENCE,
            polarity=EvidencePolarity.POSITIVE,
            description="Stable vocal delivery",
            measurement=audio.vocal_stability,
            source_modalities=["audio"],
            timestamp=ts,
            contribution=audio.vocal_stability * 0.38,
        ))
    elif audio.vocal_stability < 0.35:
        items.append(BehavioralEvidence(
            id="audio.vocal_stability.unstable",
            dimension=EvidenceDimension.CONFIDENCE,
            polarity=EvidencePolarity.NEGATIVE,
            description="Unstable voice — pitch or energy fluctuations",
            measurement=audio.vocal_stability,
            source_modalities=["audio"],
            timestamp=ts,
            contribution=(1.0 - audio.vocal_stability) * 0.38,
        ))

    # ── Voice stress → Stress ────────────────────────────────────────────────
    if audio.voice_stress_score >= 0.65:
        items.append(BehavioralEvidence(
            id="audio.voice_stress.elevated",
            dimension=EvidenceDimension.STRESS,
            polarity=EvidencePolarity.NEGATIVE,
            description=f"Elevated vocal stress ({audio.voice_stress_score:.0%})",
            measurement=audio.voice_stress_score,
            source_modalities=["audio"],
            timestamp=ts,
            contribution=audio.voice_stress_score * 0.55,
        ))
    elif audio.voice_stress_score < 0.25:
        items.append(BehavioralEvidence(
            id="audio.voice_stress.calm",
            dimension=EvidenceDimension.STRESS,
            polarity=EvidencePolarity.POSITIVE,
            description="Calm vocal tone — minimal stress markers",
            measurement=audio.voice_stress_score,
            source_modalities=["audio"],
            timestamp=ts,
            contribution=(1.0 - audio.voice_stress_score) * 0.55,
        ))

    # ── Energy level → Engagement ────────────────────────────────────────────
    if audio.energy_level >= 0.50:
        items.append(BehavioralEvidence(
            id="audio.energy.strong",
            dimension=EvidenceDimension.ENGAGEMENT,
            polarity=EvidencePolarity.POSITIVE,
            description="Strong vocal energy",
            measurement=audio.energy_level,
            source_modalities=["audio"],
            timestamp=ts,
            contribution=audio.energy_level * 0.45,
        ))
    elif audio.energy_level < 0.20:
        items.append(BehavioralEvidence(
            id="audio.energy.low",
            dimension=EvidenceDimension.ENGAGEMENT,
            polarity=EvidencePolarity.NEGATIVE,
            description="Low vocal energy",
            measurement=audio.energy_level,
            source_modalities=["audio"],
            timestamp=ts,
            contribution=(1.0 - audio.energy_level) * 0.45,
        ))

    # ── Pause ratio → Communication ──────────────────────────────────────────
    if audio.pause_ratio >= 0.45:
        items.append(BehavioralEvidence(
            id="audio.pause_ratio.high",
            dimension=EvidenceDimension.COMMUNICATION,
            polarity=EvidencePolarity.NEGATIVE,
            description=f"High pause ratio ({audio.pause_ratio:.0%} silence in window)",
            measurement=audio.pause_ratio,
            source_modalities=["audio"],
            timestamp=ts,
            contribution=(audio.pause_ratio - 0.45) * 0.55,
        ))

    return items


def extract_nlp_evidence(nlp: Optional[NLPMetrics]) -> List[BehavioralEvidence]:
    if not nlp or not nlp.transcript_chunk.strip():
        return []

    items: List[BehavioralEvidence] = []
    ts = nlp.timestamp

    # ── Confidence language → Confidence ─────────────────────────────────────
    if nlp.confidence_language_score >= 0.65:
        items.append(BehavioralEvidence(
            id="nlp.confidence_language.high",
            dimension=EvidenceDimension.CONFIDENCE,
            polarity=EvidencePolarity.POSITIVE,
            description="Confident language patterns",
            measurement=nlp.confidence_language_score,
            source_modalities=["nlp"],
            timestamp=ts,
            contribution=nlp.confidence_language_score * 0.50,
        ))
    elif nlp.confidence_language_score < 0.40:
        items.append(BehavioralEvidence(
            id="nlp.confidence_language.low",
            dimension=EvidenceDimension.CONFIDENCE,
            polarity=EvidencePolarity.NEGATIVE,
            description="Uncertain language patterns",
            measurement=nlp.confidence_language_score,
            source_modalities=["nlp"],
            timestamp=ts,
            contribution=(1.0 - nlp.confidence_language_score) * 0.50,
        ))

    # ── Hesitation → Communication + Stress ──────────────────────────────────
    if nlp.hesitation_score >= 0.52:
        items.append(BehavioralEvidence(
            id="nlp.hesitation.communication",
            dimension=EvidenceDimension.COMMUNICATION,
            polarity=EvidencePolarity.NEGATIVE,
            description="Hesitation pattern detected in speech",
            measurement=nlp.hesitation_score,
            source_modalities=["nlp"],
            timestamp=ts,
            contribution=nlp.hesitation_score * 0.40,
        ))
        items.append(BehavioralEvidence(
            id="nlp.hesitation.stress",
            dimension=EvidenceDimension.STRESS,
            polarity=EvidencePolarity.NEGATIVE,
            description="Speech hesitation — possible cognitive load or stress",
            measurement=nlp.hesitation_score,
            source_modalities=["nlp"],
            timestamp=ts,
            contribution=nlp.hesitation_score * 0.28,
        ))

    # ── Clarity → Communication ───────────────────────────────────────────────
    if nlp.clarity_score >= 0.65:
        items.append(BehavioralEvidence(
            id="nlp.clarity.high",
            dimension=EvidenceDimension.COMMUNICATION,
            polarity=EvidencePolarity.POSITIVE,
            description="Clear sentence structure and articulation",
            measurement=nlp.clarity_score,
            source_modalities=["nlp"],
            timestamp=ts,
            contribution=nlp.clarity_score * 0.48,
        ))
    elif nlp.clarity_score < 0.40:
        items.append(BehavioralEvidence(
            id="nlp.clarity.low",
            dimension=EvidenceDimension.COMMUNICATION,
            polarity=EvidencePolarity.NEGATIVE,
            description="Unclear sentence structure",
            measurement=nlp.clarity_score,
            source_modalities=["nlp"],
            timestamp=ts,
            contribution=(1.0 - nlp.clarity_score) * 0.48,
        ))

    # ── Filler words → Communication ──────────────────────────────────────────
    if nlp.filler_word_count >= 3:
        items.append(BehavioralEvidence(
            id="nlp.filler_words.multiple",
            dimension=EvidenceDimension.COMMUNICATION,
            polarity=EvidencePolarity.NEGATIVE,
            description=f"{nlp.filler_word_count} filler word(s) in this segment",
            measurement=float(nlp.filler_word_count),
            source_modalities=["nlp"],
            timestamp=ts,
            contribution=min(nlp.filler_word_count / 12.0, 0.35),
        ))
    elif nlp.filler_word_count == 0 and nlp.words_per_chunk >= 6:
        items.append(BehavioralEvidence(
            id="nlp.filler_words.none",
            dimension=EvidenceDimension.COMMUNICATION,
            polarity=EvidencePolarity.POSITIVE,
            description="No filler words — clean, deliberate delivery",
            measurement=0.0,
            source_modalities=["nlp"],
            timestamp=ts,
            contribution=0.12,
        ))

    return items


def extract_cross_modal_evidence(
    face: Optional[FaceMetrics],
    audio: Optional[AudioMetrics],
    nlp: Optional[NLPMetrics],
) -> List[BehavioralEvidence]:
    """
    Cross-modal corroboration — only fires when both source modalities are active.
    A two-modality observation carries more weight than either alone.
    """
    items: List[BehavioralEvidence] = []

    face_active  = face  is not None and face.face_detected
    audio_active = audio is not None and audio.is_speaking
    nlp_active   = nlp   is not None and bool(nlp.transcript_chunk.strip())

    # Corroborated stress: facial tension + vocal stress both elevated
    if face_active and audio_active:
        if face.facial_tension > 0.55 and audio.voice_stress_score > 0.55:
            compound = (face.facial_tension + audio.voice_stress_score) / 2.0
            items.append(BehavioralEvidence(
                id="cross.stress.face_audio",
                dimension=EvidenceDimension.STRESS,
                polarity=EvidencePolarity.NEGATIVE,
                description=(
                    f"Two-modality stress corroboration — "
                    f"facial tension {face.facial_tension:.0%} · "
                    f"vocal stress {audio.voice_stress_score:.0%}"
                ),
                measurement=compound,
                source_modalities=["face", "audio"],
                contribution=compound * 0.22,
            ))

        # Behavioral consistency: calm voice but tense face (or vice versa)
        if face.facial_tension > 0.60 and audio.voice_stress_score < 0.30:
            items.append(BehavioralEvidence(
                id="cross.consistency.face_audio_mismatch",
                dimension=EvidenceDimension.CONSISTENCY,
                polarity=EvidencePolarity.NEGATIVE,
                description=(
                    "Behavioral mismatch — controlled voice tone with elevated facial tension"
                ),
                measurement=(face.facial_tension + (1.0 - audio.voice_stress_score)) / 2.0,
                source_modalities=["face", "audio"],
                contribution=0.22,
            ))

    # Corroborated confidence: strong eye contact + confident language
    if face_active and nlp_active:
        if face.eye_contact_score > 0.62 and nlp.confidence_language_score > 0.60:
            compound = (face.eye_contact_score + nlp.confidence_language_score) / 2.0
            items.append(BehavioralEvidence(
                id="cross.confidence.face_nlp",
                dimension=EvidenceDimension.CONFIDENCE,
                polarity=EvidencePolarity.POSITIVE,
                description=(
                    f"Two-modality confidence signal — "
                    f"eye contact {face.eye_contact_score:.0%} · "
                    f"language confidence {nlp.confidence_language_score:.0%}"
                ),
                measurement=compound,
                source_modalities=["face", "nlp"],
                contribution=compound * 0.18,
            ))

    # Corroborated engagement: vocal energy + eye contact both strong
    if face_active and audio_active:
        if face.eye_contact_score > 0.60 and audio.energy_level > 0.50:
            compound = (face.eye_contact_score + audio.energy_level) / 2.0
            items.append(BehavioralEvidence(
                id="cross.engagement.face_audio",
                dimension=EvidenceDimension.ENGAGEMENT,
                polarity=EvidencePolarity.POSITIVE,
                description="Strong presence — eye contact and vocal energy both elevated",
                measurement=compound,
                source_modalities=["face", "audio"],
                contribution=compound * 0.15,
            ))

    return items
