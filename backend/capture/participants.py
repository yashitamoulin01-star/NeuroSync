"""
Participant & speaker attribution (Volume 2B §Participant/Speaker, Volume 4
§Interview Fairness Engine).

Panel interviews have N interviewers + 1 candidate. Reports must read
"Candidate / Interviewer 1/2/3", never "Person A/B". This is a NORMALIZATION-layer
concern: it labels the stream before the MBA engine sees it, so the AI stays
agnostic about who is in the room.

Input is speaker-attributed segments (from diarization in production; the tracker
is agnostic to how segments are produced). Output is role-labeled participants
plus interview balance/fairness metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ParticipantRole(str, Enum):
    CANDIDATE   = "candidate"
    INTERVIEWER = "interviewer"
    OBSERVER    = "observer"
    MODERATOR   = "moderator"
    UNKNOWN     = "unknown"


@dataclass
class Participant:
    speaker_id:   str
    display_name: str
    role:         ParticipantRole = ParticipantRole.UNKNOWN

    def to_dict(self) -> dict:
        return {"speaker_id": self.speaker_id, "display_name": self.display_name, "role": self.role.value}


@dataclass
class SpeakerSegment:
    speaker_id: str
    start:      float   # seconds since session start
    end:        float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class SpeakerTracker:
    """Accumulates speaker segments and derives role labels + fairness metrics."""
    participants: Dict[str, Participant] = field(default_factory=dict)
    segments:     List[SpeakerSegment]   = field(default_factory=list)

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def register(self, speaker_id: str, display_name: str = "") -> Participant:
        if speaker_id not in self.participants:
            self.participants[speaker_id] = Participant(
                speaker_id=speaker_id, display_name=display_name or speaker_id
            )
        return self.participants[speaker_id]

    def add_segment(self, speaker_id: str, start: float, end: float) -> None:
        self.register(speaker_id)
        self.segments.append(SpeakerSegment(speaker_id=speaker_id, start=start, end=end))

    # ── Derived stats ─────────────────────────────────────────────────────────

    def _talk_time(self) -> Dict[str, float]:
        totals: Dict[str, float] = {sid: 0.0 for sid in self.participants}
        for seg in self.segments:
            totals[seg.speaker_id] = totals.get(seg.speaker_id, 0.0) + seg.duration
        return totals

    def _interruptions(self) -> Dict[str, int]:
        """An interruption = speaker B starts before speaker A's segment ends."""
        counts: Dict[str, int] = {sid: 0 for sid in self.participants}
        ordered = sorted(self.segments, key=lambda s: s.start)
        for i in range(1, len(ordered)):
            prev, cur = ordered[i - 1], ordered[i]
            if cur.speaker_id != prev.speaker_id and cur.start < prev.end:
                counts[cur.speaker_id] = counts.get(cur.speaker_id, 0) + 1
        return counts

    def assign_roles(self, candidate_id: Optional[str] = None) -> None:
        """
        Label participants. Heuristic when candidate isn't given: the speaker with
        the most total talk time is the Candidate (candidates answer at length);
        remaining speakers become Interviewer 1..N by first-speech order. An
        explicit candidate_id always wins.
        """
        if not self.participants:
            return
        talk = self._talk_time()
        if candidate_id is None and talk:
            candidate_id = max(talk, key=lambda sid: talk[sid])

        first_speech: Dict[str, float] = {}
        for seg in sorted(self.segments, key=lambda s: s.start):
            first_speech.setdefault(seg.speaker_id, seg.start)

        interviewers = sorted(
            (sid for sid in self.participants if sid != candidate_id),
            key=lambda sid: first_speech.get(sid, float("inf")),
        )
        for sid, p in self.participants.items():
            if sid == candidate_id:
                p.role = ParticipantRole.CANDIDATE
                p.display_name = "Candidate"
        for idx, sid in enumerate(interviewers, start=1):
            p = self.participants[sid]
            p.role = ParticipantRole.INTERVIEWER
            p.display_name = f"Interviewer {idx}"

    # ── Fairness / balance summary ────────────────────────────────────────────

    def attribution_summary(self) -> dict:
        talk = self._talk_time()
        total = sum(talk.values()) or 1.0
        interruptions = self._interruptions()

        candidate_pct = sum(
            talk[sid] for sid, p in self.participants.items() if p.role == ParticipantRole.CANDIDATE
        ) / total * 100.0
        interviewer_pct = sum(
            talk[sid] for sid, p in self.participants.items() if p.role == ParticipantRole.INTERVIEWER
        ) / total * 100.0

        # Balance: how close candidate talk time is to a healthy interview share
        # (candidates ideally hold the majority of speaking time, ~60–75%).
        balance = max(0.0, 1.0 - abs(candidate_pct - 67.5) / 67.5)

        return {
            "participants": [p.to_dict() for p in self.participants.values()],
            "talk_time_seconds": {sid: round(t, 1) for sid, t in talk.items()},
            "candidate_speaking_pct":   round(candidate_pct, 1),
            "interviewer_speaking_pct": round(interviewer_pct, 1),
            "interruptions": interruptions,
            "total_interruptions": sum(interruptions.values()),
            "balance_score": round(balance, 3),
        }
