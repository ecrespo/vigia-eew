"""GEOFON FDSN REST poller — independent global-network source (RF-39, RNF-03).

`GEOFONPoller` queries GEOFON's `fdsnws-event` service (GFZ Potsdam) every
`poll_interval_s` to add redundant global coverage from a **different network** than
EMSC/USGS. It plays the same low-frequency-backup role as `rest_usgs.RESTReconciler`
(RF-05), but from a distinct provider, so an outage or catalog gap at one network does
not leave the agent blind.

Two things set it apart from the USGS reconciler:

  - **Text, not GeoJSON** (API-SPEC §4.3): GEOFON's `format=text` returns a stable
    pipe-delimited table — one `#`-prefixed header line, then one `|`-delimited row per
    event. The poller splits that into a per-event ``{column: value}`` dict (the header
    names the columns) and emits it as a `RawMessage`; `pipeline.normalize._map_geofon`
    maps those keys into the common `SeismicEvent`. A row with the wrong column count is
    discarded on its own without aborting the rest of the batch.
  - **Cursor is an FDSN `starttime`** (RF-06): like USGS, it persists the maximum origin
    time seen (`cursor_geofon_ms`) and queries `starttime=<cursor>` so history isn't
    re-fetched every cycle. The cursor survives restarts (re-alerting is prevented
    downstream by the persisted `alerted_ids`).
  - **Bounded backlog floor** (RF-41, ADR-017): the effective `starttime` sent is never
    older than 00:00 local time today — when the persisted cursor is `None` or older
    than that floor (a stale cursor after a long outage), the floor is used instead.
    Mirrors `rest_usgs.RESTReconciler`'s floor; the downstream freshness filter (RF-40)
    remains the authoritative rule for what gets alerted.

The HTTP client (`httpx`) and `sleep` are injected so it's testable without network.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from vigia_eew.config import Filter, GEOFONSource, ReferencePoint
from vigia_eew.ingest import RawMessage
from vigia_eew.state import StateStore
from vigia_eew.timeutil import Clock, default_clock, floor_starttime_ms

_SleepFn = Callable[[float], Any]

# FDSN `fdsnws-event` expresses a search radius in degrees, not kilometres (unlike
# USGS's `maxradiuskm` extension). ~111.195 km per degree of great-circle arc.
_KM_PER_DEGREE = 111.195


class GEOFONPoller:
    """Polls GEOFON `fdsnws-event` (text format) with a persisted cursor; emits `RawMessage`."""

    def __init__(
        self,
        cfg: GEOFONSource,
        reference: ReferencePoint,
        filter_cfg: Filter,
        state: StateStore,
        output: asyncio.Queue[RawMessage],
        *,
        client: httpx.AsyncClient | None = None,
        sleep: _SleepFn = asyncio.sleep,
        timezone: str = "UTC",
        now: Clock = default_clock,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._reference = reference
        self._filter = filter_cfg
        self._state = state
        self._output = output
        self._client = client
        self._sleep = sleep
        self._timezone = timezone
        self._now = now
        self._log = logger or logging.getLogger("vigia_eew.ingest.geofon")

    def _build_params(self, cursor_ms: int | None) -> dict[str, Any]:
        """Builds the FDSN query parameters (API-SPEC §4.2)."""
        params: dict[str, Any] = {
            "format": "text",
            "lat": self._reference.lat,
            "lon": self._reference.lon,
            "maxradius": self._filter.radius_km / _KM_PER_DEGREE,
            "minmagnitude": self._filter.min_magnitude,
            "orderby": "time",
        }
        effective_cursor = floor_starttime_ms(cursor_ms, self._timezone, self._now)
        if effective_cursor is not None:
            moment = datetime.fromtimestamp(effective_cursor / 1000, tz=UTC)
            params["starttime"] = moment.strftime("%Y-%m-%dT%H:%M:%S")
        return params

    async def poll_once(self) -> float:
        """Runs one query and processes the response. Returns seconds to wait next."""
        interval = float(self._cfg.poll_interval_s)
        cursor = self._state.state.cursor_geofon_ms
        params = self._build_params(cursor)

        if self._client is None:
            raise RuntimeError("GEOFONPoller requires an httpx client (injected or created).")

        try:
            resp = await self._client.get(
                self._cfg.url, params=params, timeout=self._cfg.timeout_s
            )
        except httpx.HTTPError as exc:
            self._log.warning("geofon_network_error type=%s detail=%s", type(exc).__name__, exc)
            return interval

        if resp.status_code == 204:
            # No matching events: an empty result, not an error (API-SPEC §4.4).
            return interval
        if resp.status_code == 429:
            retry = _retry_after_seconds(resp.headers, default=interval)
            self._log.warning("geofon_429 retry_after_s=%.1f", retry)
            return retry
        if resp.status_code >= 500:
            self._log.warning("geofon_5xx status=%d", resp.status_code)
            return interval
        if resp.status_code != 200:
            self._log.warning("geofon_unexpected_status status=%d", resp.status_code)
            return interval

        max_time = await self._process_text(resp.text)
        if max_time is not None:
            self._state.update_geofon_cursor(max_time)
            self._state.save()
        return interval

    async def _process_text(self, text: Any) -> int | None:
        """Parses the pipe-delimited body, enqueues events; returns the max origin time (ms)."""
        if not isinstance(text, str):
            self._log.warning("geofon_body_not_text")
            return None

        columns: list[str] | None = None
        max_time: int | None = None
        for line in text.splitlines():
            row = line.strip()
            if not row:
                continue
            if row.startswith("#"):
                # The (single) header names the columns for every following row.
                columns = [c.strip() for c in row.lstrip("#").split("|")]
                continue
            if columns is None:
                # A data row before any header: the shape is unknown, skip the batch.
                self._log.warning("geofon_no_header")
                return max_time
            values = row.split("|")
            if len(values) != len(columns):
                self._log.warning(
                    "geofon_malformed_row expected=%d got=%d", len(columns), len(values)
                )
                continue
            feature = {col: val.strip() for col, val in zip(columns, values, strict=True)}
            if not _is_earthquake(feature):
                continue
            await self._output.put(
                RawMessage(source="GEOFON", action="create", feature=feature)
            )
            moment = _time_ms(feature)
            if moment is not None and (max_time is None or moment > max_time):
                max_time = moment
        return max_time

    async def run(self) -> None:
        """Perpetual polling loop. Only exits when cancelled."""
        if self._client is None:
            self._client = httpx.AsyncClient()
        while True:
            wait = await self.poll_once()
            await self._sleep(wait)


def _is_earthquake(feature: dict[str, str]) -> bool:
    """True unless `EventType` positively names a non-earthquake (blasts, explosions…).

    GEOFON's catalog is overwhelmingly earthquakes; an empty/missing type is kept
    (lenient), only a known non-earthquake type is filtered — same intent as USGS's
    `eventtype=earthquake` query filter (API-SPEC §4.3).
    """
    event_type = feature.get("EventType", "").strip().lower()
    return event_type in ("", "earthquake")


def _time_ms(feature: dict[str, str]) -> int | None:
    """Parses the `Time` column (ISO-8601 UTC) into epoch milliseconds, or None."""
    raw = feature.get("Time")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def _retry_after_seconds(headers: Any, *, default: float) -> float:
    """Reads `Retry-After` (seconds) from the headers; uses `default` if missing or invalid."""
    raw = headers.get("Retry-After")
    if raw is None:
        return default
    try:
        return max(default, float(raw))
    except (TypeError, ValueError):
        return default
