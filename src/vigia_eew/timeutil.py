"""Shared local-time helpers (RF-40, RF-41, ADR-017).

Centralizes the "local calendar day" boundary computation shared by the freshness
filter (`pipeline/filter.py`, RF-40) and the REST backlog floor (`ingest/rest_usgs.py`,
`ingest/rest_geofon.py`, RF-41), so both stay consistent and the `ZoneInfo` fail-safe
handling isn't duplicated across modules.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

Clock = Callable[[], datetime]


def default_clock() -> datetime:
    """Default clock: the real current time (UTC). Overridden in tests for determinism."""
    return datetime.now(UTC)


def local_date(moment: datetime, timezone: str) -> date | None:
    """`moment` (any tz-aware datetime) converted to a calendar date in `timezone`.

    Returns `None` if `timezone` is invalid/unsupported (fail-safe, never raises).
    """
    try:
        tz = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return None
    return moment.astimezone(tz).date()


def local_midnight_ms(timezone: str, now: Clock) -> int | None:
    """Epoch ms of the most recent local midnight (00:00) in `timezone`.

    Returns `None` if `timezone` is invalid/unsupported — callers must treat that as
    "can't compute, don't apply the bound" (fail-safe, never raises).
    """
    try:
        tz = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return None
    local_now = now().astimezone(tz)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(local_midnight.astimezone(UTC).timestamp() * 1000)


def floor_starttime_ms(cursor_ms: int | None, timezone: str, now: Clock) -> int | None:
    """Bounds a REST poller's cursor at local midnight today (RF-41).

    Returns `cursor_ms` unchanged if it's already at/after that floor. Returns the
    floor itself when the cursor is `None` (fresh install) or older than the floor (a
    stale cursor after a long outage). Fail-safe passthrough: if the local midnight
    can't be computed (invalid timezone), `cursor_ms` is returned unchanged so query
    construction behaves exactly as it did before RF-41.
    """
    floor_ms = local_midnight_ms(timezone, now)
    if floor_ms is None:
        return cursor_ms
    if cursor_ms is None or cursor_ms < floor_ms:
        return floor_ms
    return cursor_ms
