"""Tests for end-to-end correlation (REQ-OBS-002, HU-105, ADR-021).

An earthquake crosses five stages -- ingestion, normalization, filter,
deduplication, presentation -- and each one logged whatever identifier it
happened to have at hand. Answering "why was I not warned about that one?"
meant reading five logs and guessing which lines belonged together.

A correlation id is generated at ingestion, travels in the internal contract,
and is written by every stage. One search, one journey.

It never leaves the process (invariant I-4): it is an internal reference, and
sending it to a seismic network would be leaking our tracing into somebody
else's logs for no benefit to anyone.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from vigia_eew.config import Filter, ReferencePoint, Severity
from vigia_eew.ingest import RawMessage, new_trace_id
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.filter import GeoFilter
from vigia_eew.pipeline.normalize import Normalizer

_CARACAS = ReferencePoint(name="Caracas", lat=10.5, lon=-66.9)


def _emsc(**overrides) -> RawMessage:
    props = {
        "unid": "20260919_0000042",
        "mag": 6.1,
        "magtype": "mw",
        "flynn_region": "NEAR COAST OF VENEZUELA",
        "lat": 10.6,
        "lon": -66.8,
        "depth": 15.0,
        "time": "2026-09-19T12:00:00Z",
    }
    props.update(overrides.pop("properties", {}))
    return RawMessage(source="EMSC", action="create", feature={"properties": props}, **overrides)


def test_every_raw_message_arrives_with_a_trace_id() -> None:
    """CA-105.1: the id is generated at ingestion, where the journey starts.

    Not at normalization: an event discarded as malformed never reaches the
    normalizer, and that discard is exactly the kind of thing somebody will
    later want to search for.
    """
    assert _emsc().trace_id
    assert _emsc().trace_id != _emsc().trace_id


def test_the_trace_id_survives_normalization() -> None:
    """CA-105.1: the internal contract carries it, so every later stage has it."""
    msg = _emsc()
    event = Normalizer(_CARACAS, Severity()).normalize(msg)
    assert event is not None
    assert event.trace_id == msg.trace_id


def test_an_explicit_trace_id_is_respected() -> None:
    """A source that already has one can pass it rather than start a second."""
    given = new_trace_id()
    assert _emsc(trace_id=given).trace_id == given


def test_normalization_logs_the_trace_of_what_it_discards(caplog) -> None:
    """CA-105.1: a malformed payload is searchable too.

    The discard is the interesting entry: the alert that never happened is
    harder to explain than the one that did.
    """
    msg = RawMessage(source="EMSC", action="create", feature={"properties": {}})
    with caplog.at_level(logging.WARNING):
        assert Normalizer(_CARACAS, Severity()).normalize(msg) is None
    assert msg.trace_id in caplog.text


def test_the_filter_verdict_names_the_reason(caplog) -> None:
    """CA-105.3: a discard says which check rejected it, not just that one did."""
    far_away = SeismicEvent(
        id="e-1",
        trace_id="trace-far",
        source="EMSC",
        magnitude=6.1,
        mag_type="mw",
        lat=-33.0,
        lon=-70.0,
        depth_km=10.0,
        time_utc=datetime.now(UTC),
        distance_km=5000.0,
        severity="critical",
    )
    verdict = GeoFilter(Filter(today_only=False)).verdict(far_away)
    assert not verdict.accepted
    assert verdict.reason == "radius"


def test_the_filter_names_each_of_its_checks() -> None:
    """CA-105.3: the four reasons are distinguishable, which is the point."""
    now = datetime.now(UTC)
    base = {
        "id": "e-1",
        "trace_id": "t",
        "source": "EMSC",
        "mag_type": "mw",
        "lat": 10.5,
        "lon": -66.9,
        "depth_km": 10.0,
        "severity": "critical",
    }
    geo = GeoFilter(Filter(today_only=True, min_magnitude=4.0, radius_km=500))

    accepted = geo.verdict(SeismicEvent(**base, magnitude=6.1, time_utc=now, distance_km=10.0))
    assert accepted.accepted and accepted.reason is None

    small = geo.verdict(SeismicEvent(**base, magnitude=1.0, time_utc=now, distance_km=10.0))
    assert small.reason == "magnitude"

    stale = geo.verdict(
        SeismicEvent(**base, magnitude=6.1, time_utc=now - timedelta(days=3), distance_km=10.0)
    )
    assert stale.reason == "freshness"


def test_accepts_still_answers_yes_or_no() -> None:
    """The boolean form stays: most callers only need the verdict, not the reason."""
    geo = GeoFilter(Filter(today_only=False))
    event = SeismicEvent(
        id="e-1",
        trace_id="t",
        source="EMSC",
        magnitude=6.1,
        mag_type="mw",
        lat=10.5,
        lon=-66.9,
        depth_km=10.0,
        time_utc=datetime.now(UTC),
        distance_km=10.0,
        severity="critical",
    )
    assert geo.accepts(event) is True
