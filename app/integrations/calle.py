from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from calle import CalleClient
from calle.errors import CalleWebhookSignatureError

from app.config import settings
from app.models.orm import FollowUp, Patient


FOLLOWUP_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "feeling_overall",
        "pain_level",
        "medication_compliance",
        "emergency_symptoms_reported",
        "notes",
    ],
    "properties": {
        "feeling_overall": {
            "type": "string",
            "description": "How the patient says they feel overall.",
            "enum": ["better", "same", "worse", "unknown"],
        },
        "pain_level": {
            "type": "string",
            "description": "How much pain the patient is experiencing, on a scale of 0 to 10",
            "minimum": 0,
            "maximum": 10,
        },
        "medication_compliance": {
            "type": "string",
            "description": "Whether the patient is taking their medications as prescribed",
            "enum": ["yes", "partial", "no", "unknown"],
        },
        "emergency_symptoms_reported": {
            "type": "boolean",
            "description": (
                "True if the patient reports emergency symptoms such as chest pain, "
                "severe shortness of breath, or confusion."
            ),
        },
        "notes": {
            "type": "string",
            "description": "Short clinical notes from the conversation.",
        },
    },
}


@dataclass
class CallEResult:
    provider_call_id: str | None
    status: str
    dry_run: bool
    raw_response: dict[str, Any] = field(default_factory=dict)


def _get_client() -> CalleClient:
    return CalleClient(
        api_key=settings.calle_api_key,
        base_url=settings.calle_base_url,
    )


def _infer_region(phone: str) -> str:
    if phone.startswith("+91"):
        return "IN"
    if phone.startswith("+1"):
        return "US"
    return "IN"


def _build_task(patient: Patient) -> str:
    diagnosis = patient.discharge_diagnosis or "a recent hospital discharge"
    doctor = patient.doctor_name or "their care team"
    discharge = (
        patient.discharge_date.isoformat()
        if patient.discharge_date
        else "recently"
    )

    return (
        f"Call {patient.phone}. You are a hospital post-discharge follow-up assistant "
        f"calling on behalf of {doctor}. "
        f"The patient's name is {patient.name}. They were discharged on {discharge} "
        f"after {diagnosis}. "
        "Be warm, brief, and clear. Confirm you are speaking with the patient. "
        "Ask how they are feeling overall, whether they have pain (0-10), whether they "
        "are taking medications as prescribed, and whether they have any concerning "
        "symptoms such as chest pain, severe shortness of breath, fainting, or confusion. "
        "If they report emergency symptoms, advise them to seek urgent care / emergency "
        "services and end the call politely. "
        "Do not diagnose or prescribe. Keep the call under 3 minutes."
    )


def place_call(
    patient: Patient,
    followup: FollowUp | None = None,
    *,
    dry_run: bool | None = None,
    internal_call_id: int | None = None,
    webhook_url: str | None = None,
) -> CallEResult:
    """Place a CALL-E follow up call for a patient."""
    if dry_run is None:
        dry_run = settings.dry_run_default

    if not patient.consent_on_file and not dry_run:
        raise ValueError("Patient has not given consent to be called")

    metadata = {
        "purpose": "post_discharge_followup",
        "patient_id": str(patient.id),
        "followup_id": str(followup.id) if followup else None,
        "internal_call_id": str(internal_call_id) if internal_call_id else None,
    }

    if dry_run:
        fake_id = f"dryrun_{uuid4().hex[:12]}"
        return CallEResult(
            provider_call_id=fake_id,
            status="dry_run",
            dry_run=True,
            raw_response={
                "id": fake_id,
                "status": "dry_run",
                "metadata": metadata,
                "message": "Dry run only — no CALL-E request was sent.",
            },
        )

    resolved_webhook = webhook_url or settings.calle_webhook_url

    client = _get_client()
    response = client.calls.create(
        task=_build_task(patient),
        recipients=[
            {
                "phones": [patient.phone],
                "region": _infer_region(patient.phone),
                "locale": "en-IN" if patient.phone.startswith("+91") else "en-US",
            }
        ],
        result_schema=FOLLOWUP_RESULT_SCHEMA,
        metadata=metadata,
        webhook_url=resolved_webhook,
        idempotency_key=(
            f"followup-{followup.id}-{internal_call_id}"
            if followup and internal_call_id
            else f"patient-{patient.id}-{uuid4().hex[:8]}"
        ),
    )

    return CallEResult(
        provider_call_id=str(response["id"]) if response.get("id") else None,
        status=str(response.get("status", "queued")),
        dry_run=False,
        raw_response=response,
    )


def unwrap_webhook(raw_body: bytes, headers: dict[str, str], secret: str) -> dict[str, Any]:
    """Verify and unwrap a CALL-E webhook payload. Raises CalleWebhookSignatureError."""
    client = CalleClient(
        api_key=settings.calle_api_key,
        base_url=settings.calle_base_url,
    )
    return client.webhooks.unwrap(
        raw_body=raw_body,
        headers=headers,
        secret=secret,
    )


# Re-export for callers that catch signature errors
__all__ = [
    "CallEResult",
    "CalleWebhookSignatureError",
    "FOLLOWUP_RESULT_SCHEMA",
    "place_call",
    "unwrap_webhook",
]
