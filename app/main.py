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
from app.workers.embedder import embed_all_missing
from app.workers.scheduler import start_scheduler, stop_scheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


async def _run_embedding_backfill() -> None:
    try:
        await asyncio.to_thread(embed_all_missing)
        logger.info("Embedding backfill completed")
    except Exception:
        logger.exception("Embedding backfill failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_scheduler()
    logger.info("Follow-up scheduler started")

    embedding_task = asyncio.create_task(_run_embedding_backfill())
    logger.info("Local embedding backfill started")

    try:
        yield
    finally:
        if not embedding_task.done():
            embedding_task.cancel()
        stop_scheduler()
        logger.info("Follow-up scheduler stopped")


app = FastAPI(
    title="Post-Discharge Follow-Up Agent",
    version="0.1.0",
    description="A FastAPI application for post-discharge follow-up agent",
    lifespan=lifespan,
)

# Allow local Next.js frontend to call the API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(agent.router, prefix="/agent", tags=["agent"])
app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(calls.router, prefix="/calls", tags=["calls"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(followups.router, prefix="/followups", tags=["followups"])
app.include_router(disease_protocols.router, prefix="/protocols", tags=["protocols"])

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}

@app.get("/", tags=["root"])
async def root():
    return {"message": "Post-Discharge Follow-Up Agent"}
