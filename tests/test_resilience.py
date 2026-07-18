"""End-to-end resilience tests (Phase 7, F7-4; CA-02, CA-04, CA-05, CA-07).

The unit-level failure scenarios (WS down, 429/5xx, invalid JSON, restart) are already
covered where each component was implemented (`test_ws_emsc.py`, `test_rest_usgs.py`,
`test_supervisor.py`, `test_dedup.py`, `test_state.py`). This module closes the
remaining gap: the same acceptance criteria but **through the full pipeline**
(`Processor` with real `Normalizer`/`GeoFilter`/`Deduplicator`) or combining two
components that so far were only tested separately (`WSIngestor` inside a real
`Supervisor`).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from vigia_eew.config import Dedup, EMSCSource, Filter, ReferencePoint, Severity
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.ws_emsc import WSIngestor
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.pipeline.filter import GeoFilter
from vigia_eew.pipeline.normalize import Normalizer
from vigia_eew.pipeline.processor import Processor
from vigia_eew.state import StateStore
from vigia_eew.supervisor import Supervisor

# --- Raw fixtures: the same earthquake (M6.1, near Caracas) reported by both sources ---

_EMSC_PROPS = {
    "lat": 10.60,
    "lon": -66.93,
    "depth": 12.0,
    "mag": 6.1,
    "magtype": "mw",
    "time": "2026-06-28T13:39:00.0Z",
    "unid": "emsc-1",
    "flynn_region": "NEAR COAST OF VENEZUELA",
}


def _raw_emsc(action="create", **props) -> RawMessage:
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-66.93, 10.60, 12.0]},
        "id": "emsc-1",
        "properties": {**_EMSC_PROPS, **props},
    }
    return RawMessage(source="EMSC", action=action, feature=feature)


def _raw_usgs(
    *, id_="us-1", lat=10.60, lon=-66.93, depth=12.0, mag=6.1, time: datetime
) -> RawMessage:
    feature = {
        "type": "Feature",
        "id": id_,
        "properties": {
            "mag": mag,
            "place": "19 km WSW of Morón, Venezuela",
            "time": int(time.timestamp() * 1000),
            "magType": "mw",
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat, depth]},
    }
    return RawMessage(source="USGS", action="create", feature=feature)


class _Capture:
    def __init__(self):
        self.alerted: list = []
        self.updated: list = []


def _processor(tmp_path, capture, state=None):
    state = state or StateStore(tmp_path / "state.json")
    state.load()
    input_queue: asyncio.Queue[RawMessage] = asyncio.Queue()
    proc = Processor(
        input_queue,
        Normalizer(ReferencePoint(), Severity()),
        # today_only=False: these fixtures use a fixed 2026-06-28 date unrelated to the
        # freshness filter (RF-40), which has its own dedicated tests in test_filter.py.
        GeoFilter(Filter(today_only=False)),
        Deduplicator(Dedup(), state),
        on_alert=capture.alerted.append,
        on_update=capture.updated.append,
    )
    return proc, state


# --- CA-04: the USGS backup alone delivers an alert through the whole pipeline ---


async def test_usgs_only_event_generates_alert_via_full_pipeline(tmp_path):
    """An event the WS never saw (only arrived via USGS) still triggers an alert (RF-05, OBJ-3)."""
    cap = _Capture()
    proc, _ = _processor(tmp_path, cap)
    time = datetime(2026, 6, 28, 13, 39, 0, tzinfo=UTC)
    await proc.process_one(_raw_usgs(time=time))
    assert [e.id for e in cap.alerted] == ["us-1"]
    assert cap.alerted[0].source == "USGS"


# --- CA-05: the same earthquake from both sources produces a single alert, in the real pipeline ---


async def test_same_earthquake_from_both_sources_yields_a_single_alert(tmp_path):
    cap = _Capture()
    proc, _ = _processor(tmp_path, cap)

    await proc.process_one(_raw_emsc())  # EMSC arrives first -> alert
    usgs_time = datetime(2026, 6, 28, 13, 39, 25, tzinfo=UTC)  # 25 s later (window_s=90)
    await proc.process_one(
        _raw_usgs(id_="us-1", lat=10.62, lon=-66.95, mag=6.3, time=usgs_time)  # close, Δmag=0.2
    )

    assert len(cap.alerted) == 1  # the USGS report was deduplicated, not a 2nd alert
    assert cap.alerted[0].source == "EMSC"


async def test_same_earthquake_outside_heuristic_is_not_deduplicated(tmp_path):
    """Negative control: if magnitude differs more than tolerated, treat as another earthquake."""
    cap = _Capture()
    proc, _ = _processor(tmp_path, cap)

    await proc.process_one(_raw_emsc())
    usgs_time = datetime(2026, 6, 28, 13, 39, 25, tzinfo=UTC)
    await proc.process_one(
        _raw_usgs(id_="us-2", lat=10.62, lon=-66.95, mag=3.0, time=usgs_time)  # Δmag=3.1 > 0.5
    )

    assert len(cap.alerted) == 2  # no heuristic links them: two distinct earthquakes


# --- CA-07: after "restarting" the agent (StateStore reopened from disk), no re-alert ---


async def test_agent_restart_does_not_realert_a_previously_seen_event(tmp_path):
    state_path = tmp_path / "state.json"
    cap1 = _Capture()
    proc1, _ = _processor(tmp_path, cap1, state=StateStore(state_path))
    await proc1.process_one(_raw_emsc())
    assert len(cap1.alerted) == 1

    # "Restart": new Processor+StateStore instance reading the same file.
    cap2 = _Capture()
    proc2, _ = _processor(tmp_path, cap2, state=StateStore(state_path))
    await proc2.process_one(_raw_emsc())  # same id as before the restart

    assert cap2.alerted == []  # already alerted; the restart does not repeat it


# --- CA-02 at integration level: real WSIngestor running inside a real Supervisor ---


class _FakeWS:
    def __init__(self, messages, *, error=None):
        self._messages = list(messages)
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages:
            return self._messages.pop(0)
        if self._error is not None:
            raise self._error
        raise StopAsyncIteration


class _FakeConnect:
    def __init__(self, connections):
        self._connections = list(connections)

    def __call__(self, url, **kw):
        return self._connections.pop(0)


async def test_supervisor_keeps_the_ws_ingestor_alive_after_a_drop():
    """The real, supervised WSIngestor keeps delivering messages after a drop (CA-02)."""
    import json

    message = json.dumps(
        {
            "action": "create",
            "data": {
                "type": "Feature",
                "id": "x",
                "geometry": {"type": "Point", "coordinates": [-66.9, 10.48, 12.0]},
                "properties": {**_EMSC_PROPS, "unid": "emsc-1"},
            },
        }
    )
    connect = _FakeConnect(
        [
            _FakeWS([], error=ConnectionResetError("simulated drop")),
            _FakeWS([message]),
        ]
    )

    async def fast_sleep(_seconds):
        await asyncio.sleep(0)  # no need to actually wait in the test

    output: asyncio.Queue[RawMessage] = asyncio.Queue()
    ingestor = WSIngestor(EMSCSource(), output, connect=connect, sleep=fast_sleep, jitter=False)

    sup = Supervisor(sleep=fast_sleep, jitter=False, handle_signals=False)
    sup.add("ws", ingestor.run)

    run_task = asyncio.create_task(sup.run())
    try:
        msg = await asyncio.wait_for(output.get(), timeout=1.0)
    finally:
        sup.request_stop()
        await asyncio.wait_for(run_task, timeout=1.0)

    assert msg.source == "EMSC" and msg.feature["properties"]["unid"] == "emsc-1"
