from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    name: str
    phone: str = Field(..., description="E.164 phone, eg: +912121234567")
    age: int | None = None 
    gender: str | None = None 
    doctor_name: str | None = None 
    doctor_contact: str | None = None 
    discharge_date: date | None = None 
    discharge_diagnosis: str | None = None 
    consent_on_file: bool = False

class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    age: int | None = None
    gender: str | None = None
    doctor_name: str | None = None
    doctor_contact: str | None = None
    discharge_date: date | None = None
    discharge_diagnosis: str | None = None
    current_risk_level: str
    consent_on_file: bool


class FollowUpCreate(BaseModel):
    patient_id: int
    scheduled_time: datetime
    max_attempts: int = 3

class FollowUpRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    scheduled_time: datetime
    status: str
    attempt_count: int
    max_attempts: int

class CallTriggerRequest(BaseModel):
    patient_id: int
    followup_id: int | None = None
    dry_run: bool = True

class SymptomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str
    severity: str | None = None
    note: str | None = None

class CallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    followup_id: int | None = None
    calle_call_id: str | None = None
    status: str
    summary: str | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    is_emergency: bool
    transcript: str | None = None
    dry_run: bool
    symptoms: list[SymptomRead] = []


class TranscriptTurn(BaseModel):
    model_config = ConfigDict(extra="allow")

    offset_seconds: int | None = None
    speaker: str | None = None
    text: str | None = None


class CalleWebhookData(BaseModel):
    """Terminal call task object under event.data."""
    model_config = ConfigDict(extra="allow")

    id: str
    object: str | None = None
    status: str | None = None
    task: str | None = None
    recipients: list[dict[str, Any]] = []
    structured_result: dict[str, Any] | None = None
    summary: str | None = None
    task_completed: bool | None = None
    metadata: dict[str, Any] | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class CalleWebhookEvent(BaseModel):
    """Top-level CALL-E webhook event envelope."""
    model_config = ConfigDict(extra="allow")

    id: str
    type: str  # call.completed | call.failed | call.result_validation_failed
    created_at: str | None = None
    data: CalleWebhookData