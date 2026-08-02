from twilio.rest import Client

from app.config import settings


def send_sms(*, to: str, body: str) -> None:
    if not (
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_from_number
    ):
        print("Twilio credentials not configured")
        return

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    client.messages.create(
        to=to,
        from_=settings.twilio_from_number,
        body=body[:1500],
    )
