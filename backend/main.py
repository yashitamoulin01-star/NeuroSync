"""
MBA — Multimodal Behavioral Analytics
FastAPI backend entry point.
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import settings
from backend.routers import session as session_router
from backend.routers import analytics as analytics_router
from backend.routers import ws_session as ws_router
from backend.routers import dataset as dataset_router
from backend.routers import labeling as labeling_router
from backend.routers import media as media_router
from backend.routers import validation as validation_router
from backend.routers import training as training_router

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mba")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MBA backend starting — model: whisper/%s device: %s",
                settings.WHISPER_MODEL, settings.WHISPER_DEVICE)
    yield
    logger.info("MBA backend shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Real-time Multimodal Behavioral Analytics API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router.router)
app.include_router(analytics_router.router)
app.include_router(ws_router.router)
app.include_router(dataset_router.router)
app.include_router(labeling_router.router)
app.include_router(media_router.router)
app.include_router(validation_router.router)
app.include_router(training_router.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "ws": "/ws/session/{session_id}",
    }
