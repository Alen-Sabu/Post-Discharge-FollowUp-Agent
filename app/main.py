from fastapi import FastAPI

from app.api.routes import calls, followups, patients, webhooks

app = FastAPI(
    title="Post-Discharge Follow-Up Agent",
    version="0.1.0",
    description="A FastAPI application for post-discharge follow-up agent",
)

app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(calls.router, prefix="/calls", tags=["calls"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(followups.router, prefix="/followups", tags=["followups"])


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
