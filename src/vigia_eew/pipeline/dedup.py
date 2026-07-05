"""Deduplication and `update` handling (RF-09, RF-10, RF-11; TECHNICAL-DESIGN §5).

`Deduplicator` classifies each already-filtered `SeismicEvent` into one of three
outcomes:

  - `"new"`: never alerted and no match against recent events -> raise an alert.
  - `"update"`: same `id` already alerted with `action="update"` -> refresh the
    on-screen alert without alerting again (RF-11).
  - `"duplicate"`: same `id` already alerted, or a cross-source match by heuristic
    (<= distance, <= time window, <= magnitude delta, RF-09) -> discard.

The state (`alerted_ids` + `recent_signatures`) is persisted so alerts are not
repeated across restarts (RF-10). Id decisions use exact equality; cross-source
matches use the configurable heuristic (`Dedup`).
"""

from __future__ import annotations

import logging
from typing import Literal

from vigia_eew.config import Dedup
from vigia_eew.geo import haversine_km
from vigia_eew.models import AlertedId, EventSignature, SeismicEvent
from vigia_eew.state import StateStore

DedupResult = Literal["new", "update", "duplicate"]


class Deduplicator:
    """Classifies events as new/update/duplicate and persists what was alerted."""

    def __init__(
        self,
        cfg: Dedup,
        state: StateStore,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._state = state
        self._log = logger or logging.getLogger("vigia_eew.pipeline.dedup")

    def classify(self, ev: SeismicEvent) -> DedupResult:
        """Determines the dedup outcome for an already-filtered event."""
        if self._state.already_alerted(ev.id):
            # Same id: either a revision (update) of an active alert, or a duplicate.
            return "update" if ev.action == "update" else "duplicate"
        for signature in self._state.state.recent_signatures:
            if self._matches(ev, signature):
                self._log.info("dedup_cross_source id=%s source=%s", ev.id, ev.source)
                return "duplicate"
        return "new"

    def register(self, ev: SeismicEvent) -> None:
        """Marks an event as alerted (id + signature) and persists the state (RF-10)."""
        self._state.register_alerted(
            AlertedId(id=ev.id, source=ev.source, time_utc=ev.time_utc)
        )
        self._state.add_signature(ev.signature())
        self._state.save()

    def _matches(self, ev: SeismicEvent, signature: EventSignature) -> bool:
        """True if `ev` and `signature` are the same earthquake per the heuristic (RF-09)."""
        distance = haversine_km(ev.lat, ev.lon, signature.lat, signature.lon)
        delta_t = abs((ev.time_utc - signature.time_utc).total_seconds())
        delta_mag = abs(ev.magnitude - signature.magnitude)
        return (
            distance <= self._cfg.distance_km
            and delta_t <= self._cfg.window_s
            and delta_mag <= self._cfg.magnitude_delta
        )
