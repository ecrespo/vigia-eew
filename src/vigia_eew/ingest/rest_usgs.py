"""USGS FDSN REST reconciler — low-frequency backup (RF-05, RF-06, ADR-002).

`RESTReconciler` queries the USGS FDSN service every `poll_interval_s` to recover
events the EMSC WebSocket might have missed and to cover small local earthquakes.
It doesn't compete with the push channel: low frequency, low weight
(TECHNICAL-DESIGN §4).

  - **Persisted cursor** (RF-06): queries with `starttime` = last processed `time`;
    after processing, advances the cursor to the maximum seen and saves it (survives
    restarts).
  - **Resilience** (RNF-03, API-SPEC §2.5): 429 honors `Retry-After`; 5xx/timeout/
    invalid JSON are logged and retried on the next cycle, without aborting or
    losing the cursor.

The HTTP client (`httpx`) and `sleep` are injected to test without network.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from vigia_eew.config import Filter, ReferencePoint, USGSSource
from vigia_eew.ingest import RawMessage
from vigia_eew.state import StateStore

_SleepFn = Callable[[float], Any]


class RESTReconciler:
    """USGS FDSN polling with a persisted cursor; publishes `RawMessage` onto `output`."""

    def __init__(
        self,
        cfg: USGSSource,
        reference: ReferencePoint,
        filter_cfg: Filter,
        state: StateStore,
        output: asyncio.Queue[RawMessage],
        *,
        client: httpx.AsyncClient | None = None,
        sleep: _SleepFn = asyncio.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._reference = reference
        self._filter = filter_cfg
        self._state = state
        self._output = output
        self._client = client
        self._sleep = sleep
        self._log = logger or logging.getLogger("vigia_eew.ingest.rest")

    def _build_params(self, cursor_ms: int | None) -> dict[str, Any]:
        """Builds the FDSN query parameters (API-SPEC §2.2)."""
        params: dict[str, Any] = {
            "format": "geojson",
            "latitude": self._reference.lat,
            "longitude": self._reference.lon,
            "maxradiuskm": self._filter.radius_km,
            "minmagnitude": self._filter.min_magnitude,
            "orderby": "time",
            "eventtype": "earthquake",
        }
        if cursor_ms is not None:
            moment = datetime.fromtimestamp(cursor_ms / 1000, tz=UTC)
            params["starttime"] = moment.strftime("%Y-%m-%dT%H:%M:%S")
        return params

    async def poll_once(self) -> float:
        """Runs one query and processes the response.

        Returns:
            Seconds to wait before the next poll (normally `poll_interval_s`;
            higher if a 429 indicates `Retry-After`).
        """
        interval = float(self._cfg.poll_interval_s)
        cursor = self._state.state.cursor_usgs_ms
        params = self._build_params(cursor)

        if self._client is None:
            raise RuntimeError("RESTReconciler requires an httpx client (injected or created).")

        try:
            resp = await self._client.get(
                self._cfg.url, params=params, timeout=self._cfg.timeout_s
            )
        except httpx.HTTPError as exc:
            self._log.warning("usgs_network_error type=%s detail=%s", type(exc).__name__, exc)
            return interval

        if resp.status_code == 429:
            retry = _retry_after_seconds(resp.headers, default=interval)
            self._log.warning("usgs_429 retry_after_s=%.1f", retry)
            return retry
        if resp.status_code >= 500:
            self._log.warning("usgs_5xx status=%d", resp.status_code)
            return interval
        if resp.status_code != 200:
            self._log.warning("usgs_unexpected_status status=%d", resp.status_code)
            return interval

        try:
            data = resp.json()
            features = data["features"]
        except (ValueError, KeyError, TypeError) as exc:
            self._log.warning("usgs_invalid_json detail=%s", exc)
            return interval

        max_time = await self._process_features(features)
        if max_time is not None:
            self._state.update_usgs_cursor(max_time)
            self._state.save()
        return interval

    async def _process_features(self, features: Any) -> int | None:
        """Enqueues each Feature as `RawMessage`; returns the maximum `time` seen."""
        if not isinstance(features, list):
            self._log.warning("usgs_features_not_a_list")
            return None
        max_time: int | None = None
        for feature in features:
            if not isinstance(feature, dict):
                continue
            await self._output.put(RawMessage(source="USGS", action="create", feature=feature))
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


def _retry_after_seconds(headers: Any, *, default: float) -> float:
    """Reads `Retry-After` (seconds) from the headers; uses `default` if missing or invalid."""
    raw = headers.get("Retry-After")
    if raw is None:
        return default
    try:
        return max(default, float(raw))
    except (TypeError, ValueError):
        return default


def _time_ms(feature: dict[str, Any]) -> int | None:
    """Extracts `properties.time` (epoch ms) from a Feature, or None if not an int."""
    properties = feature.get("properties")
    if not isinstance(properties, dict):
        return None
    time_value = properties.get("time")
    return time_value if isinstance(time_value, int) else None
