"""Event normalizer (RF-07, RF-08, RF-13; mapping in API-SPEC §3.1).

`Normalizer` translates a `RawMessage` (raw EMSC or USGS payload) into the common
`SeismicEvent` that flows through the rest of the pipeline. It resolves the differences
between sources:

  - EMSC: lowercase `magtype`, ISO-8601 timestamps, id in `properties.unid`,
    coordinates in `properties`.
  - USGS: camelCase `magType`, epoch-ms timestamps, id on the Feature itself,
    coordinates in `geometry.coordinates` [lon, lat, depth].

It computes the **derived** fields (`distance_km` via haversine, `severity` via
thresholds) and requires timestamps to end up tz-aware in UTC (enforced by
`SeismicEvent`). On invalid raw input it logs and returns `None` (discard without
aborting, RNF-03).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from ..config import ReferencePoint, Severity
from ..geo import haversine_km
from ..ingest import RawMessage
from ..models import Action, SeismicEvent, classify_severity


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
