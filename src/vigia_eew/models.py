"""Data models (pydantic v2).

Implements the internal contract defined in `docs/DATA-MODEL.md`:
  - `SeismicEvent`: normalized seismic event (RF-07).
  - `AlertedId`, `EventSignature`, `AppState`: persisted state (RF-06, RF-10).
  - `classify_severity`: severity derivation by magnitude (RF-13).

Key invariant: every `datetime` is *tz-aware* in UTC. Conversion to local time
(America/Caracas) happens only in the presentation layer (RF-18, RNF-12).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# --- Domain type aliases ---
Source = Literal["EMSC", "USGS", "FUNVISIS", "GEOFON", "SIMULATED"]
SeverityLevel = Literal["info", "warning", "critical"]
Action = Literal["create", "update"]


def _require_utc(value: datetime | None) -> datetime | None:
    """Validates that a datetime is tz-aware and normalizes it to UTC.

    A *naive* datetime (without a timezone) is rejected to avoid time ambiguities,
    which would be dangerous in a seismic alert.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("The datetime must be tz-aware (include a timezone).")
    return value.astimezone(UTC)


def _require_aware_utc(value: datetime) -> datetime:
    """Same as `_require_utc` for a field that cannot be None.

    Written as a check rather than an `assert`: assertions are removed by
    `python -O`, and this one is the last thing standing between a naive
    datetime and the freshness rules that decide whether to alert.
    """
    validated = _require_utc(value)
    if validated is None:  # pragma: no cover - a required field is never None
        raise ValueError("a required timestamp cannot be None")
    return validated


def classify_severity(magnitude: float, info_max: float, warning_max: float) -> SeverityLevel:
    """Classifies the severity of an earthquake by its magnitude (RF-13).

    By default (config): `< info_max` -> info, `< warning_max` -> warning,
    otherwise -> critical. The thresholds are configurable (see `Settings`).
    """
    if magnitude < info_max:
        return "info"
    if magnitude < warning_max:
        return "warning"
    return "critical"


class SeismicEvent(BaseModel):
    """Normalized seismic event that flows between the agent's layers (RF-07)."""

    id: str
    #: Correlation id of the arrival this event came from (REQ-OBS-002,
    #: ADR-021). Internal only -- invariant I-4 keeps it out of every outgoing
    #: request. Defaulted so that constructing an event by hand, as the
    #: simulation and the tests do, does not have to invent one.
    trace_id: str = ""
    source: Source
    magnitude: float
    mag_type: str
    place: str | None = None
    region: str | None = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    depth_km: float = Field(ge=0)
    time_utc: datetime
    lastupdate_utc: datetime | None = None
    distance_km: float = Field(ge=0)
    severity: SeverityLevel
    action: Action = "create"

    @field_validator("time_utc", "lastupdate_utc")
    @classmethod
    def _validate_utc(cls, v: datetime | None) -> datetime | None:
        return _require_utc(v)

    @field_validator("mag_type")
    @classmethod
    def _normalize_magtype(cls, v: str) -> str:
        # EMSC uses `magtype` (lowercase) and USGS `magType` (camelCase); we unify them.
        return v.strip().lower()

    def signature(self) -> EventSignature:
        """Produces the signature used for inter-source deduplication (RF-09)."""
        return EventSignature(
            lat=self.lat,
            lon=self.lon,
            time_utc=self.time_utc,
            magnitude=self.magnitude,
            trace_id=self.trace_id,
        )


class EventSignature(BaseModel):
    """Minimal fingerprint of an event used to detect duplicates across sources (RF-09)."""

    lat: float
    lon: float
    time_utc: datetime
    magnitude: float
    #: Journey that alerted this signature, so a later arrival of the same
    #: earthquake can be linked to it instead of losing its own (REQ-OBS-002).
    #: Defaulted: state files written before v1.0 carry no trace ids.
    trace_id: str = ""

    @field_validator("time_utc")
    @classmethod
    def _validate_utc(cls, v: datetime) -> datetime:
        return _require_aware_utc(v)


class AlertedId(BaseModel):
    """Record of an already-alerted event, to avoid repeating it after restarts (RF-10)."""

    id: str
    source: str
    time_utc: datetime
    acknowledged_utc: datetime | None = None  # acknowledge audit trail (OBJ-1)
    #: See `EventSignature.trace_id`. Defaulted for state written before v1.0.
    trace_id: str = ""

    @field_validator("time_utc", "acknowledged_utc")
    @classmethod
    def _validate_utc(cls, v: datetime | None) -> datetime | None:
        return _require_utc(v)


class DetectedLocation(BaseModel):
    """IP-based location cached after the first successful detection (RF-33)."""

    name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    detected_utc: datetime

    @field_validator("detected_utc")
    @classmethod
    def _validate_utc(cls, v: datetime) -> datetime:
        return _require_aware_utc(v)


class AppState(BaseModel):
    """Persisted agent state (RF-06, RF-10). See `state.py`."""

    version: int = 1
    cursor_usgs_ms: int | None = None
    cursor_geofon_ms: int | None = None
    alerted_ids: list[AlertedId] = Field(default_factory=list)
    recent_signatures: list[EventSignature] = Field(default_factory=list)
    detected_location: DetectedLocation | None = None
