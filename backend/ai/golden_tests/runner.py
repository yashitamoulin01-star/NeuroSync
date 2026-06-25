"""
Golden Test Runner — executes the full reasoning pipeline against golden scenarios.

Runs every golden scenario through the actual reasoning pipeline and validates
that outputs fall within expected ranges. This is the canary that detects
regressions before they reach production.

Every CI run (or manual trigger) should execute this suite.
If any scenario fails, deployment is blocked until fixed.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.ai.golden_tests.scenarios import GOLDEN_SCENARIOS, GoldenScenario

logger = logging.getLogger(__name__)


@dataclass
class ScenarioRunResult:
    scenario_id:   str
    name:          str
    category:      str
    passed:        bool
    duration_ms:   float
    scores:        Dict
    behavioral_state: str
    reliability:   str
    validation:    Dict


@dataclass
class GoldenTestReport:
    total:         int
    passed:        int
    failed:        int
    skipped:       int
    duration_ms:   float
    pipeline_version: str
    results:       List[ScenarioRunResult] = field(default_factory=list)
    failures:      List[str]              = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0

    def to_dict(self) -> Dict:
        return {
            "total":            self.total,
            "passed":           self.passed,
            "failed":           self.failed,
            "skipped":          self.skipped,
            "pass_rate":        round(self.pass_rate, 3),
            "duration_ms":      round(self.duration_ms, 1),
            "pipeline_version": self.pipeline_version,
            "failures":         self.failures,
            "results": [
                {
                    "scenario_id":      r.scenario_id,
                    "name":             r.name,
                    "category":         r.category,
                    "passed":           r.passed,
                    "duration_ms":      round(r.duration_ms, 2),
                    "scores":           {k: round(v, 4) for k, v in r.scores.items()},
                    "behavioral_state": r.behavioral_state,
                    "reliability":      r.reliability,
                    "validation":       r.validation,
                }
                for r in self.results
            ],
        }


def _build_mock_evidence(scenario: GoldenScenario):
    """
    Build synthetic BehavioralEvidence from scenario signals.

    Translates scenario signal dictionaries into the same evidence
    format the real extractors produce, so the reasoning pipeline
    receives realistic inputs.
    """
    from backend.models.evidence import (
        BehavioralEvidence, EvidenceDimension, EvidencePolarity,
    )
    import uuid

    evidence = []
    face = scenario.face_signals
    audio = scenario.audio_signals
    nlp = scenario.nlp_signals

    def _ev(dim, polarity, contribution, modalities):
        return BehavioralEvidence(
            id=str(uuid.uuid4())[:8],
            dimension=dim,
            polarity=polarity,
            description=f"synthetic:{scenario.scenario_id}:{dim.value}",
            source_modalities=modalities,
            contribution=min(contribution, 0.40),
        )

    P = EvidencePolarity.POSITIVE
    N = EvidencePolarity.NEGATIVE
    D = EvidenceDimension

    # Face signals
    if ec := face.get("eye_contact"):
        pol = P if ec > 0.60 else N
        evidence.append(_ev(D.ENGAGEMENT,    pol, abs(ec - 0.5) * 0.6, ["face"]))
        evidence.append(_ev(D.CONFIDENCE,    pol, abs(ec - 0.5) * 0.4, ["face"]))
        # For STRESS (descending dim): calm eye contact (high ec) → POSITIVE → decreases stress
        stress_pol = P if ec > 0.60 else N
        evidence.append(_ev(D.STRESS, stress_pol, abs(ec - 0.5) * 0.35, ["face"]))

    if hs := face.get("head_stability"):
        pol = P if hs > 0.60 else N
        evidence.append(_ev(D.CONSISTENCY,   pol, abs(hs - 0.5) * 0.4, ["face"]))
        # Stable head → POSITIVE → decreases stress; unstable → NEGATIVE → increases stress
        evidence.append(_ev(D.STRESS,        pol, abs(hs - 0.5) * 0.3, ["face"]))

    # Audio signals
    if audio.get("is_speaking"):
        evidence.append(_ev(D.ENGAGEMENT,    P, 0.20, ["audio"]))
        wpm = audio.get("speech_rate_wpm", 120)
        # Optimal pace: 120–160 WPM
        if 100 <= wpm <= 160:
            evidence.append(_ev(D.COMMUNICATION, P, 0.25, ["audio"]))
            evidence.append(_ev(D.STRESS,        P, 0.15, ["audio"]))   # steady pace → calmer
        elif wpm > 180:
            # NEGATIVE for STRESS (descending dim) → increases stress score
            evidence.append(_ev(D.STRESS,        N, 0.30, ["audio"]))   # rapid = stress
            evidence.append(_ev(D.COMMUNICATION, N, 0.15, ["audio"]))
        elif wpm < 100:
            # Halting/slow speech → hesitation → stress
            evidence.append(_ev(D.STRESS,        N, 0.25, ["audio"]))
            evidence.append(_ev(D.CONFIDENCE,    N, 0.20, ["audio"]))

    # NLP signals
    if fr := nlp.get("filler_rate"):
        pol = N if fr > 0.08 else P
        evidence.append(_ev(D.CONFIDENCE,    pol, min(fr * 2, 0.30), ["nlp"]))
        evidence.append(_ev(D.COMMUNICATION, pol, min(fr * 1.5, 0.25), ["nlp"]))

    if cl := nlp.get("clarity_score"):
        pol = P if cl > 0.60 else N
        evidence.append(_ev(D.COMMUNICATION, pol, abs(cl - 0.5) * 0.5, ["nlp"]))

    if conf_lang := nlp.get("confidence_language"):
        pol = P if conf_lang > 0.60 else N
        evidence.append(_ev(D.CONFIDENCE,    pol, abs(conf_lang - 0.5) * 0.5, ["nlp"]))

    return evidence


def _build_mock_quality(scenario: GoldenScenario):
    from backend.models.evidence import ModalityQuality
    face_ok  = bool(scenario.face_signals)
    audio_ok = bool(scenario.audio_signals)
    nlp_ok   = bool(scenario.nlp_signals)
    return ModalityQuality(
        face_available  = face_ok,
        face_quality    = scenario.face_signals.get("eye_contact", 0.7) if face_ok else 0.0,
        audio_available = audio_ok,
        audio_quality   = 0.75 if audio_ok else 0.0,
        nlp_available   = nlp_ok,
        nlp_quality     = scenario.nlp_signals.get("clarity_score", 0.65) if nlp_ok else 0.0,
        transcript_words = scenario.total_words,
        evidence_coverage = 0.8 if (face_ok and audio_ok and nlp_ok) else 0.4,
    )


def run_golden_suite(
    scenarios: Optional[List[GoldenScenario]] = None,
    pipeline_version: str = "3.0.0",
) -> GoldenTestReport:
    """
    Run all golden scenarios through the reasoning pipeline.

    Does NOT invoke ML models — uses synthetic evidence built from
    scenario signal parameters. Fast (~50ms total).
    """
    from backend.reasoning.reasoner import reasoner

    target = scenarios or GOLDEN_SCENARIOS
    results: List[ScenarioRunResult] = []
    failures: List[str] = []
    passed_count = 0
    skipped_count = 0
    suite_start = time.perf_counter()

    for scenario in target:
        t0 = time.perf_counter()
        try:
            evidence = _build_mock_evidence(scenario)
            quality  = _build_mock_quality(scenario)

            breakdown = reasoner.reason(
                evidence         = evidence,
                quality          = quality,
                session_duration = scenario.session_duration_s,
                total_words      = scenario.total_words,
            )

            scores = {
                "confidence":    breakdown.confidence,
                "stress":        breakdown.stress,
                "communication": breakdown.communication,
                "engagement":    breakdown.engagement,
                "consistency":   breakdown.consistency,
            }
            reliability = breakdown.reliability.value

            # Check reliability exclusion
            if scenario.expected_reliability_not:
                rel_ok = reliability != scenario.expected_reliability_not
            else:
                rel_ok = True

            # Run scenario validation
            validation = scenario.validate(scores)
            if not rel_ok:
                validation["passed"] = False
                validation["checks"].append({
                    "name": "reliability_exclusion",
                    "passed": False,
                    "reason": f"reliability={reliability!r} should not be {scenario.expected_reliability_not!r}",
                })

            passed = validation["passed"] and rel_ok
            duration_ms = (time.perf_counter() - t0) * 1000

            result = ScenarioRunResult(
                scenario_id      = scenario.scenario_id,
                name             = scenario.name,
                category         = scenario.category,
                passed           = passed,
                duration_ms      = duration_ms,
                scores           = scores,
                behavioral_state = "warming_up",   # no temporal context in synthetic runs
                reliability      = reliability,
                validation       = validation,
            )
            results.append(result)

            if passed:
                passed_count += 1
            else:
                failures.append(f"{scenario.scenario_id} {scenario.name}: "
                                + "; ".join(c["reason"] for c in validation["checks"] if not c["passed"]))
                logger.warning("Golden test FAILED: %s", scenario.scenario_id)

        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            logger.exception("Golden test ERROR: %s — %s", scenario.scenario_id, exc)
            results.append(ScenarioRunResult(
                scenario_id=scenario.scenario_id, name=scenario.name,
                category=scenario.category, passed=False, duration_ms=duration_ms,
                scores={}, behavioral_state="", reliability="",
                validation={"passed": False, "error": str(exc), "checks": []},
            ))
            failures.append(f"{scenario.scenario_id}: exception — {exc}")

    total_ms = (time.perf_counter() - suite_start) * 1000

    return GoldenTestReport(
        total            = len(target),
        passed           = passed_count,
        failed           = len(target) - passed_count - skipped_count,
        skipped          = skipped_count,
        duration_ms      = total_ms,
        pipeline_version = pipeline_version,
        results          = results,
        failures         = failures,
    )
