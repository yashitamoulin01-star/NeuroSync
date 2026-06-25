"""
NeuroSync — Multimodal Behavioral Analysis Platform
FastAPI backend entry point.
"""

import logging
import asyncio
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import settings
from backend.core.errors import NeuroSyncError
from backend.core.events.bus import event_bus
from backend.core.events.types import BackendEvent, EventType
from backend.core.registry.model_registry import model_registry
from backend.routers import session as session_router
from backend.routers import analytics as analytics_router
from backend.routers import ws_session as ws_router
from backend.routers import dataset as dataset_router
from backend.routers import labeling as labeling_router
from backend.routers import media as media_router
from backend.routers import validation as validation_router
from backend.routers import training as training_router
from backend.routers import sessions_history as history_router
from backend.routers import system as system_router
from backend.routers import ai_platform as ai_platform_router
from backend.routers import observability as observability_router
from backend.routers import enterprise_auth as enterprise_auth_router
from backend.routers import enterprise_governance as enterprise_governance_router
from backend.routers import enterprise_platform as enterprise_platform_router
from backend.routers import connectors as connectors_router
from backend.routers import uploads as uploads_router
from backend.routers import capture as capture_router
from backend.routers import ats as ats_router
from backend.behavioral_memory import router as _bm_router_module
from backend.behavioral_knowledge import router as _bk_router_module

import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "correlation_id"):
            log_record["correlation_id"] = record.correlation_id
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    handlers=[handler],
    force=True
)
logger = logging.getLogger("neurosync")


def _wire_event_subscriptions() -> None:
    """Subscribe internal components to lifecycle events."""
    def _on_session_created(event: BackendEvent) -> None:
        logger.info("event:SESSION_CREATED session=%s", event.session_id)

    def _on_session_ended(event: BackendEvent) -> None:
        logger.info("event:SESSION_ENDED session=%s", event.session_id)

    event_bus.subscribe(EventType.SESSION_CREATED, _on_session_created)
    event_bus.subscribe(EventType.SESSION_ENDED,   _on_session_ended)


def _startup_validation():
    """Log the status of every optional dependency and model artifact."""
    from pathlib import Path
    root = Path(__file__).parent.parent
    models = root / "models"

    checks = {
        "cv2":       lambda: __import__("cv2"),
        "mediapipe": lambda: __import__("mediapipe"),
        "torch":     lambda: __import__("torch"),
        "faster_whisper": lambda: __import__("faster_whisper"),
        "numpy":     lambda: __import__("numpy"),
        "psutil":    lambda: __import__("psutil"),
    }
    for name, fn in checks.items():
        try:
            fn()
            logger.info("  ✓ %s", name)
        except ImportError:
            logger.warning("  ✗ %s — not installed (some features degraded)", name)

    artifacts = {
        "DeBERTa checkpoint": models / "deberta" / "best" / "model.pt",
        "Fusion model":        models / "fusion" / "best_fusion.pt",
        "Confidence classifier": models / "classifiers" / "confidence_clf.pkl",
    }
    for label, path in artifacts.items():
        if path.exists():
            logger.info("  ✓ %s", label)
        else:
            logger.warning("  ✗ %s — not found at %s", label, path)

    try:
        import torch
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info(0)
            logger.info("  ✓ GPU: %s  VRAM %dMB / %dMB free",
                        torch.cuda.get_device_name(0),
                        free // 1_000_000, total // 1_000_000)
        else:
            logger.warning("  ✗ CUDA not available — inference on CPU")
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("── NeuroSync startup validation ─────────────────────────")
    try:
        from backend.startup.validator import validate_startup
        validate_startup()
    except Exception as _ve:
        logger.warning("Startup validation warning: %s", _ve)
    _startup_validation()
    logger.info("─────────────────────────────────────────────────────────")

    # Init SQLite schema (core + enterprise)
    from backend.services.db_service import init_db
    try:
        init_db()
        logger.info("Database initialised (SQLite WAL)")
    except Exception as exc:
        logger.error("Database init failed: %s", exc)

    from backend.services.enterprise_db import init_enterprise_db
    try:
        init_enterprise_db()
        logger.info("Enterprise DB schema initialised")
    except Exception as exc:
        logger.error("Enterprise DB init failed: %s", exc)

    from backend.behavioral_memory.repository import init_behavioral_db
    try:
        init_behavioral_db()
        logger.info("Behavioral memory DB schema initialised")
    except Exception as exc:
        logger.error("Behavioral memory DB init failed: %s", exc)

    from backend.behavioral_knowledge.repository import init_cbip_db
    try:
        init_cbip_db()
        logger.info("CBIP knowledge DB schema initialised")
    except Exception as exc:
        logger.error("CBIP knowledge DB init failed: %s", exc)

    from backend.connectors.schema import init_connectors_db
    try:
        init_connectors_db()
        logger.info("Connector DB schema initialised")
    except Exception as exc:
        logger.error("Connector DB init failed: %s", exc)

    from backend.uploads.schema import init_uploads_db
    try:
        init_uploads_db()
        logger.info("Upload jobs schema initialised")
    except Exception as exc:
        logger.error("Upload DB init failed: %s", exc)

    from backend.ats.schema import init_ats_db
    try:
        init_ats_db()
        logger.info("ATS schema initialised")
    except Exception as exc:
        logger.error("ATS DB init failed: %s", exc)

    # Pre-warm Whisper singleton so the first session doesn't pay cold-start
    try:
        from backend.services.audio_service import _get_shared_transcriber
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _get_shared_transcriber)
    except Exception as exc:
        logger.warning("Whisper pre-warm failed: %s", exc)

    # Wire event subscriptions
    _wire_event_subscriptions()
    logger.info("Event bus wired (%d subscriber types)", len(event_bus._handlers))

    # Log model registry catalog at startup
    logger.info("Model registry: %d models registered", len(model_registry.all()))
    for m in model_registry.all():
        logger.info("  ✓ model:%s  version=%s  status=%s", m.name, m.version, m.status)

    # Start background workers
    from backend.workers.cleanup_worker import create_cleanup_tasks
    cleanup_tasks = [asyncio.create_task(coro) for coro in create_cleanup_tasks()]

    # Upload analysis worker — drains the recording-upload queue off the event loop.
    from backend.uploads.worker import upload_worker_loop
    cleanup_tasks.append(asyncio.create_task(upload_worker_loop()))

    logger.info("NeuroSync backend ready — whisper/%s device:%s",
                settings.WHISPER_MODEL, settings.WHISPER_DEVICE)
    yield

    try:
        from backend.operations.graceful_shutdown import run_graceful_shutdown
        await run_graceful_shutdown(cleanup_tasks)
    except Exception as _se:
        logger.error("Graceful shutdown error: %s", _se)
        for t in cleanup_tasks:
            t.cancel()
    logger.info("NeuroSync backend shutting down.")


app = FastAPI(
    title="NeuroSync — Behavioral Intelligence Platform",
    version=settings.APP_VERSION,
    description="Real-time Multimodal Behavioral Analysis API · Powered by the MBA Engine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NeuroSyncError)
async def neurosync_error_handler(request: Request, exc: NeuroSyncError):
    """Convert typed domain errors to structured HTTP responses."""
    from backend.core.errors import (
        SessionNotFoundError, SessionExpiredError, SessionStateError,
        InsufficientSignalError, TranscriptUnavailableError,
        StorageError, RecordNotFoundError, ConfigurationError,
        InferenceTimeoutError, ModelUnavailableError,
    )
    status = 500
    if isinstance(exc, (SessionNotFoundError, RecordNotFoundError)):
        status = 404
    elif isinstance(exc, SessionExpiredError):
        status = 410
    elif isinstance(exc, (SessionStateError, InsufficientSignalError, TranscriptUnavailableError)):
        status = 409
    elif isinstance(exc, (InferenceTimeoutError, ModelUnavailableError)):
        status = 503
    elif isinstance(exc, ConfigurationError):
        status = 500

    return JSONResponse(
        status_code=status,
        content={
            "error":   exc.error_code,
            "message": str(exc),
            "context": exc.context,
        },
    )


import time
from collections import defaultdict

# In-memory rate limiter: 100 req / 60 s per IP.
# Bounded to _MAX_TRACKED_IPS entries — when exceeded, all fully-expired buckets
# are evicted lazily on the next request. Prevents unbounded memory growth under
# unique-IP floods (rotating NAT pools, bot traffic) without async scheduling.
_rate_limit_records: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_MAX = 100
RATE_LIMIT_WINDOW = 60
_MAX_TRACKED_IPS = 10_000

@app.middleware("http")
async def security_hardening_middleware(request: Request, call_next):
    try:
        from backend.security.hardening import security_middleware
        return await security_middleware(request, call_next)
    except Exception:
        return await call_next(request)


@app.middleware("http")
async def production_hardening_middleware(request: Request, call_next):
    # 1. Rate Limiting
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    # Slide window: discard timestamps outside the current window.
    _rate_limit_records[client_ip] = [t for t in _rate_limit_records[client_ip] if now - t < RATE_LIMIT_WINDOW]

    # Lazy eviction: purge all empty buckets when the dict exceeds the IP cap.
    if len(_rate_limit_records) > _MAX_TRACKED_IPS:
        expired = [ip for ip, ts in _rate_limit_records.items() if not ts]
        for ip in expired:
            del _rate_limit_records[ip]

    if len(_rate_limit_records[client_ip]) >= RATE_LIMIT_MAX:
        logger.warning("Rate limit exceeded for IP: %s", client_ip)
        return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
    
    _rate_limit_records[client_ip].append(now)

    # 2. Request Tracing
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    request.state.correlation_id = request_id

    # 3. Process Request
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error("Unhandled exception during request processing", exc_info=exc, extra={"correlation_id": request_id})
        response = JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    
    # 4. Security Headers
    response.headers["X-Request-ID"] = request_id
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"          # disable legacy IE XSS filter (exploitable; modern browsers ignore it)
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    
    return response


# ── Router registration ───────────────────────────────────────────────────────
#
# URL prefix convention (RC1):
#
#   /api/*         Core session pipeline — session, analytics, dataset,
#                  labeling, media, validation, training, history.
#                  Legacy prefix; RC2 will migrate these to /api/v1/*.
#
#   /api/v1/*      Enterprise platform — auth, governance, tenants, RBAC,
#                  compliance, audit. Official prefix for all NEW routers.
#
#   /ai/*          AI lifecycle — model registry, experiments, golden tests,
#                  drift monitor, calibration, replay.
#
#   /system/*      Infrastructure — health, readiness, version, metrics, config.
#
#   /behavior/*    ABME behavioral memory (candidate profiles, EMA).
#                  RC2: migrate to /api/v1/behavior/*.
#
#   /cbip/*        CBIP behavioral knowledge (archetypes, coaching, org intel).
#                  RC2: migrate to /api/v1/cbip/*.
#
#   /ws/*          WebSocket — live session streams.
#
#   /metrics, /health/live, /health/ready  — bare Prometheus / k8s probe paths
#                  (no prefix, served directly by the observability router).
#
# Rule: add new routers under /api/v1/. Do not introduce new prefix schemes.
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(session_router.router)
app.include_router(analytics_router.router)
app.include_router(ws_router.router)
app.include_router(history_router.router)
app.include_router(dataset_router.router)
app.include_router(labeling_router.router)
app.include_router(media_router.router)
app.include_router(validation_router.router)
app.include_router(training_router.router)
app.include_router(system_router.router)
app.include_router(ai_platform_router.router)
app.include_router(observability_router.router)
app.include_router(enterprise_auth_router.router)
app.include_router(enterprise_governance_router.router)
app.include_router(enterprise_platform_router.router)
app.include_router(connectors_router.router)
app.include_router(uploads_router.router)
app.include_router(capture_router.router)
app.include_router(ats_router.router)
app.include_router(_bm_router_module.router)
app.include_router(_bk_router_module.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "name": settings.APP_NAME,
        "engine": "MBA (Multimodal Behavioral Analysis)",
    }


@app.get("/")
async def root():
    return {
        "name": f"{settings.APP_NAME} — Behavioral Intelligence Platform",
        "version": settings.APP_VERSION,
        "engine": "MBA Engine",
        "docs": "/docs",
        "ws": "/ws/session/{session_id}",
        "endpoints": {
            "sessions": "/api/sessions",
            "dashboard": "/api/dashboard/stats",
            "health": "/api/health/detailed",
        },
    }
