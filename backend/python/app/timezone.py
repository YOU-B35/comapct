"""Timezone helpers that also work in minimal Windows Python environments."""
from __future__ import annotations

from datetime import timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def load_shanghai_timezone() -> tzinfo:
    """Return China Standard Time even when the IANA timezone database is absent."""
    try:
        return ZoneInfo("Asia/Shanghai")
    except (ZoneInfoNotFoundError, OSError):
        # China currently has no daylight-saving transitions, so UTC+8 is a
        # correct operational fallback while tzdata is installed or repaired.
        return timezone(timedelta(hours=8), name="Asia/Shanghai")


SHANGHAI = load_shanghai_timezone()
