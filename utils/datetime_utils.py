from datetime import datetime, timezone, timedelta


def utc_now() -> datetime:
    """Returns the current time in UTC with tzinfo."""
    return datetime.now(timezone.utc)


def utc_in(minutes: int = 0, days: int = 0) -> datetime:
    """Returns a future time in UTC offset by given minutes or days."""
    return datetime.now(timezone.utc) + timedelta(minutes=minutes, days=days)
