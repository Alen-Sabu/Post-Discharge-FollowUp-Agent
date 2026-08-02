from datetime import datetime, timezone

from app.integrations.calle import place_call
from app.models.orm import Call
from app.repositories.call_repository import CallRepository
from app.repositories.followup_repository import FollowUpRepository
from app.repositories.patient_repository import PatientRepository


class TriggerError(Exception):
    """Domain error while triggering a follow-up call."""


class CallService:
    def __init__(
        self,
        patients: PatientRepository,
        followups: FollowUpRepository,
        calls: CallRepository,
    ):
        self.patients = patients
        self.followups = followups
        self.calls = calls

    def trigger(
        self,
        *,
        patient_id: int,
        followup_id: int | None = None,
        dry_run: bool = True,
    ) -> Call:
        patient = self.patients.get_by_id(patient_id)
        if not patient:
            raise TriggerError("Patient not found")

        followup = None
        if followup_id is not None:
            followup = self.followups.get_for_patient(followup_id, patient.id)
            if not followup:
                raise TriggerError("Follow-up not found for this patient")

        if not patient.consent_on_file and not dry_run:
            raise TriggerError("Patient has not provided consent")

        call = Call(
            patient_id=patient.id,
            followup_id=followup.id if followup else None,
            status="queued",
            dry_run=dry_run,
            call_start=datetime.now(timezone.utc),
        )
        call = self.calls.create(call)

        try:
            result = place_call(
                patient=patient,
                followup=followup,
                dry_run=dry_run,
                internal_call_id=call.id,
            )
        except Exception as exc:
            call.status = "failed"
            self.calls.save(call)
            raise TriggerError(str(exc)) from exc

        call.calle_call_id = result.provider_call_id
        call.status = result.status
        call.dry_run = result.dry_run
        return self.calls.save(call)

    def list(self) -> list[Call]:
        return self.calls.list_all()

    def get(self, call_id: int) -> Call:
        call = self.calls.get_by_id(call_id)
        if not call:
            raise TriggerError("call not found")
        return call

    def process_due_followups(self, *, dry_run: bool) -> None:
        now = datetime.now(timezone.utc)
        due = self.followups.get_due(now, limit=20)

        for followup in due:
            followup.status = "in_progress"
            followup.attempt_count += 1
            self.followups.save(followup)

            try:
                self.trigger(
                    patient_id=followup.patient_id,
                    followup_id=followup.id,
                    dry_run=dry_run,
                )
                followup.status = "completed"
                self.followups.save(followup)
            except TriggerError:
                if followup.attempt_count >= followup.max_attempts:
                    followup.status = "failed"
                else:
                    followup.status = "pending"
                self.followups.save(followup)
