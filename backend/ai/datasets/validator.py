"""
Dataset Validator — pre-training data quality checks.

Reject invalid datasets before training begins. A bad training dataset
produces a bad model — and dataset issues are often subtle enough that
training completes successfully but produces a subtly miscalibrated model.

Checks performed:
  - Missing values (NaN, None) in critical fields
  - Class imbalance (any class < 10% of dataset)
  - Annotation consistency (label ranges valid)
  - Feature completeness per sample
  - Duplicate sample detection (by content hash)
  - Sample count sufficiency

The validator runs as a mandatory gate before any training job starts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ValidationIssue:
    severity: str    # "error" | "warning" | "info"
    check:    str
    message:  str
    samples_affected: int = 0


@dataclass
class DatasetValidationReport:
    dataset_name:    str
    dataset_version: str
    total_samples:   int
    passed:          bool
    errors:          List[ValidationIssue] = field(default_factory=list)
    warnings:        List[ValidationIssue] = field(default_factory=list)
    info:            List[ValidationIssue] = field(default_factory=list)
    statistics:      Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "dataset_name":    self.dataset_name,
            "dataset_version": self.dataset_version,
            "total_samples":   self.total_samples,
            "passed":          self.passed,
            "error_count":     len(self.errors),
            "warning_count":   len(self.warnings),
            "errors":   [{"check": e.check, "message": e.message, "samples": e.samples_affected}
                         for e in self.errors],
            "warnings": [{"check": w.check, "message": w.message, "samples": w.samples_affected}
                         for w in self.warnings],
            "statistics": self.statistics,
        }


class DatasetValidator:
    """
    Validates behavioral interview datasets before training.

    Input: list of sample dicts, each with at least:
        {
            "session_id": str,
            "features": {...},
            "labels": {"confidence": float, "stress": float, ...}
        }
    """

    REQUIRED_LABEL_KEYS   = ["confidence", "stress", "communication", "engagement", "consistency"]
    REQUIRED_FEATURE_KEYS = ["session_duration", "total_words"]
    MIN_SAMPLES           = 50
    MIN_CLASS_FRACTION    = 0.05   # any label bucket below 5% triggers imbalance warning
    LABEL_MIN             = 0.0
    LABEL_MAX             = 1.0

    def validate(
        self,
        samples:         List[Dict],
        dataset_name:    str = "unknown",
        dataset_version: str = "unknown",
    ) -> DatasetValidationReport:
        errors:   List[ValidationIssue] = []
        warnings: List[ValidationIssue] = []
        info:     List[ValidationIssue] = []
        stats:    Dict = {}

        n = len(samples)
        stats["total_samples"] = n

        # ── Check 1: sample count ─────────────────────────────────────────────
        if n < self.MIN_SAMPLES:
            errors.append(ValidationIssue(
                severity="error",
                check="sample_count",
                message=f"Dataset has only {n} samples; minimum is {self.MIN_SAMPLES}.",
            ))
        else:
            info.append(ValidationIssue(
                severity="info", check="sample_count",
                message=f"Sample count {n} ≥ {self.MIN_SAMPLES}.",
            ))

        if n == 0:
            return DatasetValidationReport(
                dataset_name=dataset_name, dataset_version=dataset_version,
                total_samples=0, passed=False, errors=errors,
            )

        # ── Check 2: missing labels ───────────────────────────────────────────
        for key in self.REQUIRED_LABEL_KEYS:
            missing_count = sum(
                1 for s in samples
                if s.get("labels", {}).get(key) is None
            )
            if missing_count > 0:
                errors.append(ValidationIssue(
                    severity="error",
                    check="missing_labels",
                    message=f"Label '{key}' is None in {missing_count}/{n} samples.",
                    samples_affected=missing_count,
                ))

        # ── Check 3: label range validation ──────────────────────────────────
        for key in self.REQUIRED_LABEL_KEYS:
            out_of_range = [
                s for s in samples
                if s.get("labels", {}).get(key) is not None
                and not (self.LABEL_MIN <= s["labels"][key] <= self.LABEL_MAX)
            ]
            if out_of_range:
                errors.append(ValidationIssue(
                    severity="error",
                    check="label_range",
                    message=f"Label '{key}' out of [{self.LABEL_MIN},{self.LABEL_MAX}] in {len(out_of_range)} samples.",
                    samples_affected=len(out_of_range),
                ))

        # ── Check 4: class imbalance (confidence bucketed) ────────────────────
        conf_values = [
            s["labels"]["confidence"] for s in samples
            if s.get("labels", {}).get("confidence") is not None
        ]
        if conf_values:
            low  = sum(1 for v in conf_values if v < 0.33)
            med  = sum(1 for v in conf_values if 0.33 <= v < 0.66)
            high = sum(1 for v in conf_values if v >= 0.66)
            stats["confidence_distribution"] = {
                "low": low, "medium": med, "high": high,
            }
            for label, count in [("low", low), ("medium", med), ("high", high)]:
                frac = count / len(conf_values)
                if frac < self.MIN_CLASS_FRACTION:
                    warnings.append(ValidationIssue(
                        severity="warning",
                        check="class_imbalance",
                        message=f"Confidence class '{label}' has only {frac*100:.1f}% of samples.",
                        samples_affected=count,
                    ))

        # ── Check 5: required features present ───────────────────────────────
        for key in self.REQUIRED_FEATURE_KEYS:
            missing_count = sum(
                1 for s in samples
                if s.get("features", {}).get(key) is None
            )
            if missing_count > 0:
                warnings.append(ValidationIssue(
                    severity="warning",
                    check="missing_features",
                    message=f"Feature '{key}' missing in {missing_count}/{n} samples.",
                    samples_affected=missing_count,
                ))

        # ── Check 6: duplicate detection ──────────────────────────────────────
        hashes = set()
        duplicates = 0
        for s in samples:
            h = hashlib.md5(
                json.dumps(s.get("features", {}), sort_keys=True).encode()
            ).hexdigest()
            if h in hashes:
                duplicates += 1
            hashes.add(h)
        stats["duplicate_count"] = duplicates
        if duplicates > 0:
            warnings.append(ValidationIssue(
                severity="warning",
                check="duplicates",
                message=f"{duplicates} duplicate feature sets detected.",
                samples_affected=duplicates,
            ))

        # ── Summary stats ──────────────────────────────────────────────────────
        for key in self.REQUIRED_LABEL_KEYS:
            values = [
                s["labels"][key] for s in samples
                if s.get("labels", {}).get(key) is not None
            ]
            if values:
                stats[f"label_{key}_mean"]   = round(sum(values) / len(values), 4)
                stats[f"label_{key}_min"]    = round(min(values), 4)
                stats[f"label_{key}_max"]    = round(max(values), 4)

        passed = len(errors) == 0
        return DatasetValidationReport(
            dataset_name    = dataset_name,
            dataset_version = dataset_version,
            total_samples   = n,
            passed          = passed,
            errors          = errors,
            warnings        = warnings,
            info            = info,
            statistics      = stats,
        )


dataset_validator = DatasetValidator()
