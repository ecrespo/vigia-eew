"""Pipeline processor -- the task that bridges ingestion and notification (RF-07..RF-13).

`Processor` consumes the `RawMessage` objects from the ingestion queue and, for each
one, applies the normalize -> filter -> deduplicate sequence (TECHNICAL-DESIGN §2):

  - invalid or filtered out -> discarded;
  - `new` -> registered as alerted and delivered to `on_alert`;
  - `update` (a revision of the one on screen) -> delivered to `on_update` without
    alerting again (RF-11);
  - `duplicate` -> discarded.

`on_alert`/`on_update` are callbacks (in the agent, they publish onto the
asyncio<->Tk bridge). This keeps the processor decoupled from the GUI and testable
without a screen.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from vigia_eew.ingest import RawMessage
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.pipeline.filter import GeoFilter
from vigia_eew.pipeline.normalize import Normalizer

_Callback = Callable[[SeismicEvent], None]


class Processor:
    """Orchestrates normalize->filter->dedup over the raw message queue (pipeline_task)."""

    def __init__(
        self,
        input_queue: asyncio.Queue[RawMessage],
        normalizer: Normalizer,
        geofilter: GeoFilter,
        deduplicator: Deduplicator,
        *,
        on_alert: _Callback,
        on_update: _Callback | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._input_queue = input_queue
        self._normalizer = normalizer
        self._filter = geofilter
        self._dedup = deduplicator
        self._on_alert = on_alert
        self._on_update = on_update
        self._log = logger or logging.getLogger("vigia_eew.pipeline.processor")

    async def process_one(self, msg: RawMessage) -> None:
        """Processes a single raw message applying normalize->filter->dedup."""
        ev = self._normalizer.normalize(msg)
        if ev is None:
            return
        if not self._filter.accepts(ev):
            self._log.debug("event_filtered id=%s distance=%.0f", ev.id, ev.distance_km)
            return
        result = self._dedup.classify(ev)
        if result == "new":
            self._dedup.register(ev)
            self._on_alert(ev)
        elif result == "update":
            if self._on_update is not None:
                self._on_update(ev)
        # "duplicate": discarded silently

    async def run(self) -> None:
        """Pipeline loop: consumes the queue until cancelled."""
        while True:
            msg = await self._input_queue.get()
            try:
                await self.process_one(msg)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - a single raw message must not sink the pipeline
                self._log.warning("processor_error type=%s detail=%s", type(exc).__name__, exc)
