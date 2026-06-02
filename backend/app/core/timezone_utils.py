"""时间格式化工具。"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta


BEIJING_TZ = timezone(timedelta(hours=8))


def to_beijing_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BEIJING_TZ).isoformat()
