from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from app.api.routes import (
    agent,
    auth,
    calls,
    dashboard,
    disease_protocols,
    followups,
    patients,
    webhooks,
)
from app.config import settings
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from app.db import check_db
from app.workers.embedder import embed_all_missing
from app.workers.scheduler import start_scheduler, stop_scheduler
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

logger = logging.getLogger(__name__)


async def _run_embedding_backfill() -> None:
    try:
        await asyncio.to_thread(embed_all_missing)
        logger.info("Embedding backfill completed")
    except Exception:
        logger.exception("Embedding backfill failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    scheduler_started = False 
    embedding_task: asyncio.Task | None = None 

    if settings.scheduler_enabled: 
        start_scheduler()
        scheduler_started = True
        logger.info("Follow-up scheduler started")
    else: 
        logger.info("Follow-up scheduler disabled")

    if settings.embedding_backfill_enabled: 
        embedding_task = asyncio.create_task(_run_embedding_backfill())
        logger.info("Local embedding backfill started")
    else: 
        logger.info("Embedding backfill disabled") 

    try:
        yield
    finally:
        if embedding_task is not None and not embedding_task.done():
            embedding_task.cancel()
            logger.info("Embedding backfill cancelled")

        if scheduler_started:
            stop_scheduler()
            logger.info("Follow-up scheduler stopped")

def create_app() -> FastAPI: 
    configure_logging()

    application = FastAPI(
        title="Post-Discharge Follow-Up Agent",
        version="0.1.0",
        description="A FastAPI application for post-discharge follow-up agent",
        lifespan=lifespan,
    )


    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(SecurityHeadersMiddleware)
    if settings.force_https_enabled:
        application.add_middleware(HTTPSRedirectMiddleware)
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts
    )

    application.include_router(auth.router, prefix="/auth", tags=["auth"])
    application.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
    application.include_router(agent.router, prefix="/agent", tags=["agent"])
    application.include_router(patients.router, prefix="/patients", tags=["patients"])
    application.include_router(calls.router, prefix="/calls", tags=["calls"])
    application.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
    application.include_router(followups.router, prefix="/followups", tags=["followups"])
    application.include_router(disease_protocols.router, prefix="/protocols", tags=["protocols"])

    @application.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok"}

    @application.get("/health/ready", tags=["health"])
    async def health_ready(response: Response):
        try:
            check_db()
        except Exception:
            logger.exception("Readiness check failed")
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready", "database": "down"}
        return {"status": "ready", "database": "up", "env": settings.app_env}

    @application.get("/", tags=["root"])
    async def root():
        return {"message": "Post-Discharge Follow-Up Agent"}
        
    return application

app = create_app()