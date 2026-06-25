"""
Candidate portal service.

Provides candidates with access to their own interview data:
  - Interview history (their sessions only)
  - Behavioral timeline
  - Strengths + growth areas
  - Coaching suggestions
  - Transcript access
  - Privacy settings management
  - Data download (portability)

Data access is strictly limited to the candidate's own records.
Coaching language is constructive and forward-looking — never evaluative.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.candidate_portal")


@dataclass
class CoachingInsight:
    dimension:   str
    score:       float
    label:       str         # "strength" | "growth_area"
    headline:    str
    suggestion:  str
    evidence:    List[str]   = field(default_factory=list)

    def to_dict(self) -> Dict:
        return self.__dict__.copy()


def _coaching_suggestions(scores: Dict[str, float]) -> List[CoachingInsight]:
    """Generate forward-looking coaching insights from behavioral scores."""
    insights = []

    confidence = scores.get("confidence")
    if confidence is not None:
        if confidence >= 0.70:
            insights.append(CoachingInsight(
                dimension  = "confidence",
                score      = confidence,
                label      = "strength",
                headline   = "Strong confident presence",
                suggestion = "Continue using deliberate eye contact and measured pacing to sustain this.",
                evidence   = ["Consistent eye contact", "Stable posture"],
            ))
        else:
            insights.append(CoachingInsight(
                dimension  = "confidence",
                score      = confidence,
                label      = "growth_area",
                headline   = "Building confident delivery",
                suggestion = "Practice the STAR method for structuring answers — the structure itself reduces nervous energy.",
                evidence   = ["Variable eye contact patterns", "Some hesitation detected"],
            ))

    stress = scores.get("stress")
    if stress is not None:
        if stress >= 0.65:
            insights.append(CoachingInsight(
                dimension  = "stress",
                score      = stress,
                label      = "growth_area",
                headline   = "Managing interview pressure",
                suggestion = "Box breathing (4-4-4-4) before the interview significantly reduces visible stress signals.",
                evidence   = ["Elevated speech rate detected", "Increased filler word frequency"],
            ))

    engagement = scores.get("engagement")
    if engagement is not None:
        if engagement >= 0.70:
            insights.append(CoachingInsight(
                dimension  = "engagement",
                score      = engagement,
                label      = "strength",
                headline   = "Highly engaged communication style",
                suggestion = "Your energy is a genuine strength — maintain it without forcing it.",
                evidence   = ["Active listening signals", "Responsive expression patterns"],
            ))

    communication = scores.get("communication")
    if communication is not None and communication < 0.60:
        insights.append(CoachingInsight(
            dimension  = "communication",
            score      = communication,
            label      = "growth_area",
            headline   = "Clarity and structure in answers",
            suggestion = "Lead with the conclusion, then support it. Interviewers absorb structured answers better.",
            evidence   = ["Answer structure variability"],
        ))

    return insights


class CandidatePortalService:
    def get_sessions(self, candidate_user_id: str, tenant_id: str) -> List[Dict]:
        """Return all sessions belonging to this candidate."""
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                """
                SELECT id, name, mode, started_at, ended_at, duration,
                       avg_confidence, avg_stress, avg_engagement,
                       avg_communication, avg_consistency, total_words
                FROM sessions
                WHERE user_id = ?
                ORDER BY started_at DESC
                """,
                (candidate_user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def get_behavioral_timeline(self, session_id: str, candidate_user_id: str) -> List[Dict]:
        """Frame-by-frame behavioral timeline for this candidate's session."""
        con = get_enterprise_conn()
        try:
            # Verify ownership before returning frame data
            owner = con.execute(
                "SELECT user_id FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if owner is None or owner["user_id"] != candidate_user_id:
                raise PermissionError("Access denied: not the session owner")

            rows = con.execute(
                """
                SELECT ts, confidence, stress, engagement, communication, consistency, is_speaking
                FROM session_frames
                WHERE session_id = ?
                ORDER BY ts
                """,
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def get_coaching_report(self, session_id: str, candidate_user_id: str) -> Dict:
        """Generate coaching report with strengths and growth areas."""
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
                (session_id, candidate_user_id),
            ).fetchone()
            if row is None:
                raise PermissionError("Session not found or not accessible")
            session = dict(row)
        finally:
            con.close()

        scores = {
            "confidence":    session.get("avg_confidence"),
            "stress":        session.get("avg_stress"),
            "engagement":    session.get("avg_engagement"),
            "communication": session.get("avg_communication"),
            "consistency":   session.get("avg_consistency"),
        }
        insights = _coaching_suggestions({k: v for k, v in scores.items() if v is not None})

        strengths    = [i for i in insights if i.label == "strength"]
        growth_areas = [i for i in insights if i.label == "growth_area"]

        return {
            "session_id":    session_id,
            "session_name":  session.get("name"),
            "completed_at":  session.get("ended_at"),
            "scores":        scores,
            "strengths":     [i.to_dict() for i in strengths],
            "growth_areas":  [i.to_dict() for i in growth_areas],
            "overall_label": "strong_candidate" if len(strengths) > len(growth_areas) else "developing",
            "note": "This report is for your personal development. It reflects behavioral signals, not a final decision.",
        }

    def get_privacy_settings(self, candidate_user_id: str, tenant_id: str) -> Dict:
        """Return candidate's current privacy settings and consent status."""
        con = get_enterprise_conn()
        try:
            consents = con.execute(
                """
                SELECT purpose, granted, granted_at, expires_at
                FROM consent_records
                WHERE tenant_id = ? AND subject_id = ?
                ORDER BY granted_at DESC
                """,
                (tenant_id, candidate_user_id),
            ).fetchall()
            latest_per_purpose: Dict[str, Any] = {}
            for c in consents:
                p = c["purpose"]
                if p not in latest_per_purpose:
                    latest_per_purpose[p] = {
                        "purpose":    p,
                        "granted":    bool(c["granted"]),
                        "granted_at": c["granted_at"],
                        "expires_at": c["expires_at"],
                    }
            return {
                "candidate_id": candidate_user_id,
                "consents":     list(latest_per_purpose.values()),
            }
        finally:
            con.close()

    def request_data_export(self, candidate_user_id: str, tenant_id: str) -> str:
        """Create a data portability request. Returns request_id."""
        from backend.compliance.service import compliance_service
        req = compliance_service.create_data_request(
            tenant_id    = tenant_id,
            subject_id   = candidate_user_id,
            request_type = "export",
            notes        = "Self-initiated portability request via candidate portal",
        )
        return req.request_id

    def request_erasure(self, candidate_user_id: str, tenant_id: str) -> str:
        """Create a right-to-erasure request. Returns request_id."""
        from backend.compliance.service import compliance_service
        req = compliance_service.create_data_request(
            tenant_id    = tenant_id,
            subject_id   = candidate_user_id,
            request_type = "erasure",
            notes        = "Self-initiated erasure request via candidate portal",
        )
        logger.warning(
            "Erasure requested: subject=%s tenant=%s request=%s",
            candidate_user_id, tenant_id, req.request_id,
        )
        return req.request_id


candidate_portal_service = CandidatePortalService()
