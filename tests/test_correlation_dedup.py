"""Tests for correlation across deduplication and presentation (REQ-OBS-002, HU-105).

Deduplication is where the journey would otherwise break. Two arrivals of one
earthquake come in with two ids from two networks; one wins and the other is
discarded. Dropping the loser's correlation id leaves exactly the gap this
requirement exists to close -- *why did the second arrival not produce an
alert?* -- so the deduplicator links them instead of forgetting one.

The id also has to stay inside the process (invariant I-4). It is our tracing,
of no use to a seismic network and not theirs to log.
"""

from __future__ import annotations

import logging
from dataclasses import astuple, fields
from datetime import UTC, datetime, timedelta

from vigia_eew.config import Dedup
from vigia_eew.models import AlertedId, SeismicEvent
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.state import StateStore

_BASE = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _event(*, id: str, trace_id: str, source: str = "EMSC", action: str = "create", **kw):
    fields = {
        "magnitude": 6.1,
        "mag_type": "mw",
        "lat": 10.5,
        "lon": -66.9,
        "depth_km": 10.0,
        "time_utc": _BASE,
        "distance_km": 10.0,
        "severity": "critical",
    }
    fields.update(kw)
    return SeismicEvent(id=id, trace_id=trace_id, source=source, action=action, **fields)


def _dedup(tmp_path) -> Deduplicator:
    return Deduplicator(Dedup(), StateStore(tmp_path / "state.json"))


def test_a_cross_source_duplicate_is_linked_to_the_survivor(tmp_path) -> None:
    """CA-105.2: both arrivals of one earthquake end up on one journey."""
    dedup = _dedup(tmp_path)
    first = _event(id="emsc-1", trace_id="trace-first", source="EMSC")
    dedup.register(first)

    second = _event(
        id="usgs-9", trace_id="trace-second", source="USGS", time_utc=_BASE + timedelta(seconds=30)
    )
    verdict = dedup.verdict(second)

    assert verdict.result == "duplicate"
    assert verdict.linked_trace == "trace-first"


def test_the_link_is_written_where_someone_can_search_for_it(tmp_path, caplog) -> None:
    """CA-105.2: the log carries both ids, which is what makes the link usable."""
    dedup = _dedup(tmp_path)
    dedup.register(_event(id="emsc-1", trace_id="trace-first"))

    with caplog.at_level(logging.INFO):
        dedup.verdict(
            _event(
                id="usgs-9",
                trace_id="trace-second",
                source="USGS",
                time_utc=_BASE + timedelta(seconds=30),
            )
        )

    assert "trace-second" in caplog.text
    assert "trace-first" in caplog.text


def test_an_update_stays_on_the_same_journey(tmp_path) -> None:
    """CA-105.4: a revision continues the flow instead of starting a new one."""
    dedup = _dedup(tmp_path)
    dedup.register(_event(id="emsc-1", trace_id="trace-first"))

    verdict = dedup.verdict(
        _event(id="emsc-1", trace_id="trace-revision", action="update", magnitude=6.4)
    )

    assert verdict.result == "update"
    assert verdict.linked_trace == "trace-first"


def test_a_new_event_has_nothing_to_link_to(tmp_path) -> None:
    """A first arrival starts its own journey; linking it anywhere would be a lie."""
    verdict = _dedup(tmp_path).verdict(_event(id="emsc-1", trace_id="trace-first"))
    assert verdict.result == "new"
    assert verdict.linked_trace is None


def test_state_written_before_correlation_still_loads(tmp_path) -> None:
    """A state file from v0.6.0 has no trace ids, and must not break the upgrade."""
    store = StateStore(tmp_path / "state.json")
    store.register_alerted(AlertedId(id="old-1", source="EMSC", time_utc=_BASE))
    store.save()

    reloaded = StateStore(tmp_path / "state.json")
    reloaded.load()
    assert reloaded.already_alerted("old-1")
    assert reloaded.trace_of("old-1") is None


def test_the_trace_id_never_reaches_the_user_facing_payload() -> None:
    """CA-105.5: it is not in what leaves the process, nor in what is shown.

    Every outgoing request this agent makes is built from configuration --
    a catalogue URL and its query parameters -- never from an event. The
    reachable surface where an event's fields *do* get rendered is the alert
    payload, so that is what is checked here.
    """
    from vigia_eew.notify.presentation import format_event, toast_text

    event = _event(id="emsc-1", trace_id="trace-secret")

    data = format_event(event, reference_name="Caracas")
    assert "trace_id" not in {f.name for f in fields(data)}
    assert "trace-secret" not in " ".join(str(v) for v in astuple(data))

    title, message = toast_text(event, reference_name="Caracas")
    assert "trace-secret" not in title + message
