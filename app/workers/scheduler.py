from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.db import SessionLocal
from app.repositories.call_repository import CallRepository
from app.repositories.followup_repository import FollowUpRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.protocol_repository import ProtocolRepository
from app.services.call_service import CallService
from app.services.protocol_service import ProtocolService

scheduler = BackgroundScheduler()


def process_due_followups() -> None:
    db = SessionLocal()
    try:
        service = CallService(
            PatientRepository(db),
            FollowUpRepository(db),
            CallRepository(db),
            ProtocolService(ProtocolRepository(db)),
        )
        service.process_due_followups(dry_run=settings.dry_run_default)
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        process_due_followups,
        trigger="interval",
        minutes=10,
        id="due_followups",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
