from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.orm import Call, Symptom
from app.repositories.call_repository import CallRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.symptom_repository import SymptomRepository
from app.services.ai_service import analyze_transcript
from app.services.notification_service import notify_emergency

_PROCESSED_EVENT_IDS: set[str] = set()

RISK_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

TERMINAL_TYPES = {
    "call.completed",
    "call.failed",
    "call.result_validation_failed",
}


class WebhookServiceError(Exception):
    """Domain/service error while processing webhooks."""


def _flatten_transcript(data: dict[str, Any]) -> str:
    lines: list[str] = []
    recipients = data.get("recipients", [])
    if not isinstance(recipients, list):
        return ""

    for recipient in recipients:
        if not isinstance(recipient, dict):
            continue

        attempts = recipient.get("attempts", [])
        if not isinstance(attempts, list):
            continue

        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue

            turns = attempt.get("transcript_turns", [])
            if not isinstance(turns, list):
                continue

            for turn in turns:
                if not isinstance(turn, dict):
                    continue
                text = turn.get("text", "").strip()
                if not text:
                    continue

                speaker = turn.get("speaker") or "unknown"
                lines.append(f"{speaker}: {text}")

    return "\n".join(lines)


def _is_worse(new_level: str, current_level: str | None) -> bool:
    return RISK_RANK.get((new_level or "").lower(), 0) > RISK_RANK.get(
        (current_level or "").lower(), 0
    )


def _first_recipient_structured_result(data: dict[str, Any]) -> dict[str, Any] | None:
    recipients = data.get("recipients", [])
    if not isinstance(recipients, list):
        return None

    for recipient in recipients:
        if isinstance(recipient, dict) and isinstance(recipient.get("structured_result"), dict):
            return recipient["structured_result"]
    return None


class WebhookService:
    def __init__(
        self,
        calls: CallRepository,
        patients: PatientRepository,
        symptoms: SymptomRepository,
    ):
        self.calls = calls
        self.patients = patients
        self.symptoms = symptoms

    def _find_call(self, data: dict[str, Any]) -> Call | None:
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        internal_call_id = metadata.get("internal_call_id")
        if internal_call_id is not None:
            try:
                call = self.calls.get_by_id(int(internal_call_id))
                if call:
                    return call
            except (TypeError, ValueError):
                pass

        provider_call_id = data.get("id")
        if provider_call_id:
            return self.calls.get_by_provider_id(str(provider_call_id))

        return None

    def process_calle_event(self, event_id: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        if event_id in _PROCESSED_EVENT_IDS:
            return {"ok": True, "duplicate": True, "event_id": event_id}

        if event_type not in TERMINAL_TYPES:
            return {"ok": True, "ignored": True, "event_type": event_type}

        call = self._find_call(data)
        if not call:
            raise WebhookServiceError("matching call record not found")

        _PROCESSED_EVENT_IDS.add(event_id)

        call.calle_call_id = str(data.get("id") or call.calle_call_id)
        call.status = str(data.get("status") or call.status)
        if data.get("completed_at"):
            try:
                call.call_end = datetime.fromisoformat(
                    str(data["completed_at"]).replace("Z", "+00:00")
                )
            except ValueError:
                call.call_end = datetime.now(timezone.utc)
        else:
            call.call_end = datetime.now(timezone.utc)

        if data.get("summary"):
            call.summary = data["summary"]

        transcript = _flatten_transcript(data)
        call.transcript = transcript or call.transcript

        if event_type == "call.failed" or call.status in {"failed", "canceled"}:
            self.calls.save(call)
            return {
                "ok": True,
                "event_id": event_id,
                "call_id": call.id,
                "status": call.status,
                "event_type": event_type,
            }

        structured_result = data.get("structured_result")
        if structured_result is None:
            structured_result = _first_recipient_structured_result(data)

        analysis = analyze_transcript(
            transcript=transcript,
            structured_result=structured_result if isinstance(structured_result, dict) else None,
        )

        call.summary = analysis.summary or call.summary
        call.risk_score = analysis.risk_score
        call.risk_level = analysis.risk_level
        call.is_emergency = analysis.is_emergency

        symptom_rows = [
            Symptom(
                call_id=call.id,
                name=item.name,
                severity=item.severity,
                note=item.note,
            )
            for item in analysis.symptoms
        ]
        self.symptoms.replace_for_call(call.id, symptom_rows)

        patient = self.patients.get_by_id(call.patient_id)
        if patient and _is_worse(analysis.risk_level, patient.current_risk_level):
            patient.current_risk_level = analysis.risk_level
            self.patients.save(patient)

        self.calls.save(call)

        if call.is_emergency and patient is not None:
            notify_emergency(patient=patient, call=call)

        return {
            "ok": True,
            "event_id": event_id,
            "call_id": call.id,
            "type": event_type,
            "risk_level": call.risk_level,
            "is_emergency": call.is_emergency,
        }
