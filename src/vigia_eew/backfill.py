"""Completing the history from the networks' catalogues (REQ-HIS-010..012, ADR-036).

The history only knows what the agent saw while it was running. For an
alerting tool that is correct; for a view of a region's seismicity it is the
limitation that weighs most -- a fresh install has an empty map, and two weeks
with the machine off are two weeks missing.

This module reads a period from each network's catalogue and writes what is
not already there. Nearly all of its design is about what it does **not** do
([[lat.md/history#Recovery is a separate path that writes only to the history]]):

  - **It cannot alert.** It is not an ingestor: nothing it reads reaches the
    raw queue, the filter's verdict, the deduplicator's memory, the supervisor
    or the alert controller. It does not import them, and a contract fails if
    it ever does. An earthquake from a month ago cannot open a window.
  - **It touches the history file and nothing else.** Not `state.json`, not the
    live cursors.
  - **It never overwrites what the agent decided.** An arrival already there
    is left alone; a recovered one is stored as `recovered`, a verdict of its
    own, because nobody evaluated it.
  - **It does not turn one earthquake into two.** The same earthquake from
    another network joins the one already known, by the very rule the
    deduplicator alerts by.

One network failing is reported and the others carry on (Art. 3).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from vigia_eew.config import Settings
from vigia_eew.history import RECOVERED, EventRecord, HistoryStore
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.ingest import RawMessage, new_trace_id
from vigia_eew.ingest.catalogue import Catalogue, CatalogueError, NotRecoverable, fetch
from vigia_eew.ingest.registry import SOURCE_REGISTRY, SourceSpec, ordered_sources
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.dedup import Origin, same_earthquake
from vigia_eew.pipeline.normalize import Normalizer

Clock = Callable[[], datetime]
_Sleep = Callable[[float], Awaitable[Any]]


class PeriodRefused(ValueError):
    """The period asked for cannot be recovered (REQ-HIS-012).

    Raised before any request is made. `days` and `limit` are kept so that a
    frontend can word the refusal in the user's language.
    """

    def __init__(self, days: int, limit: int) -> None:
        self.days = days
        self.limit = limit
        if days < 1:
            message = f"cannot recover {days} days: the period must be at least one day"
        else:
            message = (
                f"cannot recover {days} days: recovered entries are kept for {limit} "
                "([history] recovered_retention_days)"
            )
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class Outcome:
    """What became of one configured network in a recovery.

    `status` is `recovered` (the catalogue was read to the end), `failed` (it
    could not be -- what was read before the failure is kept and counted) or
    `not_recoverable` (the source has no catalogue to ask).
    """

    source: str
    status: str
    #: Arrivals written; arrivals that were already there; records that did
    #: not parse.
    recovered: int = 0
    present: int = 0
    skipped: int = 0
    #: Why it failed, or why it cannot be recovered.
    detail: str = ""
    reason_key: str | None = None


def check_period(days: int, cfg: Settings) -> None:
    """Refuses a period that reaches further back than recovered rows are kept.

    The bound is the retention because recovering what the next start would
    delete is not a feature.
    """
    limit = cfg.history.recovered_retention_days
    if days < 1 or days > limit:
        raise PeriodRefused(days, limit)


async def recover(
    cfg: Settings,
    store: HistoryStore,
    days: int,
    *,
    client: Any,
    now: Clock | None = None,
    sleep: _Sleep = asyncio.sleep,
    registry: tuple[SourceSpec, ...] = SOURCE_REGISTRY,
    logger: logging.Logger | None = None,
) -> list[Outcome]:
    """Recovers the last `days` days into `store`; one outcome per configured network.

    Networks are read in the user's order of preference, so that when two of
    them report one earthquake the row of the better-ranked one is the one
    that prevails.
    """
    check_period(days, cfg)
    log = logger or logging.getLogger("vigia_eew.backfill")
    until = (now or (lambda: datetime.now(UTC)))()
    since = until - timedelta(days=days)
    normalizer = Normalizer(cfg.reference, cfg.severity, registry=registry, logger=log)
    outcomes = []
    for spec in ordered_sources(cfg, registry):
        if not spec.is_enabled(cfg):
            continue
        recovery = spec.recovery
        if not isinstance(recovery, Catalogue):
            outcomes.append(_not_recoverable(spec.source, recovery))
            continue
        messages = fetch(
            spec.source, recovery, cfg, since, until, client=client, sleep=sleep, logger=log
        )
        outcome = await _recover_source(spec.source, messages, normalizer, cfg, store, until, log)
        log.info(
            "backfill_source source=%s status=%s recovered=%d present=%d skipped=%d",
            outcome.source,
            outcome.status,
            outcome.recovered,
            outcome.present,
            outcome.skipped,
        )
        outcomes.append(outcome)
    return outcomes


async def _recover_source(
    source: str,
    messages: AsyncIterator[RawMessage],
    normalizer: Normalizer,
    cfg: Settings,
    store: HistoryStore,
    moment: datetime,
    log: logging.Logger,
) -> Outcome:
    """Writes what one network's catalogue yields; a failure is its outcome, not an exception.

    What was read before a failure has been written and is counted: half a
    period recovered is better than none, and the next run completes it.
    """
    outcome = Outcome(source, RECOVERED)
    try:
        async for message in messages:
            event = normalizer.normalize(message)
            outcome = _tally(outcome, None if event is None else _write(event, cfg, store, moment))
    except CatalogueError as exc:
        log.warning("backfill_failed source=%s detail=%s", source, exc)
        return replace(outcome, status="failed", detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - one network must not stop the others (Art. 3)
        log.warning("backfill_failed source=%s type=%s detail=%s", source, type(exc).__name__, exc)
        return replace(outcome, status="failed", detail=f"{type(exc).__name__}: {exc}")
    return outcome


def _not_recoverable(source: str, recovery: NotRecoverable | None) -> Outcome:
    if recovery is None:  # the registry's validation forbids it; said rather than assumed
        return Outcome(source, "not_recoverable", detail="the source declares no catalogue")
    return Outcome(
        source, "not_recoverable", detail=recovery.reason, reason_key=recovery.reason_key
    )


def _tally(outcome: Outcome, written: bool | None) -> Outcome:
    """Counts one record: unreadable (None), written (True) or already there (False)."""
    if written is None:
        return replace(outcome, skipped=outcome.skipped + 1)
    if written:
        return replace(outcome, recovered=outcome.recovered + 1)
    return replace(outcome, present=outcome.present + 1)


def _write(event: SeismicEvent, cfg: Settings, store: HistoryStore, moment: datetime) -> bool:
    """Stores one recovered arrival, joined to its earthquake; False if it was there.

    `recorded_at` is the instant of the recovery and `distance_km` the
    distance to today's reference point: the only ones there are.
    """
    correlation_id, prevailing = _earthquake_of(event, cfg, store)
    return store.record_recovered(
        EventRecord(
            correlation_id=correlation_id,
            source=event.source,
            source_event_id=event.id,
            occurred_at=event.time_utc,
            recorded_at=moment,
            latitude=event.lat,
            longitude=event.lon,
            depth_km=event.depth_km,
            magnitude=event.magnitude,
            region=event.place or event.region,
            distance_km=event.distance_km,
            verdict=RECOVERED,
            superseded_by=prevailing,
        )
    )


# @lat: [[pipeline#Deduplication]]
def _earthquake_of(
    event: SeismicEvent, cfg: Settings, store: HistoryStore
) -> tuple[str, int | None]:
    """The earthquake this arrival belongs to, and the row that prevails in it.

    An arrival of an earthquake the history already holds -- from another
    network -- takes that earthquake's correlation id and points at its
    prevailing row. The test is the deduplicator's own (RF-09), with the
    configured thresholds: two rules for "the same earthquake" would be two
    answers. Otherwise the arrival starts an earthquake of its own.
    """
    here = Origin(event.lat, event.lon, event.time_utc, event.magnitude)
    known = [
        row
        for row in store.near(event.time_utc, cfg.dedup.window_s)
        if row.correlation_id
        and not (row.source == event.source and row.source_event_id == event.id)
        and same_earthquake(
            cfg.dedup, here, Origin(row.latitude, row.longitude, row.occurred_at, row.magnitude)
        )
    ]
    if not known:
        return new_trace_id(), None
    # The row to join: one that alerted, else one nothing superseded.
    best = min(
        known, key=lambda row: (row.verdict != "alerted", row.superseded_by is not None, row.id)
    )
    return best.correlation_id, best.superseded_by or best.id


# --- Running it, and saying what happened ------------------------------------------


def run(cfg: Settings, days: int, *, store: HistoryStore | None = None) -> list[Outcome]:
    """Recovers `days` days with a client and a history of its own, and waits for it.

    For the command line and for a worker thread. The store is opened here
    unless one is given, with **no pruning**: a recovery must not delete.
    """
    check_period(days, cfg)
    own = store is None
    target = store if store is not None else HistoryStore(prune_on_open=False).open()

    async def work() -> list[Outcome]:
        async with httpx.AsyncClient() as client:
            return await recover(cfg, target, days, client=client)

    try:
        return asyncio.run(work())
    finally:
        if own:
            target.close()


def refusal_text(refusal: PeriodRefused, locale_code: str = DEFAULT_LOCALE) -> str:
    """A refusal in the user's language, naming the limit (CA-117.6)."""
    key = "backfill_refused_empty" if refusal.days < 1 else "backfill_refused"
    return t(key, locale_code, days=refusal.days, limit=refusal.limit)


def describe(outcomes: list[Outcome], locale_code: str = DEFAULT_LOCALE) -> list[str]:
    """One line per network, as `--backfill` prints them."""
    return [f"{outcome.source:<10}{_worded(outcome, locale_code)}" for outcome in outcomes]


def _worded(outcome: Outcome, locale_code: str) -> str:
    if outcome.status == "not_recoverable":
        reason = t(outcome.reason_key, locale_code) if outcome.reason_key else outcome.detail
        return t("backfill_not_recoverable", locale_code, reason=reason)
    counts = t(
        "backfill_recovered", locale_code, recovered=outcome.recovered, present=outcome.present
    )
    if outcome.skipped:
        counts += t("backfill_skipped", locale_code, skipped=outcome.skipped)
    if outcome.status == "failed":
        failed = t("backfill_failed", locale_code, detail=outcome.detail)
        return f"{failed} ({counts})" if outcome.recovered or outcome.present else failed
    return counts


def exit_code(outcomes: list[Outcome]) -> int:
    """0 if a network was read or there was none to read; 1 if every one that could, failed."""
    readable = [outcome for outcome in outcomes if outcome.status != "not_recoverable"]
    if not readable or any(outcome.status == RECOVERED for outcome in readable):
        return 0
    return 1
