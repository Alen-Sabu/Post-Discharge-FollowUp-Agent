from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories.call_repository import CallRepository
from app.repositories.followup_repository import FollowUpRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.protocol_repository import ProtocolRepository
from app.repositories.symptom_repository import SymptomRepository
from app.services.call_service import CallService
from app.services.followup_service import FollowUpService
from app.services.patient_service import PatientService
from app.services.protocol_service import ProtocolService
from app.services.webhook_service import WebhookService


def get_patient_service(db: Session = Depends(get_db)) -> PatientService:
    return PatientService(
        PatientRepository(db),
        ProtocolRepository(db),
        FollowUpRepository(db),
    )


def get_followup_service(db: Session = Depends(get_db)) -> FollowUpService:
    return FollowUpService(FollowUpRepository(db), PatientRepository(db))


def get_call_service(db: Session = Depends(get_db)) -> CallService:
    return CallService(
        PatientRepository(db),
        FollowUpRepository(db),
        CallRepository(db),
        ProtocolService(ProtocolRepository(db))
    )


def get_webhook_service(db: Session = Depends(get_db)) -> WebhookService:
    return WebhookService(
        CallRepository(db),
        PatientRepository(db),
        SymptomRepository(db),
        ProtocolService(ProtocolRepository(db))
    )


def get_protocol_service(db: Session = Depends(get_db)) -> ProtocolService:
    return ProtocolService(ProtocolRepository(db))
