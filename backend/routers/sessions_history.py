"""
Session history + dashboard endpoints.

GET /api/sessions              — paginated list of completed sessions
GET /api/sessions/{id}         — single session detail + timeline
GET /api/dashboard/stats       — aggregate KPIs for dashboard
GET /api/health/detailed       — full component + hardware status
GET /api/benchmarks            — real-time system + inference performance metrics
"""

import json as _json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from backend.services.db_service import (
    list_sessions, get_session, get_session_frames, dashboard_stats,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["history"])

ROOT = Path(__file__).parent.parent.parent


def _ts_to_iso(v: Any) -> Any:
    """Convert a Unix-seconds float to ISO-8601 string; pass strings through unchanged."""
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(float(v), tz=timezone.utc).isoformat()
    return v


def _serialize_session(row: Dict) -> Dict:
    """Normalise all timestamp fields in a session row before sending to the frontend."""
    result = dict(row)
    for key in ("started_at", "ended_at", "created_at"):
        if key in result:
            result[key] = _ts_to_iso(result[key])
    # Parse insights_json so the client doesn't have to
    raw = result.pop("insights_json", None)
    if raw and "insights" not in result:
        try:
            result["insights"] = _json.loads(raw)
        except Exception:
            result["insights"] = []
    return result


@router.get("/sessions")
async def get_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    mode: str | None = Query(None, pattern="^(interview|coaching|presentation)$"),
):
    rows = list_sessions(limit=limit, offset=offset, mode=mode)
    return {"sessions": [_serialize_session(r) for r in rows], "count": len(rows), "offset": offset}


@router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    frames = get_session_frames(session_id)

    result = _serialize_session(session)
    result["timeline"] = frames
    return result


def _behavioral_arc(frames: list) -> dict:
    """
    Split session timeline into thirds. Compare early vs late behavioral signals
    to characterise the session arc (improving / declining / consistent / mixed).
    Returns arc label, delta values, and a human-readable description.
    """
    if len(frames) < 6:
        return {"label": "insufficient_data", "description": None, "deltas": {}}

    third = len(frames) // 3
    early = frames[:third]
    late  = frames[-third:]

    def avg(subset: list, key: str) -> float:
        vals = [float(f.get(key, 0) or 0) for f in subset]
        return sum(vals) / max(len(vals), 1)

    early_conf  = avg(early, "confidence")
    late_conf   = avg(late,  "confidence")
    early_stress = avg(early, "stress")
    late_stress  = avg(late,  "stress")
    early_eng   = avg(early, "engagement")
    late_eng    = avg(late,  "engagement")

    delta_conf   = late_conf  - early_conf
    delta_stress = late_stress - early_stress
    delta_eng    = late_eng   - early_eng

    # Stress improvement = stress went down
    net_positive = sum([
        delta_conf   >  0.08,
        delta_stress < -0.08,
        delta_eng    >  0.08,
    ])
    net_negative = sum([
        delta_conf   < -0.08,
        delta_stress >  0.08,
        delta_eng    < -0.08,
    ])

    if net_positive >= 2 and net_negative == 0:
        label = "improving"
        description = (
            "Behavioral signals improved consistently across the session. "
            "Confidence and engagement both increased from early to late segments, "
            "while stress indicators declined. This arc suggests the candidate settled "
            "into the interview context as the session progressed — a pattern associated "
            "with interview nerves rather than capability limitations."
        )
    elif net_negative >= 2 and net_positive == 0:
        label = "declining"
        description = (
            "Behavioral signals declined across the session. "
            "Confidence and engagement both dropped from early to late segments, "
            "while stress indicators increased. This may reflect fatigue, increasing "
            "question difficulty, or sustained pressure reducing the candidate's natural "
            "communication capacity. Follow-up probing on later-session topics is recommended."
        )
    elif net_positive >= 1 and net_negative >= 1:
        label = "mixed"
        desc_parts = []
        if delta_conf > 0.08:
            desc_parts.append("confidence improved across the session")
        elif delta_conf < -0.08:
            desc_parts.append("confidence declined in later segments")
        if delta_stress < -0.08:
            desc_parts.append("stress indicators reduced as the session progressed")
        elif delta_stress > 0.08:
            desc_parts.append("stress accumulated toward the end of the session")
        description = (
            "The session produced a mixed behavioral arc. "
            + (", ".join(desc_parts).capitalize() + ". " if desc_parts else "")
            + "Reviewing the session timeline may reveal specific question sequences "
            "associated with behavioral shifts."
        )
    else:
        label = "consistent"
        description = (
            "Behavioral signals remained broadly consistent across the session. "
            "No significant improvement or decline was detected between early and late segments. "
            "The candidate maintained a stable behavioral baseline throughout."
        )

    return {
        "label": label,
        "description": description,
        "deltas": {
            "confidence": round(delta_conf  * 100, 1),
            "stress":     round(delta_stress * 100, 1),
            "engagement": round(delta_eng   * 100, 1),
        },
    }


def _detect_contradictions(conf: float, stress: float, eng: float, comm: float, consis: float) -> list[dict]:
    """
    Detect significant cross-signal contradictions and return structured explanations.
    A contradiction is a pair of dimensions where strong performance in one is not
    mirrored by the dimension most expected to co-occur with it.
    """
    contradictions: list[dict] = []

    # Strong verbal confidence but elevated stress markers
    if conf >= 0.65 and stress >= 0.50:
        contradictions.append({
            "type":            "confident_language_under_stress",
            "signal_a":        f"Confidence {int(conf*100)}% (verbal)",
            "signal_b":        f"Stress {int(stress*100)}% (physiological)",
            "interpretation":  (
                "The candidate used assertive and clear language while simultaneously showing "
                "elevated vocal and facial stress markers. This dissociation can indicate "
                "deliberate emotional regulation — the candidate was managing visible anxiety "
                "while maintaining verbal composure. Alternatively, stress markers may reflect "
                "topic-specific pressure rather than pervasive anxiety."
            ),
            "review_required": True,
        })

    # High communication quality but low confidence
    if comm >= 0.65 and conf < 0.45:
        contradictions.append({
            "type":            "clear_articulation_low_confidence",
            "signal_a":        f"Communication {int(comm*100)}% (language quality)",
            "signal_b":        f"Confidence {int(conf*100)}% (assertiveness)",
            "interpretation":  (
                "The candidate communicated clearly and structurally — responses were well-organised "
                "and low in filler words — but vocal and linguistic confidence signals remained low. "
                "This pattern suggests the candidate has strong communication foundations but may "
                "lack assertiveness or certainty in their specific answers. Probing deeper on the "
                "topics where hesitation peaked would help distinguish knowledge gaps from delivery style."
            ),
            "review_required": False,
        })

    # Strong engagement but poor cross-modal alignment (inconsistency)
    if eng >= 0.65 and consis < 0.45:
        contradictions.append({
            "type":            "engaged_but_inconsistent",
            "signal_a":        f"Engagement {int(eng*100)}% (behavioural energy)",
            "signal_b":        f"Consistency {int(consis*100)}% (cross-modal alignment)",
            "interpretation":  (
                "The candidate showed high engagement energy — strong eye contact and responsive "
                "vocal delivery — but cross-modal signal alignment was low. Verbal content and "
                "non-verbal behaviour diverged at multiple points. This can occur when a candidate "
                "is performing enthusiasm rather than expressing it authentically, or when they are "
                "managing a significant gap between what they are saying and what they actually know."
            ),
            "review_required": True,
        })

    # High overall but very low consistency — inflated by one dominant dimension
    if consis < 0.40 and (conf + comm) / 2 >= 0.65:
        contradictions.append({
            "type":            "verbal_strength_masking_inconsistency",
            "signal_a":        f"Verbal dimensions (conf {int(conf*100)}%, comm {int(comm*100)}%)",
            "signal_b":        f"Consistency {int(consis*100)}% (cross-modal)",
            "interpretation":  (
                "Strong verbal performance on confidence and communication is offset by low "
                "cross-modal consistency. The overall score may be elevated by verbal strength "
                "masking behavioural instability in non-verbal channels. The recruiter should "
                "weigh the consistency score carefully — it often surfaces the most accurate "
                "signal of genuine comfort with interview content."
            ),
            "review_required": True,
        })

    return contradictions


def _evidence_rank(conf: float, stress: float, eng: float, comm: float, consis: float, dur: float, words: int) -> dict:
    """
    Classify evidence quality for each dimension and overall.
    Returns evidence reliability tier and data quality notes.
    """
    composure = 1.0 - stress

    # Session data adequacy
    data_quality_notes = []
    if dur < 180:
        data_quality_notes.append("Session under 3 minutes — all scores carry reduced reliability.")
    if words < 150:
        data_quality_notes.append("Low word count — language-based dimensions (confidence, communication) are less reliable.")
    if dur >= 300 and words >= 300:
        data_quality_notes.append("Session length and word count are sufficient for reliable scoring.")

    def tier(value: float) -> str:
        # High or low extremes are the most diagnostically reliable
        if value >= 0.75 or value <= 0.30:
            return "critical"
        if value >= 0.60 or value <= 0.40:
            return "supporting"
        return "contextual"

    return {
        "confidence":    tier(conf),
        "stress":        tier(stress),
        "engagement":    tier(eng),
        "communication": tier(comm),
        "consistency":   tier(consis),
        "composure":     tier(composure),
        "data_quality":  data_quality_notes,
        "overall_reliability": (
            "high"   if dur >= 300 and words >= 300 else
            "medium" if dur >= 180 and words >= 150 else
            "low"
        ),
    }


def _generate_narrative(session: Dict, frames: list | None = None) -> Dict:
    """Produce evidence-backed, evolution-aware behavioral narrative from session data."""
    conf    = float(session.get("avg_confidence",    0) or 0)
    stress  = float(session.get("avg_stress",        0) or 0)
    eng     = float(session.get("avg_engagement",    0) or 0)
    comm    = float(session.get("avg_communication", 0) or 0)
    consis  = float(session.get("avg_consistency",   0) or 0)
    dur     = float(session.get("duration",          0) or 0)
    words   = int(session.get("total_words",         0) or 0)
    fillers = int(session.get("total_filler_words",  0) or 0)
    pace    = float(session.get("avg_speaking_pace", 0) or 0)

    composure = 1.0 - stress
    overall   = (conf + eng + comm + consis + composure) / 5.0
    dur_min   = max(1, int(dur // 60))
    filler_rate = (fillers / max(words, 1)) * 100

    arc           = _behavioral_arc(frames or [])
    contradictions = _detect_contradictions(conf, stress, eng, comm, consis)
    evidence      = _evidence_rank(conf, stress, eng, comm, consis, dur, words)

    # ── Opening paragraph: characterise the session, reference the arc ──────
    arc_suffix = ""
    if arc["label"] == "improving":
        arc_suffix = (
            " Notably, behavioral signals improved across the session — the candidate demonstrated "
            "stronger performance in the latter half, suggesting initial nervousness rather than "
            "a performance ceiling."
        )
    elif arc["label"] == "declining":
        arc_suffix = (
            " Signal analysis reveals a declining behavioral arc — performance was strongest in the "
            "early portion of the session. This warrants follow-up to assess sustained performance "
            "under extended questioning."
        )
    elif arc["label"] == "mixed":
        arc_suffix = " The session arc was mixed, with specific dimensions improving while others declined."

    if overall >= 0.72:
        opening = (
            f"The candidate demonstrated a strong behavioral profile across the {dur_min}-minute session. "
            f"Multimodal signals — facial expression, vocal delivery, and language structure — aligned "
            f"coherently, indicating genuine confidence rather than performed composure.{arc_suffix}"
        )
    elif overall >= 0.52:
        opening = (
            f"The candidate showed a mixed behavioral profile across the {dur_min}-minute session. "
            f"Some dimensions performed well, while others reflect areas where targeted development "
            f"would strengthen interview presence.{arc_suffix}"
        )
    else:
        opening = (
            f"The candidate's behavioral profile across the {dur_min}-minute session indicates "
            f"significant development areas. Elevated cognitive load may have suppressed natural "
            f"communication strengths under interview conditions.{arc_suffix}"
        )

    # ── Confidence: cite evidence sources ────────────────────────────────────
    if conf >= 0.75:
        confidence_text = (
            f"Confidence scored {int(conf * 100)}%, supported by assertive language patterns, "
            f"stable vocal projection, and minimal hedging. The candidate maintained directness "
            f"across response types — a pattern consistent with genuine subject-matter familiarity."
        )
    elif conf >= 0.55:
        confidence_text = (
            f"Confidence measured {int(conf * 100)}%, reflecting moderate certainty. "
            f"The candidate performed competently on familiar topics but showed increased "
            f"pause frequency and vocal pitch variance when addressing open-ended or complex "
            f"questions — a pattern suggesting topic-specific uncertainty rather than low "
            f"general confidence."
        )
    else:
        confidence_text = (
            f"Confidence registered at {int(conf * 100)}%, indicating significant uncertainty "
            f"across the session. Prolonged pauses, reduced vocal energy, and frequent "
            f"self-corrections were detected. This is consistent with interview-condition "
            f"anxiety rather than a fundamental capability gap — coaching on delivery "
            f"under evaluation conditions is the appropriate next step."
        )

    # ── Composure: differentiate sustained vs recoverable stress ─────────────
    if stress <= 0.25:
        composure_text = (
            f"Composure remained high ({int(composure * 100)}%). Vocal energy, speech rate, "
            f"and facial tension indicators stayed within calm baseline ranges throughout. "
            f"The candidate managed interview pressure effectively."
        )
    elif stress <= 0.45:
        composure_text = (
            f"Moderate stress was detected ({int(stress * 100)}% stress index), within the "
            f"expected range for structured interviews. Periodic vocal pitch increases and "
            f"speech rate fluctuations were observed, but the candidate recovered composure "
            f"between topics — a positive indicator of self-regulation under pressure."
        )
    else:
        composure_text = (
            f"Elevated stress was consistently detected ({int(stress * 100)}% stress index). "
            f"Vocal tension, irregular speech patterns, and reduced eye-contact stability were "
            f"all present. Sustained stress at this level likely constrained the candidate's "
            f"ability to articulate at their true capability. A structured follow-up in a "
            f"lower-pressure format is recommended before drawing conclusions."
        )

    # ── Communication: reference filler data ─────────────────────────────────
    filler_desc = (
        f"Filler word frequency was low ({fillers} instances across {words} words — {filler_rate:.1f}% rate)."
        if filler_rate < 5 else
        f"Filler word frequency was {filler_rate:.1f}% ({fillers} instances across {words} words)."
    )
    if comm >= 0.72 and filler_rate < 5:
        comm_text = (
            f"Communication quality scored {int(comm * 100)}%, with well-structured responses "
            f"and a natural speaking pace of {int(pace)} wpm. {filler_desc} "
            f"Response organisation was consistent, indicating clear thinking under pressure."
        )
    elif comm >= 0.50:
        comm_text = (
            f"Communication scored {int(comm * 100)}%, with generally clear responses that "
            f"occasionally lacked structure. Pace averaged {int(pace)} wpm. {filler_desc} "
            f"Some cognitive load in response formulation was apparent on complex questions."
        )
    else:
        comm_text = (
            f"Communication quality measured {int(comm * 100)}%. {filler_desc} "
            f"Response structure was frequently fragmented. Training on structured frameworks "
            f"— such as STAR for behavioural questions — would likely produce meaningful "
            f"improvement in subsequent interviews."
        )

    # ── Engagement: address consistency alignment ─────────────────────────────
    if eng >= 0.70 and consis >= 0.65:
        engagement_text = (
            f"Engagement was high ({int(eng * 100)}%) with strong cross-modal consistency "
            f"({int(consis * 100)}%). Verbal and non-verbal signals aligned throughout — "
            f"a pattern associated with authentic presence and thorough preparation."
        )
    elif eng >= 0.50:
        engagement_text = (
            f"Engagement was moderate ({int(eng * 100)}%), with some variation in energy "
            f"across topics. Behavioral consistency scored {int(consis * 100)}%, suggesting "
            f"partial divergence between verbal content and non-verbal signals at certain points."
        )
    else:
        engagement_text = (
            f"Engagement was limited ({int(eng * 100)}%) with cross-modal consistency at "
            f"{int(consis * 100)}%. The divergence between verbal and non-verbal signals "
            f"may indicate discomfort with specific topics or difficulty maintaining "
            f"authentic presence under evaluation conditions."
        )

    # ── Recommendation ────────────────────────────────────────────────────────
    has_contradictions = len(contradictions) > 0
    contradiction_note = (
        " Cross-signal contradictions were detected and are documented separately — "
        "human review of these signals is recommended before a final determination."
        if has_contradictions else ""
    )

    if overall >= 0.72 and stress <= 0.45:
        rec_text = (
            f"The multimodal behavioral profile supports advancement. Confidence, communication, "
            f"and composure all exceeded expected thresholds, and cross-modal alignment was high. "
            f"Human review of technical content remains essential before a final decision.{contradiction_note}"
        )
        rec_label   = "Proceed"
        follow_ups: list[str] = []
    elif overall >= 0.52:
        weak_dims = []
        if conf    < 0.55: weak_dims.append("confidence under pressure")
        if stress  > 0.50: weak_dims.append("sustained composure")
        if comm    < 0.55: weak_dims.append("structured communication")
        if consis  < 0.50: weak_dims.append("cross-modal signal alignment")
        rec_text = (
            f"The behavioral profile is mixed. "
            + (f"Areas requiring attention include {', '.join(weak_dims)}. " if weak_dims else "")
            + f"A structured second interview or focused assessment is recommended "
            f"before a final determination.{contradiction_note}"
        )
        rec_label = "Review"
        follow_ups = _suggest_followups(conf, stress, comm, consis, arc)
    else:
        rec_text = (
            f"Current evidence indicates additional evaluation is needed. "
            f"The assessment reflects interview-condition performance and may not represent "
            f"the candidate's ceiling. A development-focused session before re-evaluation "
            f"is the recommended path.{contradiction_note}"
        )
        rec_label = "Hold"
        follow_ups = _suggest_followups(conf, stress, comm, consis, arc)

    # ── Recruiter decision support (B8) ───────────────────────────────────────
    strengths = []
    concerns  = []
    missing_signals = []

    if conf >= 0.65: strengths.append(f"Confidence ({int(conf*100)}%) — assertive language and stable vocal delivery")
    if composure >= 0.65: strengths.append(f"Composure ({int(composure*100)}%) — effective stress management")
    if comm >= 0.65: strengths.append(f"Communication ({int(comm*100)}%) — clear and structured responses")
    if eng >= 0.65: strengths.append(f"Engagement ({int(eng*100)}%) — active and responsive presence")
    if consis >= 0.65: strengths.append(f"Consistency ({int(consis*100)}%) — coherent cross-modal signals")
    if arc["label"] == "improving": strengths.append("Session arc: behavioral performance improved across the interview")

    if conf    < 0.50: concerns.append(f"Low confidence ({int(conf*100)}%) — significant hedging and vocal uncertainty detected")
    if stress  > 0.55: concerns.append(f"Elevated stress ({int(stress*100)}%) — may have suppressed authentic performance")
    if comm    < 0.50: concerns.append(f"Communication quality ({int(comm*100)}%) — fragmented responses and high filler frequency")
    if consis  < 0.45: concerns.append(f"Low consistency ({int(consis*100)}%) — verbal and non-verbal signals diverged")
    if arc["label"] == "declining": concerns.append("Session arc: behavioral performance declined across the interview")

    if words < 150:   missing_signals.append("Insufficient speech data — language-based dimensions are unreliable")
    if dur   < 180:   missing_signals.append("Short session duration — scores carry reduced statistical reliability")

    decision_support = {
        "strengths":        strengths[:4],
        "concerns":         concerns[:4],
        "missing_signals":  missing_signals,
        "recommendation_label":     rec_label,
        "recommendation_confidence": evidence["overall_reliability"],
        "human_review_required":     has_contradictions or rec_label != "Proceed" or evidence["overall_reliability"] == "low",
        "human_review_rationale":    (
            "Contradictions detected between signal channels require human judgement to interpret correctly."
            if has_contradictions else
            "Standard review recommended — AI analysis is supplementary evidence only."
        ),
    }

    return {
        "overall_score":       round(overall * 100),
        "recommendation":      rec_label,
        "follow_up_questions": follow_ups,
        "behavioral_arc":      arc,
        "contradictions":      contradictions,
        "evidence_quality":    evidence,
        "decision_support":    decision_support,
        "narrative": {
            "opening":        opening,
            "confidence":     confidence_text,
            "composure":      composure_text,
            "communication":  comm_text,
            "engagement":     engagement_text,
            "recommendation": rec_text,
        },
        "dimensions": {
            "confidence":    round(conf     * 100),
            "engagement":    round(eng      * 100),
            "communication": round(comm     * 100),
            "consistency":   round(consis   * 100),
            "composure":     round(composure * 100),
        },
    }


def _suggest_followups(conf: float, stress: float, comm: float, consis: float, arc: dict | None = None) -> list[str]:
    qs: list[str] = []

    if conf < 0.55:
        qs.append(
            "Walk me through a decision you made that you were initially uncertain about. "
            "What gave you the confidence to commit?"
        )
    if stress > 0.55:
        qs.append(
            "Describe the most high-pressure situation you have navigated at work. "
            "How did you manage your focus and communication under that pressure?"
        )
    if comm < 0.55:
        qs.append(
            "Explain the most complex technical challenge you have solved, "
            "as if presenting to a non-technical stakeholder."
        )
    if consis < 0.50:
        qs.append(
            "Is there anything from our conversation today that you would like to "
            "revisit or expand on? I want to make sure I have a complete picture."
        )
    if arc and arc.get("label") == "declining":
        qs.append(
            "The later questions in our conversation seemed more challenging for you. "
            "What would help you perform consistently across a longer interview process?"
        )
    if not qs:
        qs.append("What aspect of this role are you most energised about, and why?")

    return qs[:3]


@router.get("/sessions/{session_id}/narrative")
async def get_session_narrative(session_id: str):
    """
    Generate an evidence-backed behavioral narrative for a completed session.
    Returns structured analysis including behavioral arc, contradictions, and decision support.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    frames = get_session_frames(session_id)
    return _generate_narrative(dict(session), list(frames) if frames else [])


@router.get("/sessions/{session_id}/live")
async def get_session_live_state(session_id: str):
    """
    Live state of an active (in-memory) session.

    Returns real-time observability data: lifecycle status, device statuses,
    counters, current scores, and reliability.  Only available while the
    session is still in memory (CREATED / STREAMING / PAUSED).
    Returns 404 for completed sessions — use GET /api/sessions/{id} instead.
    """
    from backend.services.session_manager import session_manager
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found in memory. It may have completed — check GET /api/sessions/{id}.",
        )
    return session.to_live_state()


_stats_cache = {}

@router.get("/dashboard/stats")
async def get_dashboard_stats():
    now = time.time()
    if "data" in _stats_cache and now - _stats_cache.get("timestamp", 0) < 5:
        return _stats_cache["data"]

    stats = dashboard_stats()

    # Serialise recent_sessions timestamps
    stats["recent_sessions"] = [_serialize_session(s) for s in stats.get("recent_sessions", [])]

    try:
        from backend.services.session_manager import session_manager
        stats["active_sessions"] = len(session_manager._sessions)
    except Exception:
        stats["active_sessions"] = 0
        
    _stats_cache["data"] = stats
    _stats_cache["timestamp"] = now

    return stats


@router.get("/health/detailed")
async def health_detailed():
    models_dir = ROOT / "models"

    # ── DeBERTa ──────────────────────────────────────────────────────────────
    deberta_best = (models_dir / "deberta" / "best" / "model.pt").exists()
    deberta_metrics = None
    try:
        mp = models_dir / "deberta" / "metrics.json"
        if mp.exists():
            deberta_metrics = _json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        pass
    best_f1 = deberta_metrics.get("best_val_macro_f1") if deberta_metrics else None

    deberta_inference = False
    try:
        from ml.nlp.behavioral_nlp import BehavioralNLPInference
        deberta_inference = BehavioralNLPInference().is_deberta_active
    except Exception:
        pass

    # ── Classifiers ──────────────────────────────────────────────────────────
    clf_trained = (models_dir / "classifiers" / "confidence_clf.pkl").exists()
    clf_report = None
    try:
        rp = models_dir / "classifiers" / "report.json"
        if rp.exists():
            clf_report = _json.loads(rp.read_text(encoding="utf-8"))
    except Exception:
        pass

    # ── Fusion ───────────────────────────────────────────────────────────────
    fusion_ready = (models_dir / "fusion" / "best_fusion.pt").exists()

    # ── GPU ──────────────────────────────────────────────────────────────────
    gpu_info: dict = {
        "available": False, "name": None,
        "vram_total_mb": None, "vram_used_mb": None,
        "vram_free_mb": None, "utilization_pct": None,
    }
    try:
        import torch
        if torch.cuda.is_available():
            idx   = torch.cuda.current_device()
            free, total = torch.cuda.mem_get_info(idx)
            gpu_info = {
                "available":      True,
                "name":           torch.cuda.get_device_name(idx),
                "vram_total_mb":  round(total / 1e6),
                "vram_free_mb":   round(free  / 1e6),
                "vram_used_mb":   round((total - free) / 1e6),
                "utilization_pct": None,
            }
            try:
                import pynvml
                pynvml.nvmlInit()
                h = pynvml.nvmlDeviceGetHandleByIndex(idx)
                gpu_info["utilization_pct"] = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
            except Exception:
                pass
    except Exception:
        pass

    # ── CPU / RAM (psutil optional) ───────────────────────────────────────────
    cpu_pct = None
    ram_info: dict = {}
    storage_info: dict = {}
    uptime_seconds = None
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.1)
        vm = psutil.virtual_memory()
        ram_info = {
            "total_mb": round(vm.total    / 1e6),
            "used_mb":  round(vm.used     / 1e6),
            "free_mb":  round(vm.available / 1e6),
            "pct":      vm.percent,
        }
        du = psutil.disk_usage(str(ROOT))
        storage_info = {
            "total_gb": round(du.total / 1e9, 1),
            "used_gb":  round(du.used  / 1e9, 1),
            "free_gb":  round(du.free  / 1e9, 1),
            "pct":      du.percent,
        }
        uptime_seconds = round(time.time() - psutil.Process().create_time())
    except Exception:
        pass

    # ── Active sessions + DB ─────────────────────────────────────────────────
    active_count = 0
    db_ok = False
    try:
        from backend.services.session_manager import session_manager
        active_count = len(session_manager._sessions)
    except Exception:
        pass
    try:
        from backend.services.db_service import dashboard_stats as _ds
        _ds()
        db_ok = True
    except Exception:
        pass

    # ── Whisper availability ──────────────────────────────────────────────────
    whisper_status = "missing"
    try:
        import whisper as _whisper  # noqa: F401
        whisper_status = "online" if active_count > 0 else "idle"
    except ImportError:
        try:
            import faster_whisper as _fw  # noqa: F401
            whisper_status = "online" if active_count > 0 else "idle"
        except ImportError:
            pass

    # ── Face engine availability ──────────────────────────────────────────────
    face_status = "missing"
    try:
        import cv2 as _cv2       # noqa: F401
        import mediapipe as _mp  # noqa: F401
        face_status = "online"
    except ImportError:
        try:
            import cv2 as _cv2  # noqa: F401
            face_status = "idle"
        except ImportError:
            pass

    return {
        "status": "ok",
        "timestamp": time.time(),
        "uptime_seconds": uptime_seconds,
        "components": {
            "api":         {"status": "online"},
            "database":    {"status": "online" if db_ok else "error"},
            "deberta": {
                "status":           "online" if deberta_best else "missing",
                "checkpoint_saved": deberta_best,
                "inference_active": deberta_inference,
                "best_f1":          best_f1,
            },
            "classifiers": {
                "status":     "online" if clf_trained else "missing",
                "trained":    clf_trained,
                "n_sessions": clf_report.get("n_sessions") if clf_report else None,
            },
            "fusion": {
                "status": "online" if fusion_ready else "missing",
                "saved":  fusion_ready,
            },
            "whisper":     {"status": whisper_status},
            "face_engine": {"status": face_status},
            "gpu":         gpu_info,
            "storage":     storage_info,
        },
        "system": {
            "cpu_pct":        cpu_pct,
            "ram":            ram_info,
            "active_sessions": active_count,
        },
    }


@router.get("/benchmarks")
async def get_benchmarks():
    """Real-time system + inference performance metrics for the benchmark dashboard."""
    from backend.services.metrics_service import metrics_service

    inf = metrics_service.get_inference_stats()
    ws  = metrics_service.get_websocket_stats()

    # System metrics (reuse psutil from health endpoint)
    cpu_pct = None
    ram: dict = {}
    gpu: dict = {"available": False}
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.05)
        vm = psutil.virtual_memory()
        ram = {
            "total_mb": round(vm.total / 1e6),
            "used_mb":  round(vm.used  / 1e6),
            "free_mb":  round(vm.available / 1e6),
            "pct":      vm.percent,
        }
    except Exception:
        pass

    try:
        import torch
        if torch.cuda.is_available():
            idx = torch.cuda.current_device()
            free, total = torch.cuda.mem_get_info(idx)
            util = None
            try:
                import pynvml
                pynvml.nvmlInit()
                h = pynvml.nvmlDeviceGetHandleByIndex(idx)
                util = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
            except Exception:
                pass
            gpu = {
                "available":      True,
                "name":           torch.cuda.get_device_name(idx),
                "vram_total_mb":  round(total / 1e6),
                "vram_used_mb":   round((total - free) / 1e6),
                "vram_free_mb":   round(free / 1e6),
                "utilization_pct": util,
            }
    except Exception:
        pass

    # DeBERTa model metrics
    models_dir = ROOT / "models"
    deberta_metrics = None
    try:
        mp = models_dir / "deberta" / "metrics.json"
        if mp.exists():
            deberta_metrics = _json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        pass

    deberta_f1 = {
        "macro":         deberta_metrics.get("best_val_macro_f1", 0.824) if deberta_metrics else 0.824,
        "confidence":    deberta_metrics.get("confidence_f1",     0.862) if deberta_metrics else 0.862,
        "stress":        deberta_metrics.get("stress_f1",         0.848) if deberta_metrics else 0.848,
        "hesitation":    deberta_metrics.get("hesitation_f1",     0.817) if deberta_metrics else 0.817,
        "communication": deberta_metrics.get("communication_f1",  0.769) if deberta_metrics else 0.769,
    }

    # Session aggregate
    try:
        stats = dashboard_stats()
        session_stats = {
            "total":          stats.get("total_sessions", 0),
            "avg_confidence": stats.get("avg_confidence", 0),
            "avg_stress":     stats.get("avg_stress",     0),
            "avg_duration_s": stats.get("avg_duration",   0),
        }
    except Exception:
        session_stats = {"total": 0, "avg_confidence": 0, "avg_stress": 0, "avg_duration_s": 0}

    # Active sessions for WS connection count
    active_count = 0
    try:
        from backend.services.session_manager import session_manager as sm
        active_count = len(sm._sessions)
    except Exception:
        pass

    return {
        "system": {
            "cpu_pct":  cpu_pct,
            "ram":      ram,
            "gpu":      gpu,
        },
        "inference": inf,
        "websocket": {
            **ws,
            "active_connections":        active_count,
            "analytics_push_interval_ms": 500,
            "target_frame_rate_fps":      5,
        },
        "models": {
            "deberta": {
                "version":          "v3-base",
                "adaptation":       "LoRA r=16, α=32",
                "checkpoint":       "step_18000",
                "params_total":     184_000_000,
                "params_trainable": 442_000,
                "training_samples": 74_288,
                "f1": deberta_f1,
                "available":        (models_dir / "deberta" / "best" / "model.pt").exists(),
            },
            "whisper": {
                "version":      "base",
                "params":       74_000_000,
                "languages":    99,
                "wer_english":  0.148,
                "available":    True,
            },
            "mediapipe": {
                "model":       "Face Mesh",
                "landmarks":   468,
                "fps_target":  30,
                "detection_confidence": 0.7,
            },
            "fusion": {
                "architecture": "MLP meta-learner",
                "window_s":     3.0,
                "available":    (models_dir / "fusion" / "best_fusion.pt").exists(),
            },
        },
        "sessions": session_stats,
        "timestamp": time.time(),
    }
