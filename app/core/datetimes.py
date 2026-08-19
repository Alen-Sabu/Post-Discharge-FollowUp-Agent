from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """UTC clock time with tzinfo stripped for timezone-naive DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(value: datetime | None) -> datetime:
    """Normalize a datetime to naive UTC so Postgres TIMESTAMP does not shift to IST."""
    if value is None:
        return utc_now_naive()
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return value.astimezone(timezone.utc).replace(tzinfo=None)
