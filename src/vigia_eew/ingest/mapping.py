"""Shared parsing helpers for the source mappings (API-SPEC §5.1).

Each source module owns its own translation into the internal contract -- the
anti-corruption layer belongs with the adapter that speaks the foreign
language. What they share is the small vocabulary of coercions their formats
keep needing: ISO-8601, epoch milliseconds, Venezuelan local time, a depth
written as ``"32.0 km"``.

Every function here either returns a tz-aware UTC datetime or raises. Naive
values are rejected by `SeismicEvent` anyway; failing at the edge names the
source in the log instead of the model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

#: FUNVISIS publishes Venezuelan local time with no offset (RF-38).
VENEZUELA_TZ = ZoneInfo("America/Caracas")


def parse_iso(value: Any) -> datetime:
    """Parses an ISO-8601 timestamp (EMSC, GEOFON) into a tz-aware UTC datetime."""
    if not isinstance(value, str):
        raise ValueError(f"ISO timestamp is not text: {value!r}")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)  # accepts variable-length fractional seconds
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_iso_optional(value: Any) -> datetime | None:
    return parse_iso(value) if value is not None else None


def epoch_ms_to_utc(value: Any) -> datetime:
    """Converts epoch milliseconds (USGS) into a tz-aware UTC datetime."""
    if not isinstance(value, int | float):
        raise ValueError(f"epoch ms is not numeric: {value!r}")
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def epoch_ms_optional(value: Any) -> datetime | None:
    return epoch_ms_to_utc(value) if value is not None else None


def venezuela_time(date: Any, time: Any) -> datetime:
    """Combines FUNVISIS local date (`DD-MM-YYYY`) and time (`HH:MM`) into UTC."""
    if not isinstance(date, str) or not isinstance(time, str):
        raise ValueError(f"FUNVISIS date/time not text: {date!r} {time!r}")
    local = datetime.strptime(f"{date.strip()} {time.strip()}", "%d-%m-%Y %H:%M")
    return local.replace(tzinfo=VENEZUELA_TZ).astimezone(UTC)


def parse_km(value: Any) -> float:
    """Parses a FUNVISIS depth string like ``"32.0 km"`` into kilometres."""
    if not isinstance(value, str):
        raise ValueError(f"depth is not text: {value!r}")
    parts = value.strip().split()
    if not parts:
        raise ValueError("depth is empty")
    return float(parts[0])


def clean_text(value: Any) -> str | None:
    """Collapses the runs of spaces FUNVISIS and GEOFON pad their names with."""
    if not isinstance(value, str):
        return None
    return " ".join(value.split()) or None
