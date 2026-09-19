"""Pipeline processor -- the task that bridges ingestion and notification (RF-07..RF-13).

`Processor` consumes the `RawMessage` objects from the ingestion queue and, for each
one, applies the normalize -> filter -> deduplicate sequence (TECHNICAL-DESIGN §2):

  - invalid or filtered out -> discarded;
  - `new` -> registered as alerted and delivered to `on_alert`;
  - `update` (a revision of the one on screen) -> delivered to `on_update` without
    alerting again (RF-11);
  - `supersede` -> the same earthquake, reported by a network the user ranked
    higher: the alert on screen is refreshed with the better data, without
    alerting again (RF-11, REQ-PIP-010);
  - `duplicate` -> discarded.

`on_alert`/`on_update` are callbacks (in the agent, they publish onto the
asyncio<->Tk bridge). This keeps the processor decoupled from the GUI and testable
without a screen.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from vigia_eew.history import EventRecord
from vigia_eew.ingest import RawMessage
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.pipeline.filter import GeoFilter
from vigia_eew.pipeline.normalize import Normalizer

_Callback = Callable[[SeismicEvent], None]
_Recorder = Callable[[EventRecord], None]
_Clock = Callable[[], datetime]


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
        record: _Recorder | None = None,
        now: _Clock | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._input_queue = input_queue
        self._normalizer = normalizer
        self._filter = geofilter
        self._dedup = deduplicator
        self._on_alert = on_alert
        self._on_update = on_update
        self._record = record
        self._now = now or (lambda: datetime.now(UTC))
        self._log = logger or logging.getLogger("vigia_eew.pipeline.processor")

    async def process_one(self, msg: RawMessage) -> None:
        """Processes a single raw message applying normalize->filter->dedup."""
        # The journey's first entry. Here rather than in each of the four
        # adapters: one place that every arrival passes through, whichever
        # network it came from, is what the source registry made possible and
        # what stops this from being a fifth thing to remember per source.
        self._log.info(
            "event_received trace=%s source=%s action=%s", msg.trace_id, msg.source, msg.action
        )
        ev = self._normalizer.normalize(msg)
        if ev is None:
            return
        allowed = self._filter.verdict(ev)
        if not allowed.accepted:
            self._remember(ev, verdict="discarded", reason=allowed.reason)
            # At INFO, not DEBUG: "why was I not warned about that one?" is the
            # question this line exists to answer, and it cannot answer it from
            # a log level nobody runs with (REQ-OBS-002).
            self._log.info(
                "event_filtered trace=%s id=%s source=%s reason=%s mag=%.1f distance=%.0f",
                ev.trace_id,
                ev.id,
                ev.source,
                allowed.reason,
                ev.magnitude,
                ev.distance_km,
            )
            return
        # The deduplicator logs its own verdict with the journey it linked the
        # arrival to; discards are no longer silent, which is the whole point.
        verdict = self._dedup.verdict(ev)
        journey = verdict.linked_trace or ev.trace_id
        if verdict.result == "new":
            self._dedup.register(ev)
            self._on_alert(ev)
            self._remember(ev, verdict="alerted")
        elif verdict.result == "update":
            if self._on_update is not None:
                self._on_update(ev)
            self._remember(ev, verdict="alerted", journey=journey)
        elif verdict.result == "supersede":
            self._prevail(ev, verdict.linked_id)
            self._remember(ev, verdict="alerted", journey=journey)
        else:
            self._remember(ev, verdict="discarded", reason="duplicate", journey=journey)

    def _prevail(self, ev: SeismicEvent, superseded: str | None) -> None:
        """A better-ranked network reported the earthquake already on screen.

        It refreshes the alert; it does not raise a second one. The whole
        arrival prevails -- magnitude, epicentre, depth, and the distance the
        normalizer derived from that epicentre -- because patching one field
        would leave the rest describing a different earthquake (CA-110.3).

        Note what this cannot reach: an arrival the filter discarded never
        arrives here, so a better network whose coordinates put the event
        outside the radius does not overrule the alert. Alerting stays the
        filter's decision, which is the half of ADR-026 that is easy to lose.
        """
        self._dedup.register(ev, superseding=superseded)
        if self._on_update is not None:
            self._on_update(ev.model_copy(update={"action": "update", "supersedes": superseded}))

    def _remember(
        self,
        ev: SeismicEvent,
        *,
        verdict: str,
        reason: str | None = None,
        journey: str | None = None,
    ) -> None:
        """Writes the arrival into the history -- after the alert, never before.

        The order is the requirement (REQ-HIS-002, CA-111.5): the history is a
        consequence of an alert, never a condition of one. So is the `except`:
        an agent that cannot write its history is still an agent that alerts,
        and the failure belongs in the log rather than in the user's face.

        A discarded arrival carries the journey it was discarded *in favour
        of*, which is what lets the two rows of one earthquake be read
        together (CA-111.3).
        """
        if self._record is None:
            return
        try:
            self._record(
                EventRecord(
                    correlation_id=journey or ev.trace_id,
                    source=ev.source,
                    source_event_id=ev.id,
                    occurred_at=ev.time_utc,
                    recorded_at=self._now(),
                    latitude=ev.lat,
                    longitude=ev.lon,
                    depth_km=ev.depth_km,
                    magnitude=ev.magnitude,
                    region=ev.place or ev.region,
                    distance_km=ev.distance_km,
                    verdict=verdict,
                    reason=reason,
                    severity=ev.severity if verdict == "alerted" else None,
                )
            )
        except Exception as exc:  # noqa: BLE001 - the alert already happened (Art. 1)
            self._log.warning(
                "history_record_failed trace=%s type=%s detail=%s",
                ev.trace_id,
                type(exc).__name__,
                exc,
            )

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
