from app.models.orm import Patient
from app.models.schemas import PatientCreate
from app.repositories.patient_repository import PatientRepository
from app.utils.validators import is_valid_e164


class PatientServiceError(Exception):
    """Domain/service error for patient operations."""


class PatientService:
    def __init__(self, patients: PatientRepository):
        self.patients = patients

    def create(self, payload: PatientCreate) -> Patient:
        if not is_valid_e164(payload.phone):
            raise PatientServiceError(
                "phone must be a valid E.164 number, eg: +912121234567"
            )

        patient = Patient(
            name=payload.name,
            phone=payload.phone,
            age=payload.age,
            gender=payload.gender,
            doctor_name=payload.doctor_name,
            doctor_contact=payload.doctor_contact,
            discharge_date=payload.discharge_date,
            discharge_diagnosis=payload.discharge_diagnosis,
            consent_on_file=payload.consent_on_file,
            current_risk_level="low",
        )
        return self.patients.create(patient)

    def list(self) -> list[Patient]:
        return self.patients.list_all()

    def get(self, patient_id: int) -> Patient:
        patient = self.patients.get_by_id(patient_id)
        if not patient:
            raise PatientServiceError("Patient not found")
        return patient

