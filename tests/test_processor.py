"""Tests for the pipeline processor (joins normalize->filter->dedup, RF-07..RF-13)."""

from __future__ import annotations

import asyncio

import pytest

from vigia_eew.config import Dedup, Filter, ReferencePoint, Severity
from vigia_eew.ingest import RawMessage
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.pipeline.filter import GeoFilter
from vigia_eew.pipeline.normalize import Normalizer
from vigia_eew.pipeline.processor import Processor
from vigia_eew.state import StateStore

_PROPS = {
    "lat": 10.60,
    "lon": -66.93,
    "depth": 12.0,
    "mag": 6.1,
    "magtype": "mw",
    "time": "2026-06-28T13:39:00.0Z",
    "unid": "emsc-1",
    "flynn_region": "NEAR COAST OF VENEZUELA",
}


def _raw(action="create", **props) -> RawMessage:
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-66.93, 10.60, 12.0]},
        "id": "emsc-1",
        "properties": {**_PROPS, **props},
    }
    return RawMessage(source="EMSC", action=action, feature=feature)


class _Capture:
    def __init__(self):
        self.alerted: list[SeismicEvent] = []
        self.updated: list[SeismicEvent] = []


def _processor(tmp_path, capture, *, radius=300.0):
    state = StateStore(tmp_path / "state.json")
    state.load()
    input_queue: asyncio.Queue[RawMessage] = asyncio.Queue()
    proc = Processor(
        input_queue,
        Normalizer(ReferencePoint(), Severity()),
        # today_only=False: this fixture uses a fixed 2026-06-28 date unrelated to the
        # freshness filter (RF-40), which has its own dedicated tests in test_filter.py.
        GeoFilter(Filter(radius_km=radius, today_only=False)),
        Deduplicator(Dedup(), state),
        on_alert=capture.alerted.append,
        on_update=capture.updated.append,
    )
    return proc, input_queue


async def test_new_relevant_event_alerts(tmp_path):
    cap = _Capture()
    proc, _ = _processor(tmp_path, cap)
    await proc.process_one(_raw())
    assert [e.id for e in cap.alerted] == ["emsc-1"]


async def test_event_outside_radius_does_not_alert(tmp_path):
    cap = _Capture()
    proc, _ = _processor(tmp_path, cap, radius=1.0)  # tiny radius
    await proc.process_one(_raw())
    assert cap.alerted == []


async def test_invalid_raw_message_does_not_alert(tmp_path):
    cap = _Capture()
    proc, _ = _processor(tmp_path, cap)
    await proc.process_one(RawMessage(source="EMSC", action="create", feature={"properties": {}}))
    assert cap.alerted == []


async def test_duplicate_does_not_alert_twice(tmp_path):
    cap = _Capture()
    proc, _ = _processor(tmp_path, cap)
    await proc.process_one(_raw())
    await proc.process_one(_raw())  # same id
    assert len(cap.alerted) == 1


async def test_update_refreshes_without_alerting(tmp_path):
    cap = _Capture()
    proc, _ = _processor(tmp_path, cap)
    await proc.process_one(_raw())  # create (alerts + registers)
    await proc.process_one(_raw(action="update", mag=6.4))
    assert len(cap.alerted) == 1
    assert [e.magnitude for e in cap.updated] == [6.4]


async def test_run_consumes_from_the_queue(tmp_path):
    cap = _Capture()
    proc, input_queue = _processor(tmp_path, cap)
    input_queue.put_nowait(_raw())
    task = asyncio.create_task(proc.run())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert [e.id for e in cap.alerted] == ["emsc-1"]
