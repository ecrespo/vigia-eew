"""The pipeline records what it decided (T-143, REQ-HIS-001/002/006, HU-111).

Two things are being checked here and they pull in opposite directions.

The history has to be **complete** -- every evaluated arrival, with the reason
for every discard, because "why was I not warned about that earthquake?" is
the question it exists to answer.

And it has to be **incapable of costing an alert**. Art. 1: the history is a
consequence of an alert, never a condition of one. The test that matters most
in this file is the one where the history cannot be written at all.
"""

from __future__ import annotations

import asyncio
import logging
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from vigia_eew.config import Dedup, Settings
from vigia_eew.history import EventRecord, HistoryStore, HistoryWriter
from vigia_eew.ingest import RawMessage
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.pipeline.filter import GeoFilter
from vigia_eew.pipeline.normalize import Normalizer
from vigia_eew.pipeline.processor import Processor
from vigia_eew.state import StateStore

_WHEN = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

LOCAL_FIRST = {"FUNVISIS": 0, "GEOFON": 1, "EMSC": 2, "USGS": 3}


def _geofon(event_id: str, magnitude: float, *, lat: str = "10.6") -> RawMessage:
    return RawMessage(
        source="GEOFON",
        action="create",
        feature={
            "EventID": event_id,
            "Magnitude": str(magnitude),
            "MagType": "mw",
            "EventLocationName": "NEAR THE COAST OF VENEZUELA",
            "Latitude": lat,
            "Longitude": "-66.9",
            "Depth/km": "12.0",
            "Time": "2026-09-19T12:00:00Z",
        },
    )


def _funvisis(event_id: str, magnitude: float) -> RawMessage:
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


class _Recorder:
    """Stands in for the writer: records what it was handed, nothing else."""

    def __init__(self) -> None:
        self.records: list[EventRecord] = []

    def __call__(self, record: EventRecord) -> None:
        self.records.append(record)


def _processor(
    tmp_path: Path,
    recorder: Any,
    *,
    rank: dict[str, int] | None = None,
) -> Processor:
    cfg = Settings()
    queue: asyncio.Queue[Any] = asyncio.Queue()
    return Processor(
        queue,
        Normalizer(cfg.reference, cfg.severity),
        GeoFilter(cfg.filter, now=lambda: _WHEN),
        Deduplicator(Dedup(), StateStore(tmp_path / "state.json"), priority_rank=rank),
        on_alert=lambda _e: None,
        on_update=lambda _e: None,
        record=recorder,
        now=lambda: _WHEN,
    )


# --- CA-111.1 · An alerted earthquake is recorded --------------------------------


async def test_an_alerted_event_is_recorded_as_alerted(tmp_path: Path) -> None:
    recorder = _Recorder()
    processor = _processor(tmp_path, recorder)

    await processor.process_one(_geofon("gfz-1", 5.2))

    record = recorder.records[0]
    assert record.verdict == "alerted"
    assert record.reason is None
    assert record.severity == "warning"
    assert record.source == "GEOFON"
    assert record.source_event_id == "gfz-1"
    assert record.magnitude == 5.2


async def test_the_record_keeps_the_journey_it_belongs_to(tmp_path: Path) -> None:
    """CA-111.1: the correlation id is what ties the log line to the row."""
    recorder = _Recorder()
    processor = _processor(tmp_path, recorder)
    arrival = _geofon("gfz-1", 5.2)

    await processor.process_one(arrival)

    assert recorder.records[0].correlation_id == arrival.trace_id


async def test_the_distance_recorded_is_the_one_of_that_moment(tmp_path: Path) -> None:
    """Stored, not recomputed: if the user moves, the history still has to say
    how far away the earthquake was *then* (DATA-MODEL §3bis.1)."""
    recorder = _Recorder()
    processor = _processor(tmp_path, recorder)

    await processor.process_one(_geofon("gfz-1", 5.2))

    assert recorder.records[0].distance_km > 0


# --- CA-111.2 · A discarded earthquake is recorded with its reason ----------------


async def test_an_event_outside_the_radius_is_recorded_with_that_reason(
    tmp_path: Path,
) -> None:
    """The question the history exists to answer, in one row."""
    recorder = _Recorder()
    processor = _processor(tmp_path, recorder)

    await processor.process_one(_geofon("gfz-far", 5.2, lat="40.0"))

    record = recorder.records[0]
    assert record.verdict == "discarded"
    assert record.reason == "radius"
    assert record.severity is None


async def test_an_event_below_the_minimum_magnitude_says_so(tmp_path: Path) -> None:
    recorder = _Recorder()
    processor = _processor(tmp_path, recorder)

    await processor.process_one(_geofon("gfz-small", 1.0))

    assert recorder.records[0].reason == "magnitude"


# --- CA-111.3 · A duplicate is linked, not lost -----------------------------------


async def test_a_duplicate_is_recorded_under_the_journey_that_alerted(
    tmp_path: Path,
) -> None:
    recorder = _Recorder()
    processor = _processor(tmp_path, recorder)
    first = _geofon("gfz-1", 5.2)

    await processor.process_one(first)
    await processor.process_one(_funvisis("fun-1", 4.8))

    duplicate = recorder.records[1]
    assert duplicate.verdict == "discarded"
    assert duplicate.reason == "duplicate"
    assert duplicate.correlation_id == first.trace_id


async def test_a_superseding_arrival_is_recorded_as_what_is_now_on_screen(
    tmp_path: Path,
) -> None:
    """It did not raise an alert -- it *is* the alert now. Both rows are true."""
    recorder = _Recorder()
    processor = _processor(tmp_path, recorder, rank=LOCAL_FIRST)
    first = _geofon("gfz-1", 5.2)

    await processor.process_one(first)
    await processor.process_one(_funvisis("fun-1", 4.8))

    prevailing = recorder.records[1]
    assert prevailing.verdict == "alerted"
    assert prevailing.correlation_id == first.trace_id
    assert prevailing.magnitude == 4.8


async def test_a_malformed_payload_records_nothing(tmp_path: Path) -> None:
    """There is no event to record: the normalizer never produced one.

    Inventing a row out of a payload nobody could read would put fiction in
    the one place that exists to be trusted. The discard is in the log, with
    its correlation id.
    """
    recorder = _Recorder()
    processor = _processor(tmp_path, recorder)

    await processor.process_one(RawMessage(source="GEOFON", action="create", feature={}))

    assert recorder.records == []


# --- CA-111.4 / CA-111.5 · The history cannot cost an alert ----------------------


async def test_an_alert_is_presented_before_anything_is_recorded(tmp_path: Path) -> None:
    """CA-111.5: recording is not part of the path from arrival to presentation.

    Asserted by order rather than by a stopwatch: a timing test would measure
    this machine, while the order is the property itself.
    """
    sequence: list[str] = []
    cfg = Settings()
    processor = Processor(
        asyncio.Queue(),
        Normalizer(cfg.reference, cfg.severity),
        GeoFilter(cfg.filter, now=lambda: _WHEN),
        Deduplicator(Dedup(), StateStore(tmp_path / "state.json")),
        on_alert=lambda _e: sequence.append("presented"),
        record=lambda _r: sequence.append("recorded"),
        now=lambda: _WHEN,
    )

    await processor.process_one(_geofon("gfz-1", 5.2))

    assert sequence == ["presented", "recorded"]


async def test_a_history_that_explodes_does_not_stop_the_alert(tmp_path: Path) -> None:
    """CA-111.4, at the pipeline's edge."""
    presented: list[SeismicEvent] = []
    cfg = Settings()

    def explode(_record: EventRecord) -> None:
        raise OSError("read-only file system")

    processor = Processor(
        asyncio.Queue(),
        Normalizer(cfg.reference, cfg.severity),
        GeoFilter(cfg.filter, now=lambda: _WHEN),
        Deduplicator(Dedup(), StateStore(tmp_path / "state.json")),
        on_alert=presented.append,
        record=explode,
        now=lambda: _WHEN,
    )

    await processor.process_one(_geofon("gfz-1", 5.2))

    assert [e.id for e in presented] == ["gfz-1"]


async def test_the_failure_is_written_down_where_somebody_will_see_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A swallowed failure that leaves no trace is a silent one."""
    cfg = Settings()
    processor = Processor(
        asyncio.Queue(),
        Normalizer(cfg.reference, cfg.severity),
        GeoFilter(cfg.filter, now=lambda: _WHEN),
        Deduplicator(Dedup(), StateStore(tmp_path / "state.json")),
        on_alert=lambda _e: None,
        record=lambda _r: (_ for _ in ()).throw(OSError("read-only file system")),
        now=lambda: _WHEN,
    )

    with caplog.at_level(logging.WARNING):
        await processor.process_one(_geofon("gfz-1", 5.2))

    assert "history_record_failed" in caplog.text


async def test_submitting_never_waits_on_the_disk(tmp_path: Path) -> None:
    """The writer's half of REQ-HIS-002: handing a record over is a queue put."""
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.open()
    writer = HistoryWriter(store)

    writer.submit(_a_record())

    assert writer.pending == 1
    assert store.count() == 0  # nothing has touched the file yet
    await writer.write_one(_a_record())
    assert store.count() == 1
    writer.close()


async def test_a_write_that_fails_is_logged_and_swallowed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """CA-111.4 at the writer: the agent keeps running without its history."""
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.open()
    store.close()  # writing now raises: there is no connection
    writer = HistoryWriter(store)

    with caplog.at_level(logging.WARNING):
        await writer.write_one(_a_record())

    assert "history_write_failed" in caplog.text


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes to read-only files anyway")
async def test_a_read_only_history_file_still_lets_the_agent_alert(tmp_path: Path) -> None:
    """CA-111.4 as the task words it, against a real read-only file."""
    locked = tmp_path / "locked"
    locked.mkdir()
    elsewhere = tmp_path / "writable"
    elsewhere.mkdir()
    path = locked / "history.sqlite3"
    store = HistoryStore(path)
    store.open()
    store.close()
    path.chmod(stat.S_IRUSR)
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        reopened = HistoryStore(path)
        presented: list[str] = []
        try:
            reopened.open()
            writer_failed = False
        except Exception:  # noqa: BLE001 - opening a read-only history is allowed to fail
            writer_failed = True

        cfg = Settings()
        processor = Processor(
            asyncio.Queue(),
            Normalizer(cfg.reference, cfg.severity),
            GeoFilter(cfg.filter, now=lambda: _WHEN),
            Deduplicator(Dedup(), StateStore(elsewhere / "state.json")),
            on_alert=lambda e: presented.append(e.id),
            record=(lambda _r: None) if writer_failed else _writer_for(reopened),
            now=lambda: _WHEN,
        )
        await processor.process_one(_geofon("gfz-1", 5.2))

        assert presented == ["gfz-1"]
    finally:
        locked.chmod(stat.S_IRWXU)
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _writer_for(store: HistoryStore):
    def record(entry: EventRecord) -> None:
        store.record(entry)

    return record


def _a_record() -> EventRecord:
    return EventRecord(
        correlation_id="tr-1",
        source="GEOFON",
        source_event_id="gfz-1",
        occurred_at=_WHEN,
        recorded_at=_WHEN,
        latitude=10.6,
        longitude=-66.9,
        depth_km=12.0,
        magnitude=5.2,
        region="NEAR THE COAST OF VENEZUELA",
        distance_km=20.0,
        verdict="alerted",
        severity="warning",
    )


# --- The history is optional, and its absence costs nothing ----------------------


def test_the_history_can_be_turned_off(tmp_path: Path) -> None:
    """`enabled = false` records nothing and supervises nothing."""
    from vigia_eew.agent_state import AgentState
    from vigia_eew.config import History
    from vigia_eew.wiring import Wiring

    cfg = Settings(history=History(enabled=False))
    wiring = Wiring(cfg, StateStore(tmp_path / "state.json"), AgentState())

    assert wiring.build_history() is None
    sup = wiring.build_supervisor(asyncio.Queue(), object())
    assert "history" not in sup.names


def test_a_history_that_cannot_be_opened_does_not_stop_the_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """CA-111.4 at composition: the agent comes up, without its history.

    Best-effort by construction, like the tray and the toast. A read-only
    directory, a file from a newer version, a full disk -- none of them may
    cost an alert.
    """
    import vigia_eew.wiring as wiring_module
    from vigia_eew.agent_state import AgentState
    from vigia_eew.wiring import Wiring

    def refuse(*_args: object, **_kw: object) -> None:
        raise OSError("unable to open database file")

    monkeypatch.setattr(wiring_module.HistoryStore, "open", refuse)
    wiring = Wiring(Settings(), StateStore(tmp_path / "state.json"), AgentState())

    with caplog.at_level(logging.WARNING):
        assert wiring.build_history() is None

    assert "history_unavailable" in caplog.text
    sup = wiring.build_supervisor(asyncio.Queue(), object())
    assert sup.names == ["ws", "rest", "funvisis", "geofon", "pipeline"]
