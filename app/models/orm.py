from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    gender: Mapped[str] = mapped_column(String(50), nullable=True)
    doctor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doctor_contact: Mapped[str | None] = mapped_column(String(32), nullable=True)
    discharge_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    discharge_diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_risk_level: Mapped[str | None] = mapped_column(
        String(50), nullable=False, default="low"
    )
    consent_on_file: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    followups: Mapped[list["FollowUp"]] = relationship(
        "FollowUp",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    calls: Mapped[list["Call"]] = relationship(
        "Call",
        back_populates="patient",
        cascade="all, delete-orphan",
    )


class FollowUp(Base):
    __tablename__ = "followups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id"), nullable=False, index=True
    )
    scheduled_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="followups")
    calls: Mapped[list["Call"]] = relationship("Call", back_populates="followup")


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id"), nullable=False, index=True
    )
    followup_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("followups.id"), nullable=True, index=True
    )
    calle_call_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    call_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    call_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_emergency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="calls")
    followup: Mapped["FollowUp"] = relationship("FollowUp", back_populates="calls")
    symptoms: Mapped[list["Symptom"]] = relationship(
        "Symptom", back_populates="call", cascade="all, delete-orphan"
    )


class Symptom(Base):
    __tablename__ = "symptoms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    call_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("calls.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    call: Mapped["Call"] = relationship("Call", back_populates="symptoms")
