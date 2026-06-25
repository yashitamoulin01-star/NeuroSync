"""
Explainability Validator — ensures every prediction includes required explanation.

Every behavioral recommendation must be:
  - Grounded in specific evidence (no "confidence is low" without WHY)
  - Conflict-aware (contradictions are surfaced, not hidden)
  - Traceable (reasoning chain from raw features to score)
  - Transparent about missing data (missing modalities disclosed)

This validator runs at the prediction level (not model level) and
catches regressions where the explainability pipeline silently degrades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ExplainabilityCheck:
    name:    str
    passed:  bool
    reason:  str


@dataclass
class ExplainabilityValidationResult:
    session_id:      str
    window_index:    int
    passed:          bool
    score:           float             # 0–1 completeness fraction
    checks:          List[ExplainabilityCheck] = field(default_factory=list)
    missing_fields:  List[str]         = field(default_factory=list)
    warnings:        List[str]         = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "session_id":    self.session_id,
            "window_index":  self.window_index,
            "passed":        self.passed,
            "completeness_score": round(self.score, 3),
            "missing_fields":  self.missing_fields,
            "warnings":        self.warnings,
            "checks": [
                {"name": c.name, "passed": c.passed, "reason": c.reason}
                for c in self.checks
            ],
        }


class ExplainabilityValidator:
    """
    Validates that a FusedAnalytics payload carries complete explainability data.

    "Opaque recommendations are not allowed."
    — Phase 3 engineering principle
    """

    REQUIRED_EXPLANATION_KEYS = [
        "dimensions",
        "overall_reasoning_confidence",
        "conflict_summary",
        "recommendation",
    ]

    REQUIRED_DIMENSION_KEYS = [
        "supporting_behaviors",
        "reasoning_path",
        "calibrated_score",
        "evidence_count",
    ]

    def validate(
        self,
        fused_analytics_dict: Dict,
        session_id:  str = "",
        window_index: int = 0,
        strict:      bool = False,
    ) -> ExplainabilityValidationResult:
        checks: List[ExplainabilityCheck] = []
        missing: List[str] = []
        warnings: List[str] = []

        # ── Check 1: explanation block present ───────────────────────────────
        explanation = fused_analytics_dict.get("explanation")
        has_explanation = explanation is not None
        checks.append(ExplainabilityCheck(
            name="explanation_present",
            passed=has_explanation,
            reason="explanation block found" if has_explanation else "explanation is None (REST-only field may be stripped in WS)",
        ))
        if not has_explanation:
            warnings.append("explanation not present — expected on REST responses")

        # ── Check 2: behavioral state assigned ───────────────────────────────
        has_state = bool(fused_analytics_dict.get("behavioral_state"))
        checks.append(ExplainabilityCheck(
            name="behavioral_state_present",
            passed=has_state,
            reason="behavioral_state assigned" if has_state else "behavioral_state is missing",
        ))
        if not has_state:
            missing.append("behavioral_state")

        # ── Check 3: evidence items present ──────────────────────────────────
        evidence = fused_analytics_dict.get("evidence", [])
        has_evidence = len(evidence) > 0
        checks.append(ExplainabilityCheck(
            name="evidence_present",
            passed=has_evidence,
            reason=f"{len(evidence)} evidence items" if has_evidence else "no evidence items",
        ))
        if not has_evidence:
            missing.append("evidence")

        # ── Check 4: calibration block present ───────────────────────────────
        calibration = fused_analytics_dict.get("calibration")
        has_calibration = calibration is not None
        checks.append(ExplainabilityCheck(
            name="calibration_present",
            passed=has_calibration,
            reason="calibration block found" if has_calibration else "calibration is None",
        ))
        if not has_calibration:
            missing.append("calibration")

        # ── Check 5: decision trace ───────────────────────────────────────────
        trace = fused_analytics_dict.get("decision_trace")
        has_trace = trace is not None
        checks.append(ExplainabilityCheck(
            name="decision_trace_present",
            passed=has_trace,
            reason="decision_trace found" if has_trace else "decision_trace is None (REST-only, may be stripped)",
        ))

        # ── Check 6: insights not empty ───────────────────────────────────────
        insights = fused_analytics_dict.get("insights", [])
        has_insights = len(insights) > 0
        checks.append(ExplainabilityCheck(
            name="insights_present",
            passed=has_insights,
            reason=f"{len(insights)} insights" if has_insights else "no insights generated",
        ))
        if not has_insights:
            warnings.append("no insights in this window — may be early in session")

        # ── Check 7: explanation dimensions complete ───────────────────────────
        if has_explanation and explanation:
            dims = explanation.get("dimensions", {})
            dim_issues = []
            for dim_name, dim_data in dims.items():
                for key in self.REQUIRED_DIMENSION_KEYS:
                    if key not in dim_data:
                        dim_issues.append(f"{dim_name}.{key}")
            checks.append(ExplainabilityCheck(
                name="dimension_completeness",
                passed=len(dim_issues) == 0,
                reason="all dimension fields present" if not dim_issues
                       else f"missing: {', '.join(dim_issues)}",
            ))

        # ── Check 8: conflict awareness ────────────────────────────────────────
        conflict_count = fused_analytics_dict.get("conflict_count", -1)
        has_conflict_tracking = conflict_count >= 0
        checks.append(ExplainabilityCheck(
            name="conflict_tracking",
            passed=has_conflict_tracking,
            reason=f"conflict_count={conflict_count}" if has_conflict_tracking else "conflict_count missing",
        ))

        # ── Check 9: data_quality block ───────────────────────────────────────
        dq = fused_analytics_dict.get("data_quality")
        has_quality = dq is not None
        checks.append(ExplainabilityCheck(
            name="data_quality_present",
            passed=has_quality,
            reason="data_quality found" if has_quality else "data_quality is None",
        ))
        if not has_quality:
            missing.append("data_quality")

        # ── Score and gate ────────────────────────────────────────────────────
        total       = len(checks)
        passed_count = sum(1 for c in checks if c.passed)
        score       = passed_count / total if total > 0 else 0.0

        # In strict mode: ALL checks must pass. In normal mode: missing[] = fail.
        if strict:
            overall_passed = all(c.passed for c in checks)
        else:
            overall_passed = len(missing) == 0

        return ExplainabilityValidationResult(
            session_id   = session_id,
            window_index = window_index,
            passed       = overall_passed,
            score        = score,
            checks       = checks,
            missing_fields = missing,
            warnings     = warnings,
        )


explainability_validator = ExplainabilityValidator()
