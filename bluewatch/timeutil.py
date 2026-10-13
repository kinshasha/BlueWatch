"""Timestamp normalization for storage/API boundaries.

BlueWatch historically stored naive datetimes in the server's local timezone.
Keep reading those values for backwards compatibility, but emit explicit UTC
timestamps so clients in another timezone cannot reinterpret them.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, tzinfo
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def _resolve_timezone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown legacy timezone %r; falling back to UTC", name)
        return timezone.utc


def legacy_timezone() -> tzinfo:
    """Return the timezone used by pre-UTC database timestamps.

    BLUEWATCH_LEGACY_TIMEZONE should be set explicitly when migrating a
    database. Falling back to TZ preserves the existing container behavior.
    """
    name = os.environ.get("BLUEWATCH_LEGACY_TIMEZONE") or os.environ.get("TZ") or "UTC"
    return _resolve_timezone(name)


def _as_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def as_utc(value: datetime | str) -> datetime:
    """Interpret legacy naive values in the configured server timezone."""
    value = _as_datetime(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=legacy_timezone())
    return value.astimezone(timezone.utc)


def serialize_timestamp(value: datetime | str | None) -> str | None:
    """Serialize a timestamp as an explicit UTC ISO-8601 value for clients."""
    if value is None:
        return None
    return as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def serialize_utc_timestamp(value: datetime | str | None) -> str | None:
    """Serialize a value whose naive form was written by SQLite in UTC."""
    if value is None:
        return None
    parsed = _as_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
