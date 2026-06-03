"""Timezone utilities — all datetime I/O goes through this module.

Storage: always UTC (datetime.now(timezone.utc)).
Output:  Beijing time (+08:00) ISO strings, so the frontend can parse them correctly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


BEIJING_TZ = timezone(timedelta(hours=8))


def to_beijing_iso(dt: datetime | None) -> str:
    """Convert a UTC datetime to a Beijing-time ISO string with ``+08:00`` suffix.

    Naive datetimes are treated as UTC.
    """
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING_TZ).isoformat()


def beijing_today() -> str:
    """Return today's date string in Beijing time (``YYYY-MM-DD``)."""
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")


def beijing_now() -> datetime:
    """Return current datetime in the Beijing timezone."""
    return datetime.now(BEIJING_TZ)
