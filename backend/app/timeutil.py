"""East Asia (UTC+8) helpers. Storage remains UTC; API emits Z-suffixed ISO."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc
EAST_ASIA = timezone(timedelta(hours=8))


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_east_asia(dt: datetime) -> datetime:
    return as_utc(dt).astimezone(EAST_ASIA)


def utc_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return as_utc(dt).isoformat().replace("+00:00", "Z")
