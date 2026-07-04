"""Tests for the USGS REST reconciler (RF-05, RF-06, RNF-03)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from vigia_eew.config import Filter, ReferencePoint, USGSSource
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.rest_usgs import RESTReconciler
from vigia_eew.state import StateStore

# Sample USGS response (API-SPEC §2.4), trimmed.
_FEATURE = {
    "type": "Feature",
    "id": "us6000t8sx",
    "properties": {
        "mag": 4.3,
        "place": "19 km WSW of Morón, Venezuela",
        "time": 1782639238852,
        "updated": 1782655565862,
        "magType": "mb",
        "type": "earthquake",
    },
    "geometry": {"type": "Point", "coordinates": [-68.3766, 10.4497, 10]},
}
_FEATURE_2 = {
    "type": "Feature",
    "id": "us6000t900",
    "properties": {"mag": 4.5, "place": "Boca de Aroa", "time": 1782700000000, "magType": "mb"},
    "geometry": {"type": "Point", "coordinates": [-68.3, 10.6, 12]},
}


def _collection(*features):
    return {"type": "FeatureCollection", "metadata": {"status": 200}, "features": list(features)}


# --- Test doubles for the httpx client ---


class _FakeResp:
    def __init__(self, status=200, payload=None, headers=None, json_error=False):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("invalid json")
        return self._payload


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


def _reconciler(tmp_path, client, *, sleep=None):
    state = StateStore(tmp_path / "state.json")
    state.load()
    rec = RESTReconciler(
        USGSSource(),
        ReferencePoint(),
        Filter(),
        state,
        asyncio.Queue(),
        client=client,
        sleep=sleep or asyncio.sleep,
    )
    return rec, state


# --- Query construction ---


async def test_fixed_params_and_no_cursor(tmp_path):
    client = _FakeClient(_FakeResp(payload=_collection()))
    rec, _ = _reconciler(tmp_path, client)
    await rec.poll_once()

    params = client.calls[0]["params"]
    assert params["format"] == "geojson"
    assert params["latitude"] == ReferencePoint().lat
    assert params["longitude"] == ReferencePoint().lon
    assert params["maxradiuskm"] == Filter().radius_km
    assert params["minmagnitude"] == Filter().min_magnitude
    assert params["orderby"] == "time"
    assert params["eventtype"] == "earthquake"
    assert "starttime" not in params  # no previous cursor


async def test_params_include_starttime_with_cursor(tmp_path):
    client = _FakeClient(_FakeResp(payload=_collection()))
    rec, state = _reconciler(tmp_path, client)
    state.update_usgs_cursor(1782639238852)
    await rec.poll_once()

    params = client.calls[0]["params"]
    assert "starttime" in params
    assert params["starttime"].startswith("2026-")  # ISO-8601 derived from the cursor


# --- Emission and cursor ---


async def test_emits_one_rawmessage_per_feature(tmp_path):
    client = _FakeClient(_FakeResp(payload=_collection(_FEATURE, _FEATURE_2)))
    rec, _ = _reconciler(tmp_path, client)
    await rec.poll_once()

    msgs = [rec._output.get_nowait(), rec._output.get_nowait()]
    assert all(isinstance(m, RawMessage) for m in msgs)
    assert {m.feature["id"] for m in msgs} == {"us6000t8sx", "us6000t900"}
    assert msgs[0].source == "USGS" and msgs[0].action == "create"


async def test_advances_and_persists_cursor(tmp_path):
    client = _FakeClient(_FakeResp(payload=_collection(_FEATURE, _FEATURE_2)))
    rec, _ = _reconciler(tmp_path, client)
    await rec.poll_once()

    # Cursor at the maximum `time` seen and persisted to disk (RF-06).
    reloaded = StateStore(tmp_path / "state.json")
    reloaded.load()
    assert reloaded.state.cursor_usgs_ms == 1782700000000


async def test_empty_response_does_not_move_cursor(tmp_path):
    client = _FakeClient(_FakeResp(payload=_collection()))
    rec, state = _reconciler(tmp_path, client)
    await rec.poll_once()
    assert state.state.cursor_usgs_ms is None


# --- Resilience (RNF-03) ---


async def test_429_honors_retry_after(tmp_path):
    client = _FakeClient(_FakeResp(status=429, headers={"Retry-After": "120"}))
    rec, state = _reconciler(tmp_path, client)
    wait = await rec.poll_once()
    assert wait == 120.0  # honors Retry-After
    assert rec._output.empty()
    assert state.state.cursor_usgs_ms is None  # cursor untouched


async def test_5xx_does_not_break_and_retries(tmp_path):
    client = _FakeClient(_FakeResp(status=503))
    rec, _ = _reconciler(tmp_path, client)
    wait = await rec.poll_once()  # must not raise
    assert wait == USGSSource().poll_interval_s
    assert rec._output.empty()


async def test_timeout_does_not_break(tmp_path):
    client = _FakeClient(exc=httpx.TimeoutException("timeout"))
    rec, state = _reconciler(tmp_path, client)
    await rec.poll_once()  # must not raise
    assert rec._output.empty()
    assert state.state.cursor_usgs_ms is None


async def test_invalid_json_does_not_break(tmp_path):
    client = _FakeClient(_FakeResp(payload=None, json_error=True))
    rec, _ = _reconciler(tmp_path, client)
    await rec.poll_once()  # must not raise
    assert rec._output.empty()


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
    client = _FakeClient(_FakeResp(payload=_collection(_FEATURE)))
    sleep = _ControlledSleep(break_at=1)
    rec, _ = _reconciler(tmp_path, client, sleep=sleep)

    with pytest.raises(asyncio.CancelledError):
        await rec.run()

    assert sleep.waits == [float(USGSSource().poll_interval_s)]
    assert rec._output.get_nowait().feature["id"] == "us6000t8sx"
