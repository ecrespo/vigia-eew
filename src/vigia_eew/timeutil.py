"""Shared local-time helpers (RF-40, RF-41, ADR-017).

Centralizes the "local calendar day" boundary computation shared by the freshness
filter (`pipeline/filter.py`, RF-40) and the REST backlog floor (`ingest/rest_usgs.py`,
`ingest/rest_geofon.py`, RF-41), so both stay consistent and the `ZoneInfo` fail-safe
handling isn't duplicated across modules.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta, tzinfo
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


def local_day_bounds(
    first: date | None, last: date | None, timezone: str
) -> tuple[datetime | None, datetime | None]:
    """The UTC instants that bound a range of local calendar days, both inclusive.

    The history's date filter (REQ-HIS-007): the user picks days where they
    live, the history stores instants in UTC. `first` starts at its local
    midnight; `last` ends one microsecond before the next one, so that the
    bound can be used with `<=` and a day never claims the first instant of
    the following day. Either side may be `None`, meaning open.

    Raises `ValueError` if the range ends before it starts. An unknown
    `timezone` falls back to UTC days rather than to no filter -- the same
    fail-safe direction as the rest of this module: degrade, do not refuse.
    """
    if first is not None and last is not None and last < first:
        raise ValueError(f"the period ends ({last}) before it starts ({first})")
    zone: tzinfo
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        zone = UTC

    def midnight(day: date) -> datetime:
        return datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)

    since = None if first is None else midnight(first)
    until = None if last is None else midnight(last + timedelta(days=1)) - timedelta(microseconds=1)
    return since, until


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
