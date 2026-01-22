from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "America/Mexico_City"

def get_tz(tz_name: str | None):
    """Return a tzinfo for tz_name.

    On Windows, IANA tz database may be unavailable unless `tzdata` is installed.
    We fall back safely to UTC to avoid breaking the app.
    """
    name = tz_name or DEFAULT_TZ
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ModuleNotFoundError):
        # Fallback: Mexico City is UTC-06 year-round (no DST since 2022)
        if name == 'America/Mexico_City':
            return timezone(timedelta(hours=-6))
        return timezone.utc


def local_naive_to_utc_naive(dt_local_naive: datetime, tz_name: str | None = None) -> datetime:
    """Interpret a naive datetime as local time in tz_name and convert to naive UTC."""
    tz = get_tz(tz_name)
    aware = dt_local_naive.replace(tzinfo=tz)
    utc = aware.astimezone(timezone.utc)
    return utc.replace(tzinfo=None)

def utc_naive_to_local_naive(dt_utc_naive: datetime, tz_name: str | None = None) -> datetime:
    """Interpret a naive datetime as UTC and convert to local naive datetime in tz_name."""
    tz = get_tz(tz_name)
    aware = dt_utc_naive.replace(tzinfo=timezone.utc)
    local = aware.astimezone(tz)
    return local.replace(tzinfo=None)

def fmt_dt_local(dt_utc_naive: datetime | None, tz_name: str | None = None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    if not dt_utc_naive:
        return ""
    local = utc_naive_to_local_naive(dt_utc_naive, tz_name)
    return local.strftime(fmt)

def fmt_dt_input_local(dt_utc_naive: datetime | None, tz_name: str | None = None) -> str:
    """Format UTC-naive datetime for HTML <input type=datetime-local> in local tz."""
    if not dt_utc_naive:
        return ""
    local = utc_naive_to_local_naive(dt_utc_naive, tz_name)
    return local.strftime("%Y-%m-%dT%H:%M")
