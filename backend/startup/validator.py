"""
Startup configuration validator — fail fast on misconfiguration.

Called once at application startup before accepting any requests.
Critical errors raise ConfigurationError immediately.
Non-critical issues are logged as warnings and allow startup to continue.

Checks:
  - Required numeric ranges for all settings
  - Whisper model/device validity
  - Data directory accessibility
  - Port range validity
  - CORS safety (warns if wildcard)
  - AI configuration integrity
  - Python version compatibility
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from backend.core.errors import ConfigurationError

logger = logging.getLogger("neurosync.startup")


@dataclass
class CheckResult:
    name:     str
    passed:   bool
    warnings: List[str] = field(default_factory=list)
    errors:   List[str] = field(default_factory=list)


def _check_python_version() -> CheckResult:
    r = CheckResult("python_version", True)
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 10):
        r.errors.append(f"Python {major}.{minor} detected — Python 3.10+ required")
        r.passed = False
    elif (major, minor) < (3, 11):
        r.warnings.append(f"Python {major}.{minor} detected — Python 3.11+ recommended for best performance")
    return r


def _check_whisper_settings(settings) -> CheckResult:
    r = CheckResult("whisper_config", True)
    VALID_MODELS = {
        "tiny", "tiny.en", "base", "base.en",
        "small", "small.en", "medium", "medium.en",
        "large", "large-v1", "large-v2", "large-v3",
    }
    if settings.WHISPER_MODEL not in VALID_MODELS:
        r.errors.append(
            f"Invalid WHISPER_MODEL='{settings.WHISPER_MODEL}'. "
            f"Valid: {', '.join(sorted(VALID_MODELS))}"
        )
        r.passed = False
    if settings.WHISPER_DEVICE not in {"cpu", "cuda", "mps"}:
        r.errors.append(
            f"Invalid WHISPER_DEVICE='{settings.WHISPER_DEVICE}'. Valid: cpu, cuda, mps"
        )
        r.passed = False
    if settings.WHISPER_DEVICE == "cuda":
        try:
            import torch
            if not torch.cuda.is_available():
                r.warnings.append("WHISPER_DEVICE=cuda but torch.cuda.is_available() is False — will fall back to CPU")
        except ImportError:
            r.warnings.append("WHISPER_DEVICE=cuda but torch is not installed")
    return r


def _check_numeric_ranges(settings) -> CheckResult:
    r = CheckResult("numeric_ranges", True)
    checks: List[Tuple[str, float, float, float]] = [
        ("WINDOW_SIZE_SECONDS",         settings.WINDOW_SIZE_SECONDS,          0.5,   300.0),
        ("ANALYTICS_FPS",               settings.ANALYTICS_FPS,                1,     120),
        ("FACE_DETECTION_CONFIDENCE",   settings.FACE_DETECTION_CONFIDENCE,    0.0,   1.0),
        ("FACE_TRACKING_CONFIDENCE",    settings.FACE_TRACKING_CONFIDENCE,     0.0,   1.0),
        ("AUDIO_SAMPLE_RATE",           settings.AUDIO_SAMPLE_RATE,            8000,  48000),
        ("AUDIO_CHUNK_DURATION",        settings.AUDIO_CHUNK_DURATION,         0.05,  30.0),
        ("PORT",                        settings.PORT,                         1024,  65535),
    ]
    for name, value, lo, hi in checks:
        if not (lo <= value <= hi):
            r.errors.append(f"{name}={value} outside valid range [{lo}, {hi}]")
            r.passed = False
    return r


def _check_data_directories(settings) -> CheckResult:
    r = CheckResult("data_directories", True)
    dirs = [
        (settings.DATASET_DIR,       "data directory"),
        (settings.TRAINING_OUTPUT_DIR, "model output directory"),
    ]
    for dir_path, label in dirs:
        p = Path(dir_path)
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
                r.warnings.append(f"Created missing {label}: {p}")
            except Exception as exc:
                r.errors.append(f"Cannot create {label} '{p}': {exc}")
                r.passed = False
        elif not os.access(p, os.W_OK):
            r.errors.append(f"{label} '{p}' is not writable")
            r.passed = False
    return r


def _check_cors(settings) -> CheckResult:
    r = CheckResult("cors_config", True)
    if "*" in settings.ALLOWED_ORIGINS:
        r.warnings.append(
            "ALLOWED_ORIGINS contains '*' — CORS is fully open. "
            "Set specific origins in production via ALLOWED_ORIGINS env var."
        )
    if not settings.ALLOWED_ORIGINS:
        r.warnings.append("ALLOWED_ORIGINS is empty — all cross-origin requests will be blocked")
    return r


def _check_environment_vars() -> CheckResult:
    r = CheckResult("environment_variables", True)
    optional_with_notes = {
        "DATABASE_URL":  "using local SQLite",
        "SUPABASE_URL":  "cloud sync unavailable",
        "SUPABASE_KEY":  "cloud sync unavailable",
    }
    for var, note in optional_with_notes.items():
        if not os.getenv(var):
            r.warnings.append(f"{var} not configured — {note}")
    secret_patterns = ("KEY", "SECRET", "TOKEN", "PASSWORD")
    for key, value in os.environ.items():
        if any(p in key for p in secret_patterns) and value.startswith("sk-"):
            r.warnings.append(f"Environment variable {key} appears to contain an API key prefix — ensure secrets are not logged")
    return r


def _check_ai_configuration() -> CheckResult:
    r = CheckResult("ai_configuration", True)
    try:
        from backend.ai.configuration.ai_config import ai_config
        d = ai_config.to_dict()
        if not d:
            r.warnings.append("AI configuration is empty — using defaults")
    except Exception as exc:
        r.errors.append(f"AI configuration failed to load: {exc}")
        r.passed = False
    return r


# ── Public entry point ────────────────────────────────────────────────────────

def validate_startup() -> None:
    """
    Run all startup validation checks.

    Logs a WARNING for each non-critical issue.
    Raises ConfigurationError (with all error messages) if any critical check fails.
    This function should be called once at application startup, before yield in lifespan.
    """
    from backend.core.config import settings

    checks = [
        _check_python_version(),
        _check_whisper_settings(settings),
        _check_numeric_ranges(settings),
        _check_data_directories(settings),
        _check_cors(settings),
        _check_environment_vars(),
        _check_ai_configuration(),
    ]

    all_warnings: List[str] = []
    all_errors:   List[str] = []

    for check in checks:
        for w in check.warnings:
            logger.warning("[startup/%s] %s", check.name, w)
            all_warnings.append(w)
        for e in check.errors:
            logger.error("[startup/%s] CRITICAL: %s", check.name, e)
            all_errors.append(e)

    if all_errors:
        raise ConfigurationError(
            f"Startup validation failed ({len(all_errors)} error(s)): "
            + " | ".join(all_errors)
        )

    logger.info(
        "Startup validation passed — %d warning(s), 0 errors",
        len(all_warnings),
    )
