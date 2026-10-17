"""The deduplicator keeps the best arrival, not the first (T-140, REQ-PIP-010).

Until v1.0 the arrival that happened to land first won, and everything that
followed was discarded. That is a decision made by network latency. HU-110
moves it to the user: the same earthquake reported by two networks is
presented with the data of the one they ranked higher, **whichever arrived
first**.

The line this must not cross is CA-110.4, and it has its own test: priority
decides whose data prevails, never whether to alert. A network nobody ranked
still wakes you up for an earthquake only it catalogued.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from vigia_eew.config import Dedup, Settings
from vigia_eew.ingest import RawMessage
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.pipeline.filter import GeoFilter
from vigia_eew.pipeline.normalize import Normalizer
from vigia_eew.pipeline.processor import Processor
from vigia_eew.state import StateStore

#: FUNVISIS ahead of GEOFON: the case ADR-026 is written around -- a revised
#: local magnitude against a global network's automatic one.
LOCAL_FIRST = {"FUNVISIS": 0, "GEOFON": 1, "EMSC": 2, "USGS": 3}
GLOBAL_FIRST = {"GEOFON": 0, "FUNVISIS": 1, "EMSC": 2, "USGS": 3}

_WHEN = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _event(
    source: str,
    *,
    id: str,
    magnitude: float = 5.0,
    lat: float = 10.6,
    lon: float = -66.9,
    depth_km: float = 12.0,
    distance_km: float = 20.0,
    trace: str = "",
) -> SeismicEvent:
    return SeismicEvent(
        id=id,
        trace_id=trace or f"tr-{id}",
        source=source,  # type: ignore[arg-type]
        magnitude=magnitude,
        mag_type="mw",
        place="NEAR COAST OF VENEZUELA",
        lat=lat,
        lon=lon,
        depth_km=depth_km,
        time_utc=_WHEN,
        distance_km=distance_km,
        severity="warning",
    )


def _dedup(tmp_path, rank: dict[str, int] | None) -> Deduplicator:
    return Deduplicator(Dedup(), StateStore(tmp_path / "state.json"), priority_rank=rank)


# --- CA-110.1 / CA-110.2 · The better network prevails, whenever it arrives ------


def test_a_higher_priority_arrival_supersedes_the_one_already_alerted(tmp_path) -> None:
    """CA-110.1: it arrives second and still wins."""
    dedup = _dedup(tmp_path, LOCAL_FIRST)
    first = _event("GEOFON", id="gfz-1", magnitude=5.2)
    dedup.register(first)

    verdict = dedup.verdict(_event("FUNVISIS", id="fun-1", magnitude=4.8))

    assert verdict.result == "supersede"
    assert verdict.linked_trace == "tr-gfz-1"
    assert verdict.linked_id == "gfz-1"


def test_a_lower_priority_arrival_is_still_a_duplicate(tmp_path) -> None:
    """The other direction: nothing to improve, so nothing changes on screen."""
    dedup = _dedup(tmp_path, LOCAL_FIRST)
    dedup.register(_event("FUNVISIS", id="fun-1", magnitude=4.8))

    verdict = dedup.verdict(_event("GEOFON", id="gfz-1", magnitude=5.2))

    assert verdict.result == "duplicate"
    assert verdict.linked_id == "fun-1"


def test_inverting_the_priority_inverts_which_arrival_prevails(tmp_path) -> None:
    """CA-110.2, at the deduplicator's level: same two arrivals, opposite verdicts."""
    local = _dedup(tmp_path, LOCAL_FIRST)
    local.register(_event("GEOFON", id="gfz-1", magnitude=5.2))
    assert local.verdict(_event("FUNVISIS", id="fun-1", magnitude=4.8)).result == "supersede"

    globals_ = _dedup(tmp_path / "other", GLOBAL_FIRST)
    globals_.register(_event("GEOFON", id="gfz-1", magnitude=5.2))
    assert globals_.verdict(_event("FUNVISIS", id="fun-1", magnitude=4.8)).result == "duplicate"


def test_with_no_priorities_declared_the_first_arrival_still_wins(tmp_path) -> None:
    """CA-110.6: an unconfigured agent behaves exactly as v0.6.0 did."""
    dedup = _dedup(tmp_path, None)
    dedup.register(_event("GEOFON", id="gfz-1", magnitude=5.2))

    assert dedup.verdict(_event("FUNVISIS", id="fun-1", magnitude=4.8)).result == "duplicate"


def test_the_same_source_twice_is_never_a_supersede(tmp_path) -> None:
    """A network cannot outrank itself; that path is the id check, not this one."""
    dedup = _dedup(tmp_path, LOCAL_FIRST)
    dedup.register(_event("GEOFON", id="gfz-1", magnitude=5.2))

    assert dedup.verdict(_event("GEOFON", id="gfz-2", magnitude=5.2)).result == "duplicate"


def test_a_third_arrival_is_compared_against_the_data_that_prevailed(tmp_path) -> None:
    """The middle network must not win over the best one just by arriving later.

    Registering the superseding arrival *replaces* the signature rather than
    adding a second one, so the next comparison is against what is on screen
    now -- not against the arrival that has already been overruled.
    """
    dedup = _dedup(tmp_path, {"FUNVISIS": 0, "EMSC": 1, "GEOFON": 2})
    dedup.register(_event("GEOFON", id="gfz-1", magnitude=5.2))
    best = _event("FUNVISIS", id="fun-1", magnitude=4.8)
    dedup.register(best, superseding="gfz-1")

    assert dedup.verdict(_event("EMSC", id="emsc-1", magnitude=5.0)).result == "duplicate"


# --- CA-110.3 · What prevails is the whole arrival, distance included -------------


def test_the_prevailing_location_is_the_one_presented(tmp_path) -> None:
    """Epicentre, depth and the distance derived from them travel together.

    The distance is not patched afterwards: it is the one the normalizer
    computed from the prevailing coordinates, which is the only way it can
    stay consistent with them.
    """
    cfg = Settings()
    normalizer = Normalizer(cfg.reference, cfg.severity)
    far = normalizer.normalize(
        RawMessage(
            source="GEOFON",
            action="create",
            feature={
                "EventID": "gfz-1",
                "Magnitude": "5.2",
                "MagType": "mw",
                "EventLocationName": "OFFSHORE VENEZUELA",
                "Latitude": "11.9",
                "Longitude": "-66.9",
                "Depth/km": "40.0",
                "Time": "2026-09-19T12:00:00Z",
            },
        )
    )
    near = normalizer.normalize(
        RawMessage(
            source="GEOFON",
            action="create",
            feature={
                "EventID": "gfz-2",
                "Magnitude": "5.2",
                "MagType": "mw",
                "EventLocationName": "OFFSHORE VENEZUELA",
                "Latitude": "10.6",
                "Longitude": "-66.9",
                "Depth/km": "12.0",
                "Time": "2026-09-19T12:00:00Z",
            },
        )
    )
    assert far is not None and near is not None
    assert far.distance_km != near.distance_km
    assert near.depth_km == 12.0


# --- CA-110.4 · Priority never decides whether to alert ---------------------------


def test_the_lowest_priority_network_alone_still_alerts(tmp_path) -> None:
    """The reason the national network is one of the four, expressed as a test."""
    dedup = _dedup(tmp_path, {"EMSC": 0, "USGS": 1, "GEOFON": 2, "FUNVISIS": 3})

    assert dedup.verdict(_event("FUNVISIS", id="fun-1", magnitude=3.1)).result == "new"


# --- The pipeline end to end ------------------------------------------------------


class _Sink:
    def __init__(self) -> None:
        self.alerted: list[SeismicEvent] = []
        self.updated: list[SeismicEvent] = []


def _processor(tmp_path, rank: dict[str, int] | None, sink: _Sink) -> Processor:
    cfg = Settings()
    queue: asyncio.Queue[Any] = asyncio.Queue()
    return Processor(
        queue,
        Normalizer(cfg.reference, cfg.severity),
        GeoFilter(cfg.filter, now=lambda: _WHEN),
        Deduplicator(Dedup(), StateStore(tmp_path / "state.json"), priority_rank=rank),
        on_alert=sink.alerted.append,
        on_update=sink.updated.append,
    )


def _geofon(event_id: str, magnitude: float) -> RawMessage:
    return RawMessage(
        source="GEOFON",
        action="create",
        feature={
            "EventID": event_id,
            "Magnitude": str(magnitude),
            "MagType": "mw",
            "EventLocationName": "NEAR THE COAST OF VENEZUELA",
            "Latitude": "10.6",
            "Longitude": "-66.9",
            "Depth/km": "12.0",
            "Time": "2026-09-19T12:00:00Z",
        },
    )


def _funvisis(event_id: str, magnitude: float) -> RawMessage:
    """One `maravilla.json` entry, in its own borrowed vocabulary.

    `phone` is the magnitude and `city`/`postalCode` the local time -- the
    template FUNVISIS reused. 08:00 Venezuelan local is 12:00 UTC, which is
    when the GEOFON arrival says the same earthquake happened.
    """
    return RawMessage(
        source="FUNVISIS",
        action="create",
        feature={
            "id": event_id,
            "type": "Feature",
            "properties": {
                "phone": str(magnitude),
                "phoneFormatted": "12.0 km",
                "address": "NEAR THE COAST OF VENEZUELA",
                "country": "Venezuela",
                "city": "08:00",
                "postalCode": "19-09-2026",
            },
            "geometry": {"type": "Point", "coordinates": [-66.9, 10.6]},
        },
    )


async def test_reversing_the_order_reverses_the_magnitude_presented(tmp_path) -> None:
    """CA-110.2 as the task states it, through the real pipeline.

    One alert either way -- what changes is the magnitude the user ends up
    looking at.
    """
    local = _Sink()
    processor = _processor(tmp_path / "local", LOCAL_FIRST, local)
    await processor.process_one(_geofon("gfz-1", 5.2))
    await processor.process_one(_funvisis("fun-1", 4.8))

    assert [e.magnitude for e in local.alerted] == [5.2]
    assert [e.magnitude for e in local.updated] == [4.8]

    globals_ = _Sink()
    processor = _processor(tmp_path / "global", GLOBAL_FIRST, globals_)
    await processor.process_one(_geofon("gfz-1", 5.2))
    await processor.process_one(_funvisis("fun-1", 4.8))

    assert [e.magnitude for e in globals_.alerted] == [5.2]
    assert globals_.updated == []


async def test_the_superseding_arrival_refreshes_instead_of_alerting_again(tmp_path) -> None:
    """One earthquake, one alert. The better data updates it; it does not repeat it."""
    sink = _Sink()
    processor = _processor(tmp_path, LOCAL_FIRST, sink)
    await processor.process_one(_geofon("gfz-1", 5.2))
    await processor.process_one(_funvisis("fun-1", 4.8))

    assert len(sink.alerted) == 1
    assert len(sink.updated) == 1
    refreshed = sink.updated[0]
    assert refreshed.action == "update"
    assert refreshed.supersedes == "gfz-1"


async def test_a_low_priority_arrival_alone_still_produces_its_alert(tmp_path) -> None:
    """CA-110.4 through the pipeline: nobody else reported it, so it alerts."""
    sink = _Sink()
    processor = _processor(tmp_path, GLOBAL_FIRST, sink)

    await processor.process_one(_funvisis("fun-1", 4.8))

    assert [e.source for e in sink.alerted] == ["FUNVISIS"]
