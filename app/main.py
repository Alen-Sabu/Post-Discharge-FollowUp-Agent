from fastapi import FastAPI

from app.api.routes import calls, disease_protocols, followups, patients, webhooks

app = FastAPI(
    title="Post-Discharge Follow-Up Agent",
    version="0.1.0",
    description="A FastAPI application for post-discharge follow-up agent",
)

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
