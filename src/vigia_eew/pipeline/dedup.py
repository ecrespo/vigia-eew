"""Deduplication and `update` handling (RF-09, RF-10, RF-11, RF-42; TECHNICAL-DESIGN §5).

`Deduplicator` classifies each already-filtered `SeismicEvent` into one of three
outcomes:

  - `"new"`: never alerted and no match against recent events -> raise an alert.
  - `"update"`: same `id` already alerted with `action="update"` -> refresh the
    on-screen alert without alerting again (RF-11).
  - `"duplicate"`: same `id` already alerted, or a cross-source match by heuristic
    (<= distance, <= time window, <= magnitude delta, RF-09) -> discard.

The state (`alerted_ids` + `recent_signatures`) is persisted so alerts are not
repeated across restarts (RF-10). Id decisions use exact equality; cross-source
matches use the configurable heuristic (`Dedup`). `register()` also prunes entries
older than 24 h before persisting (RF-42), so the state file doesn't grow unbounded.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from vigia_eew.config import Dedup
from vigia_eew.geo import haversine_km
from vigia_eew.models import AlertedId, EventSignature, SeismicEvent
from vigia_eew.state import StateStore

DedupResult = Literal["new", "update", "duplicate", "supersede"]


@dataclass(frozen=True, slots=True)
class DedupVerdict:
    """The outcome, and the journey this arrival belongs to.

    `linked_trace` is the correlation id of the arrival that already alerted
    this earthquake. Without it, a discarded second arrival leaves precisely
    the gap the requirement exists to close: somebody asks why their second
    network produced no alert, and the answer -- "because the first one
    already did, at 12:00:07" -- is unreachable.

    None when the event is new: it starts its own journey, and linking it to
    anything would be an invention.
    """

    result: DedupResult
    linked_trace: str | None
    #: Id of the arrival this one is linked to -- the one that alerted. Carried
    #: alongside the trace because a `supersede` has to name the alert it
    #: overrules, and the history has to record which row won (REQ-HIS-006).
    linked_id: str | None = None


class Deduplicator:
    """Classifies events as new/update/duplicate and persists what was alerted."""

    def __init__(
        self,
        cfg: Dedup,
        state: StateStore,
        *,
        priority_rank: Mapping[str, int] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._state = state
        #: Position of each network in the user's preference order, smaller
        #: first. Injected as a plain mapping rather than read from the source
        #: registry: what the pipeline needs to know is the order, not where
        #: sources come from. Empty means nobody declared one, and then the
        #: first arrival keeps winning, exactly as it did before v1.0.
        self._rank = dict(priority_rank or {})
        self._log = logger or logging.getLogger("vigia_eew.pipeline.dedup")

    def classify(self, ev: SeismicEvent) -> DedupResult:
        """Determines the dedup outcome for an already-filtered event."""
        return self.verdict(ev).result

    def verdict(self, ev: SeismicEvent) -> DedupVerdict:
        """The same decision, plus the journey the arrival belongs to.

        Why the heuristic has the shape it has, and why an `update` refreshes
        the alert instead of raising a second one:
        [[lat.md/pipeline#Processing pipeline#Deduplication]].
        """
        if self._state.already_alerted(ev.id):
            # Same id: either a revision (update) of an active alert, or a duplicate.
            linked = self._state.trace_of(ev.id)
            result: DedupResult = "update" if ev.action == "update" else "duplicate"
            self._log.info(
                "dedup_same_id trace=%s linked_to=%s id=%s source=%s result=%s",
                ev.trace_id,
                linked,
                ev.id,
                ev.source,
                result,
            )
            return DedupVerdict(result, linked, ev.id)
        for signature in self._state.state.recent_signatures:
            if self._matches(ev, signature):
                linked = signature.trace_id or None
                result = "supersede" if self._outranks(ev.source, signature.source) else "duplicate"
                self._log.info(
                    "dedup_cross_source trace=%s linked_to=%s id=%s source=%s result=%s",
                    ev.trace_id,
                    linked,
                    ev.id,
                    ev.source,
                    result,
                )
                return DedupVerdict(result, linked, signature.event_id or None)
        return DedupVerdict("new", None)

    def register(self, ev: SeismicEvent, *, superseding: str | None = None) -> None:
        """Marks an event as alerted (id + signature) and persists the state (RF-10).

        Prunes entries older than `StateStore.MAX_AGE` first (RF-42, ADR-018), so
        `alerted_ids`/`recent_signatures` don't grow unbounded across the agent's
        lifetime. `prune()` previously existed but was never invoked from any run path.

        With `superseding`, this arrival's signature **replaces** that event's
        instead of being added next to it. One earthquake keeps one signature,
        so a third arrival is compared against the data that prevailed rather
        than against the one already overruled (REQ-PIP-010).
        """
        self._state.prune()
        self._state.register_alerted(
            AlertedId(id=ev.id, source=ev.source, time_utc=ev.time_utc, trace_id=ev.trace_id)
        )
        self._state.add_signature(ev.signature(), replacing=superseding)
        self._state.save()

    def _outranks(self, arriving: str, alerted: str) -> bool:
        """True if `arriving` sits ahead of `alerted` in the declared order.

        Unknown to the rank -- an undeclared network, or a signature written
        before v1.0 that records no source -- never outranks anything. Silence
        is not a claim to be better, and the alert already on screen wins by
        default (CA-110.6).
        """
        if arriving not in self._rank or alerted not in self._rank:
            return False
        return self._rank[arriving] < self._rank[alerted]

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
