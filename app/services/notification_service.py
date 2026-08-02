from app.integrations import twilio as twilio_client


def notify_emergency(*, patient, call) -> None:
    to_number = getattr(patient, "doctor_contact", None)
    body = (
        f"EMERGENCY follow-up alert\n"
        f"Patient: {getattr(patient, 'name', 'unknown')} "
        f"(id={getattr(patient, 'id', None)})\n"
        f"Phone: {getattr(patient, 'phone', 'n/a')}\n"
        f"Risk: {getattr(call, 'risk_level', 'critical')}\n"
        f"Call id: {getattr(call, 'id', None)}\n"
        f"Summary: {getattr(call, 'summary', '') or 'n/a'}"
    )

    if not to_number:
        print(f"No doctor contact for patient {getattr(patient, 'id', None)}")
        return

    twilio_client.send_sms(to=to_number, body=body)
