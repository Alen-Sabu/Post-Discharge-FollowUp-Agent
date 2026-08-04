from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- Protocol schemas ---

class ProtocolQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_text: str
    sort_order: int
    is_required: bool
    is_active: bool


class ProtocolEmergencyKeywordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keyword: str
    is_active: bool


class ProtocolResultFieldEnumRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    value: str
    sort_order: int


class ProtocolResultFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    field_key: str
    field_type: str
    description: str | None = None
    is_required: bool
    sort_order: int
    minimum: int | None = None
    maximum: int | None = None
    is_active: bool
    enums: list[ProtocolResultFieldEnumRead] = []


class DiseaseProtocolListItem(BaseModel):
    """Dropdown item for frontend."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None = None
    needs_followup_default: bool


class DiseaseProtocolDetail(BaseModel):
    """Full protocol preview + generated CALL-E schema."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None = None
    needs_followup_default: bool
    is_active: bool
    questions: list[ProtocolQuestionRead] = []
    emergency_keywords: list[ProtocolEmergencyKeywordRead] = []
    result_fields: list[ProtocolResultFieldRead] = []
    result_schema_preview: dict[str, Any] | None = None


# --- Patient schemas ---

class PatientCreate(BaseModel):
    name: str
    phone: str = Field(..., description="E.164 phone, eg: +912121234567")
    age: int | None = None
    gender: str | None = None
    doctor_name: str | None = None
    doctor_contact: str | None = None
    discharge_date: date | None = None
    discharge_diagnosis: str | None = None  # optional free-text note
    consent_on_file: bool = False
    protocol_id: int  # required from disease dropdown
    needs_followup: bool = False

    followup_scheduled_time: datetime | None = None


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
    protocol_id: int | None = None
    needs_followup: bool = False


# --- Follow-up / call / webhook schemas ---

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