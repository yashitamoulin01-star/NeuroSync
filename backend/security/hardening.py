"""
Security hardening layer.

Provides:
  1. security_middleware — ASGI middleware for request-level security checks
  2. validate_file_upload — validates uploaded files before processing

The middleware runs after the rate-limiter (wired in main.py) and before
route handlers. It is intentionally lightweight: complex validation belongs
in individual route validators, not a universal middleware.

Checks performed:
  - Path traversal patterns (%2e, ../, ..\)
  - Query parameter length limits
  - Basic injection pattern detection (XSS, SQLi, JS injection)
  - Request body size via Content-Length header
  - Removal of server identification headers from responses

What is NOT checked here (handled elsewhere):
  - Authentication / authorization (future: JWT middleware)
  - CSRF (handled by SameSite cookies + CORS)
  - Rate limiting (handled in main.py middleware)
"""

from __future__ import annotations

import logging
import re
from typing import Set

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("neurosync.security")

# ── Limits ────────────────────────────────────────────────────────────────────

MAX_BODY_BYTES       = 100 * 1024 * 1024   # 100 MB hard cap
MAX_QUERY_VALUE_LEN  = 1024
MAX_PATH_LEN         = 512

# ── Detection patterns ────────────────────────────────────────────────────────

_TRAVERSAL = re.compile(
    r"(\.\./|\.\.\\|%2e%2e|%252e%252e|%c0%af|%c1%9c)",
    re.IGNORECASE,
)
_INJECTION_PATTERNS = [
    (re.compile(r"<\s*script",           re.IGNORECASE), "XSS"),
    (re.compile(r"\bunion\b.*\bselect\b", re.IGNORECASE), "SQLi"),
    (re.compile(r"\bexec\s*\(",          re.IGNORECASE), "cmd_injection"),
    (re.compile(r"javascript\s*:",       re.IGNORECASE), "JS_injection"),
    (re.compile(r"\beval\s*\(",          re.IGNORECASE), "eval_injection"),
]

# Paths where injection scanning is skipped (WebSocket, docs)
_SCAN_SKIP_PREFIXES: Set[str] = {"/ws/", "/docs", "/redoc", "/openapi.json"}


def _should_scan(path: str) -> bool:
    return not any(path.startswith(p) for p in _SCAN_SKIP_PREFIXES)


def _detect_injection(value: str) -> str | None:
    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(value):
            return label
    return None


# ── Middleware ────────────────────────────────────────────────────────────────

async def security_middleware(request: Request, call_next):
    path = request.url.path

    # 1. Path length
    if len(path) > MAX_PATH_LEN:
        return JSONResponse(status_code=414, content={"detail": "URI too long"})

    # 2. Path traversal
    if _TRAVERSAL.search(path):
        ip = request.client.host if request.client else "unknown"
        logger.warning("security:traversal path=%s ip=%s", path, ip)
        return JSONResponse(status_code=400, content={"detail": "Invalid request path"})

    if _should_scan(path):
        # 3. Query parameter scanning
        for key, value in request.query_params.items():
            if len(value) > MAX_QUERY_VALUE_LEN:
                return JSONResponse(status_code=400, content={"detail": f"Query parameter '{key}' too long"})
            label = _detect_injection(value)
            if label:
                ip = request.client.host if request.client else "unknown"
                logger.warning("security:injection type=%s param=%s ip=%s", label, key, ip)
                return JSONResponse(status_code=400, content={"detail": "Invalid request"})

    # 4. Content-Length hard cap
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body exceeds {MAX_BODY_BYTES // 1_000_000} MB limit"},
                )
        except ValueError:
            pass

    response = await call_next(request)

    # 5. Strip server identification
    response.headers.pop("server",       None)
    response.headers.pop("x-powered-by", None)

    return response


# ── File upload validator ─────────────────────────────────────────────────────

_ALLOWED_EXTENSIONS = frozenset({".wav", ".mp3", ".mp4", ".webm", ".ogg", ".json", ".csv", ".txt"})
_ALLOWED_TYPES      = frozenset({
    "audio/wav", "audio/wave", "audio/x-wav",
    "audio/mpeg", "audio/ogg", "audio/webm",
    "video/mp4", "video/webm",
    "application/json", "text/csv", "text/plain",
})


def validate_file_upload(filename: str, content_type: str, size_bytes: int) -> None:
    """
    Validate an uploaded file before processing.
    Raises ValueError with a descriptive message on rejection.
    """
    from pathlib import Path
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise ValueError(
            f"File type '{ext}' not permitted. "
            f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )
    # Normalise content-type (strip charset and parameters)
    ct_base = content_type.split(";")[0].strip().lower()
    if ct_base not in _ALLOWED_TYPES:
        raise ValueError(f"Content-Type '{ct_base}' not permitted")
    if size_bytes > MAX_BODY_BYTES:
        raise ValueError(
            f"File too large: {size_bytes / 1e6:.1f} MB "
            f"(limit: {MAX_BODY_BYTES / 1e6:.0f} MB)"
        )
