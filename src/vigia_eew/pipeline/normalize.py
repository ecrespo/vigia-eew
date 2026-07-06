"""Event normalizer (RF-07, RF-08, RF-13; mapping in API-SPEC §5.1).

`Normalizer` translates a `RawMessage` (raw EMSC, USGS, FUNVISIS, or GEOFON payload) into
the common `SeismicEvent` that flows through the rest of the pipeline. It resolves the
differences between sources:

  - EMSC: lowercase `magtype`, ISO-8601 timestamps, id in `properties.unid`,
    coordinates in `properties`.
  - USGS: camelCase `magType`, epoch-ms timestamps, id on the Feature itself,
    coordinates in `geometry.coordinates` [lon, lat, depth].
  - FUNVISIS (Venezuela-only): a repurposed GeoJSON schema (`phone`=magnitude,
    `phoneFormatted`=depth, `city`=local time, `postalCode`=local date), local
    Venezuela time (VET) converted to UTC, synthetic id injected by the poller.
  - GEOFON: FDSN `format=text`, pre-split by the poller into a `{column: value}` dict
    (all string values), ISO-8601 timestamps, id in `EventID`, `Depth/km` column.

It computes the **derived** fields (`distance_km` via haversine, `severity` via
thresholds) and requires timestamps to end up tz-aware in UTC (enforced by
`SeismicEvent`). On invalid raw input it logs and returns `None` (discard without
aborting, RNF-03).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from vigia_eew.config import ReferencePoint, Severity
from vigia_eew.geo import haversine_km
from vigia_eew.ingest import RawMessage
from vigia_eew.models import Action, SeismicEvent, classify_severity


class Normalizer:
    """Converts `RawMessage` into `SeismicEvent`, resolving the mapping per source."""

    def __init__(
        self,
        reference: ReferencePoint,
        severity: Severity,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._reference = reference
        self._severity = severity
        self._log = logger or logging.getLogger("vigia_eew.pipeline.normalize")

    def normalize(self, msg: RawMessage) -> SeismicEvent | None:
        """Normalizes a raw message into a `SeismicEvent`; returns None if invalid."""
        try:
            if msg.source == "EMSC":
                fields = self._map_emsc(msg)
            elif msg.source == "USGS":
                fields = self._map_usgs(msg)
            elif msg.source == "FUNVISIS":
                fields = self._map_funvisis(msg)
            elif msg.source == "GEOFON":
                fields = self._map_geofon(msg)
            else:
                self._log.warning("normalize_unknown_source source=%s", msg.source)
                return None
            return self._build(fields, msg.action)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            self._log.warning(
                "normalize_discarded source=%s type=%s detail=%s",
                msg.source,
                type(exc).__name__,
                exc,
            )
            return None

    def _map_emsc(self, msg: RawMessage) -> dict[str, Any]:
        p = msg.feature["properties"]
        return {
            "id": str(p["unid"]),
            "source": "EMSC",
            "magnitude": float(p["mag"]),
            "mag_type": str(p["magtype"]),
            "place": p.get("flynn_region"),
            "region": p.get("flynn_region"),
            "lat": float(p["lat"]),
            "lon": float(p["lon"]),
            "depth_km": float(p["depth"]),
            "time_utc": _parse_iso(p["time"]),
            "lastupdate_utc": _parse_iso_optional(p.get("lastupdate")),
        }

    def _map_usgs(self, msg: RawMessage) -> dict[str, Any]:
        p = msg.feature["properties"]
        coords = msg.feature["geometry"]["coordinates"]
        return {
            "id": str(msg.feature["id"]),
            "source": "USGS",
            "magnitude": float(p["mag"]),
            "mag_type": str(p["magType"]),
            "place": p.get("place"),
            "region": None,  # USGS does not expose a Flynn region; deriving it is out of v1 scope.
            "lat": float(coords[1]),
            "lon": float(coords[0]),
            "depth_km": float(coords[2]),
            "time_utc": _epoch_ms_to_utc(p["time"]),
            "lastupdate_utc": _epoch_ms_optional(p.get("updated")),
        }

    def _map_funvisis(self, msg: RawMessage) -> dict[str, Any]:
        # FUNVISIS `maravilla.json` reuses fields from an unrelated template
        # (Venezuela-only, see ingest/rest_funvisis.py): `phone`=magnitude,
        # `phoneFormatted`=depth ("32.0 km"), `city`=local time ("09:39"),
        # `postalCode`=local date ("05-07-2026"), `address`=place. Times are
        # Venezuela local (VET, America/Caracas); we convert them to UTC.
        p = msg.feature["properties"]
        coords = msg.feature["geometry"]["coordinates"]
        return {
            "id": str(msg.feature["id"]),
            "source": "FUNVISIS",
            "magnitude": float(p["phone"]),
            "mag_type": "ml",  # FUNVISIS doesn't report a magnitude type; assume local (ML).
            "place": _clean_text(p.get("address")),
            "region": p.get("country"),
            "lat": float(coords[1]),
            "lon": float(coords[0]),
            "depth_km": _parse_km(p["phoneFormatted"]),
            "time_utc": _funvisis_time(p["postalCode"], p["city"]),
            "lastupdate_utc": None,
        }

    def _map_geofon(self, msg: RawMessage) -> dict[str, Any]:
        # GEOFON `format=text` rows are already split by the poller into a
        # `{column: value}` dict keyed by the FDSN header names (API-SPEC §4.3);
        # every value is a string, so magnitude/coordinates/depth are coerced here.
        f = msg.feature
        return {
            "id": str(f["EventID"]),
            "source": "GEOFON",
            "magnitude": float(f["Magnitude"]),
            "mag_type": str(f["MagType"]),
            "place": _clean_text(f.get("EventLocationName")),
            "region": None,  # GEOFON exposes no separate region; place carries the location.
            "lat": float(f["Latitude"]),
            "lon": float(f["Longitude"]),
            "depth_km": float(f["Depth/km"]),
            "time_utc": _parse_iso(f["Time"]),
            "lastupdate_utc": None,
        }

    def _build(self, fields: dict[str, Any], action: str) -> SeismicEvent:
        distance = haversine_km(
            self._reference.lat, self._reference.lon, fields["lat"], fields["lon"]
        )
        severity = classify_severity(
            fields["magnitude"], self._severity.info_max, self._severity.warning_max
        )
        valid_action: Action = "update" if action == "update" else "create"
        return SeismicEvent(
            **fields,
            distance_km=distance,
            severity=severity,
            action=valid_action,
        )


def _parse_iso(value: Any) -> datetime:
    """Parses an ISO-8601 timestamp (EMSC) into a tz-aware UTC datetime."""
    if not isinstance(value, str):
        raise ValueError(f"ISO timestamp is not text: {value!r}")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)  # 3.11+ accepts variable-length fractional seconds
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _parse_iso_optional(value: Any) -> datetime | None:
    return _parse_iso(value) if value is not None else None


def _epoch_ms_to_utc(value: Any) -> datetime:
    """Converts epoch milliseconds (USGS) into a tz-aware UTC datetime."""
    if not isinstance(value, int | float):
        raise ValueError(f"epoch ms is not numeric: {value!r}")
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def _epoch_ms_optional(value: Any) -> datetime | None:
    return _epoch_ms_to_utc(value) if value is not None else None


_VENEZUELA_TZ = ZoneInfo("America/Caracas")


def _funvisis_time(date: Any, time: Any) -> datetime:
    """Combines FUNVISIS local date (`DD-MM-YYYY`) and time (`HH:MM`) into UTC.

    The times are Venezuela local (VET, `America/Caracas`); they're localized and then
    converted to the tz-aware UTC that `SeismicEvent` requires.
    """
    if not isinstance(date, str) or not isinstance(time, str):
        raise ValueError(f"FUNVISIS date/time not text: {date!r} {time!r}")
    local = datetime.strptime(f"{date.strip()} {time.strip()}", "%d-%m-%Y %H:%M")
    return local.replace(tzinfo=_VENEZUELA_TZ).astimezone(UTC)


def _parse_km(value: Any) -> float:
    """Parses a FUNVISIS depth string like ``"32.0 km"`` into kilometres."""
    if not isinstance(value, str):
        raise ValueError(f"depth is not text: {value!r}")
    parts = value.strip().split()
    if not parts:
        raise ValueError("depth is empty")
    return float(parts[0])


def _clean_text(value: Any) -> str | None:
    """Collapses the runs of spaces FUNVISIS pads its place names with."""
    if not isinstance(value, str):
        return None
    return " ".join(value.split()) or None
