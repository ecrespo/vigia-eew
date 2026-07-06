"""Tests for the GEOFON FDSN poller (RF-39, RF-06, RNF-03)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from vigia_eew.config import Filter, GEOFONSource, ReferencePoint
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.rest_geofon import _KM_PER_DEGREE, GEOFONPoller
from vigia_eew.state import StateStore

# Verified GEOFON `format=text` shape (API-SPEC §4.3): one `#` header, then `|` rows.
_HEADER = (
    "#EventID|Time|Latitude|Longitude|Depth/km|Author|Catalog|Contributor|"
    "ContributorID|MagType|Magnitude|MagAuthor|EventLocationName|EventType"
)
_ROW_1 = (
    "gfz2020smye|2020-01-15T12:00:00.0|10.48|-66.90|12.0|GFZ|GFZ|GFZ|"
    "gfz2020smye|Mw|6.1|GFZ|NEAR COAST OF VENEZUELA|earthquake"
)
_ROW_2 = (
    "gfz2020zzzz|2020-01-15T13:30:00.0|10.60|-68.30|8.0|GFZ|GFZ|GFZ|"
    "gfz2020zzzz|mb|4.5|GFZ|BOCA DE AROA|earthquake"
)
_ROW_QUARRY = (
    "gfz2020blst|2020-01-15T09:00:00.0|10.50|-67.00|1.0|GFZ|GFZ|GFZ|"
    "gfz2020blst|ml|2.9|GFZ|SOMEWHERE|quarry blast"
)


def _body(*rows: str) -> str:
    return "\n".join([_HEADER, *rows]) + "\n"


def _ms(iso: str) -> int:
    dt = datetime.fromisoformat(iso).replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


# --- Test doubles for the httpx client ---


class _FakeResp:
    def __init__(self, status=200, text="", headers=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}


class _FakeClient:
    def __init__(self, resp=None, *, exc=None):
        self._resp = resp
        self._exc = exc
        self.calls: list[dict] = []

    async def get(self, url, *, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if self._exc is not None:
            raise self._exc
        return self._resp


def _poller(tmp_path, client, *, sleep=None):
    state = StateStore(tmp_path / "state.json")
    state.load()
    poller = GEOFONPoller(
        GEOFONSource(),
        ReferencePoint(),
        Filter(),
        state,
        asyncio.Queue(),
        client=client,
        sleep=sleep or asyncio.sleep,
    )
    return poller, state


# --- Query construction (API-SPEC §4.2) ---


async def test_fixed_params_and_no_cursor(tmp_path):
    client = _FakeClient(_FakeResp(text=_body()))
    poller, _ = _poller(tmp_path, client)
    await poller.poll_once()

    params = client.calls[0]["params"]
    assert params["format"] == "text"
    assert params["lat"] == ReferencePoint().lat
    assert params["lon"] == ReferencePoint().lon
    # fdsnws-event radius is in degrees, converted from km.
    assert params["maxradius"] == pytest.approx(Filter().radius_km / _KM_PER_DEGREE)
    assert params["minmagnitude"] == Filter().min_magnitude
    assert params["orderby"] == "time"
    assert "starttime" not in params  # no previous cursor


async def test_params_include_starttime_with_cursor(tmp_path):
    client = _FakeClient(_FakeResp(text=_body()))
    poller, state = _poller(tmp_path, client)
    state.update_geofon_cursor(_ms("2020-01-15T12:00:00"))
    await poller.poll_once()

    params = client.calls[0]["params"]
    assert params["starttime"].startswith("2020-01-15T12:00:00")


# --- Text parsing and emission (API-SPEC §4.3) ---


async def test_emits_one_rawmessage_per_row(tmp_path):
    client = _FakeClient(_FakeResp(text=_body(_ROW_1, _ROW_2)))
    poller, _ = _poller(tmp_path, client)
    await poller.poll_once()

    msgs = [poller._output.get_nowait(), poller._output.get_nowait()]
    assert all(isinstance(m, RawMessage) for m in msgs)
    assert all(m.source == "GEOFON" and m.action == "create" for m in msgs)
    assert {m.feature["EventID"] for m in msgs} == {"gfz2020smye", "gfz2020zzzz"}
    # Columns are keyed by the header names and stripped.
    assert msgs[0].feature["Magnitude"] == "6.1"
    assert msgs[0].feature["EventLocationName"] == "NEAR COAST OF VENEZUELA"


async def test_non_earthquake_rows_are_skipped(tmp_path):
    client = _FakeClient(_FakeResp(text=_body(_ROW_1, _ROW_QUARRY)))
    poller, _ = _poller(tmp_path, client)
    await poller.poll_once()

    msg = poller._output.get_nowait()
    assert msg.feature["EventID"] == "gfz2020smye"
    assert poller._output.empty()  # the quarry blast was dropped


async def test_malformed_row_discarded_without_aborting_batch(tmp_path):
    good, bad = _ROW_1, "gfz2020bad|2020-01-15T14:00:00.0|10.4|only|three"
    client = _FakeClient(_FakeResp(text=_body(bad, good)))
    poller, _ = _poller(tmp_path, client)
    await poller.poll_once()

    msg = poller._output.get_nowait()
    assert msg.feature["EventID"] == "gfz2020smye"  # the valid row still came through
    assert poller._output.empty()


# --- Cursor (RF-06) ---


async def test_advances_and_persists_cursor(tmp_path):
    client = _FakeClient(_FakeResp(text=_body(_ROW_1, _ROW_2)))
    poller, _ = _poller(tmp_path, client)
    await poller.poll_once()

    reloaded = StateStore(tmp_path / "state.json")
    reloaded.load()
    assert reloaded.state.cursor_geofon_ms == _ms("2020-01-15T13:30:00")


async def test_empty_response_does_not_move_cursor(tmp_path):
    client = _FakeClient(_FakeResp(text=_body()))
    poller, state = _poller(tmp_path, client)
    await poller.poll_once()
    assert state.state.cursor_geofon_ms is None


# --- Resilience (RNF-03, API-SPEC §4.4) ---


async def test_204_is_not_an_error(tmp_path):
    client = _FakeClient(_FakeResp(status=204, text=""))
    poller, state = _poller(tmp_path, client)
    wait = await poller.poll_once()  # must not raise
    assert wait == GEOFONSource().poll_interval_s
    assert poller._output.empty()
    assert state.state.cursor_geofon_ms is None


async def test_429_honors_retry_after(tmp_path):
    client = _FakeClient(_FakeResp(status=429, headers={"Retry-After": "120"}))
    poller, state = _poller(tmp_path, client)
    wait = await poller.poll_once()
    assert wait == 120.0
    assert poller._output.empty()
    assert state.state.cursor_geofon_ms is None


async def test_5xx_does_not_break_and_retries(tmp_path):
    client = _FakeClient(_FakeResp(status=503))
    poller, _ = _poller(tmp_path, client)
    wait = await poller.poll_once()  # must not raise
    assert wait == GEOFONSource().poll_interval_s
    assert poller._output.empty()


async def test_timeout_does_not_break(tmp_path):
    client = _FakeClient(exc=httpx.TimeoutException("timeout"))
    poller, state = _poller(tmp_path, client)
    await poller.poll_once()  # must not raise
    assert poller._output.empty()
    assert state.state.cursor_geofon_ms is None


async def test_body_without_header_is_ignored(tmp_path):
    client = _FakeClient(_FakeResp(text=_ROW_1 + "\n"))  # a data row, no header
    poller, state = _poller(tmp_path, client)
    await poller.poll_once()  # must not raise
    assert poller._output.empty()
    assert state.state.cursor_geofon_ms is None


# --- Loop ---


class _ControlledSleep:
    def __init__(self, break_at):
        self.waits: list[float] = []
        self._break_at = break_at

    async def __call__(self, seconds):
        self.waits.append(seconds)
        if len(self.waits) >= self._break_at:
            raise asyncio.CancelledError


async def test_run_polls_and_waits_interval(tmp_path):
    client = _FakeClient(_FakeResp(text=_body(_ROW_1)))
    sleep = _ControlledSleep(break_at=1)
    poller, _ = _poller(tmp_path, client, sleep=sleep)

    with pytest.raises(asyncio.CancelledError):
        await poller.run()

    assert sleep.waits == [float(GEOFONSource().poll_interval_s)]
    assert poller._output.get_nowait().feature["EventID"] == "gfz2020smye"
