"""FUNVISIS polling ingestor — **Venezuela-only** local coverage (RF-38, RNF-03).

`FUNVISISPoller` polls FUNVISIS's `maravilla.json` every `poll_interval_s`. FUNVISIS
(the Venezuelan national seismic network) publishes only the ~20 most recent events as
a static GeoJSON file that its web map polls; there is **no push/streaming channel**, so
this is a pure poller, like `rest_usgs.RESTReconciler`. It fills the gap of small local
earthquakes (M2-3) that the international networks (EMSC/USGS) don't catalog.

Because the endpoint always returns the same recent batch, the poller keeps an in-memory
set of the ids it has already emitted **in this process**:

  - The **first successful poll** seeds that set with whatever is currently in the file
    and emits nothing — the events already present when the agent starts are recorded as
    seen, not alerted (no startup burst of stale alerts).
  - **Later polls** emit only ids that appear for the first time — i.e. earthquakes that
    show up *after* the agent started.

Re-alerting across restarts is prevented downstream by the persisted `alerted_ids`
(`state.py` / `pipeline.dedup`); this in-process set only avoids the first-run burst.

The endpoint is **plain HTTP** (FUNVISIS offers no valid HTTPS); the data is public.
The HTTP client (`httpx`) and `sleep` are injected so it's testable without network.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

import httpx

from vigia_eew.config import FUNVISISSource
from vigia_eew.ingest import RawMessage

_SleepFn = Callable[[float], Any]


class FUNVISISPoller:
    """Polls FUNVISIS `maravilla.json`; publishes new events as `RawMessage` onto `output`."""

    def __init__(
        self,
        cfg: FUNVISISSource,
        output: asyncio.Queue[RawMessage],
        *,
        client: httpx.AsyncClient | None = None,
        sleep: _SleepFn = asyncio.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._output = output
        self._client = client
        self._sleep = sleep
        self._log = logger or logging.getLogger("vigia_eew.ingest.funvisis")
        # None until the first successful poll seeds it (that poll emits nothing).
        self._seen: set[str] | None = None

    async def poll_once(self) -> float:
        """Runs one fetch and enqueues newly-appeared events. Returns seconds to wait."""
        interval = float(self._cfg.poll_interval_s)
        if self._client is None:
            raise RuntimeError("FUNVISISPoller requires an httpx client (injected or created).")

        try:
            resp = await self._client.get(self._cfg.url, timeout=self._cfg.timeout_s)
        except httpx.HTTPError as exc:
            self._log.warning("funvisis_network_error type=%s detail=%s", type(exc).__name__, exc)
            return interval

        if resp.status_code != 200:
            self._log.warning("funvisis_unexpected_status status=%d", resp.status_code)
            return interval

        try:
            features = resp.json()["features"]
        except (ValueError, KeyError, TypeError) as exc:
            self._log.warning("funvisis_invalid_json detail=%s", exc)
            return interval

        await self._process_features(features)
        return interval

    async def _process_features(self, features: Any) -> None:
        """Emits features whose id is new; the first poll only seeds the seen-set."""
        if not isinstance(features, list):
            self._log.warning("funvisis_features_not_a_list")
            return

        ids: list[tuple[str, dict[str, Any]]] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            fid = _funvisis_id(feature)
            feature["id"] = fid  # single source of truth for the id (normalize reads it)
            ids.append((fid, feature))

        if self._seen is None:
            # First successful poll: record what's already there, alert on none of it.
            self._seen = {fid for fid, _ in ids}
            self._log.info("funvisis_seeded count=%d", len(self._seen))
            return

        for fid, feature in ids:
            if fid in self._seen:
                continue
            self._seen.add(fid)
            await self._output.put(RawMessage(source="FUNVISIS", action="create", feature=feature))

    async def run(self) -> None:
        """Perpetual polling loop. Only exits when cancelled."""
        if self._client is None:
            self._client = httpx.AsyncClient()
        while True:
            wait = await self.poll_once()
            await self._sleep(wait)


def _funvisis_id(feature: dict[str, Any]) -> str:
    """Deterministic id from a FUNVISIS feature (date + time + coordinates).

    FUNVISIS provides no event id; this composite is stable per event so the in-process
    seen-set and the downstream deduplication agree on identity. Malformed features still
    get an id (missing parts become ``?``); `normalize` discards them afterwards.
    """
    props = feature.get("properties")
    p = props if isinstance(props, dict) else {}
    date = p.get("postalCode", "?")
    time = p.get("city", "?")
    lat = p.get("lat", "?")
    lon = p.get("long", "?")
    return f"funvisis-{date}-{time}-{lat}-{lon}".replace(" ", "")
