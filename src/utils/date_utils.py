from datetime import datetime, time, timezone


def datetime_to_iso(dt: datetime) -> str:
    """Convert datetime to string with timezone."""

    if dt.tzname() is None:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="microseconds")


def time_to_iso(time_data: time) -> str:
    """Remove seconds from time."""

    return time_data.isoformat(timespec="minutes")
