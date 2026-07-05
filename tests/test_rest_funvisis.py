"""Tests for the FUNVISIS poller (Venezuela-only local coverage, RF-05, RNF-03)."""

from __future__ import annotations

import asyncio

import httpx

from vigia_eew.config import FUNVISISSource
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.rest_funvisis import FUNVISISPoller, _funvisis_id


def _feature(*, lat, lon, mag, depth, time, date="05-07-2026", place="foo"):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat], "marcador": "marker"},
        "properties": {
            "phoneFormatted": depth,
            "phone": mag,
            "address": place,
            "city": time,
            "country": "Venezuela",
            "postalCode": date,
            "state": depth,
            "lat": str(lat),
            "long": str(lon),
        },
    }


_F1 = _feature(lat=10.64, lon=-67.52, mag="2.3", depth="9.8 km", time="09:18")
_F2 = _feature(lat=10.50, lon=-68.47, mag="3.1", depth="5.4 km", time="08:36")
_F3 = _feature(lat=9.35, lon=-68.74, mag="2.8", depth="32.0 km", time="10:05")


def _collection(*features):
    return {"type": "FeatureCollection", "features": list(features)}


class _FakeResp:
    def __init__(self, status=200, payload=None, json_error=False):
        self.status_code = status
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("invalid json")
        return self._payload


class _FakeClient:
    """Returns queued responses (one per call); raises `exc` on every call if given."""

    def __init__(self, responses=None, *, exc=None):
        self._responses = list(responses or [])
        self._exc = exc
        self.calls: list[dict] = []

    async def get(self, url, *, timeout=None):
        self.calls.append({"url": url, "timeout": timeout})
        if self._exc is not None:
            raise self._exc
        return self._responses.pop(0)


def _poller(client):
    return FUNVISISPoller(FUNVISISSource(), asyncio.Queue(), client=client)


def _drain(poller):
    out = []
    while True:
        try:
            out.append(poller._output.get_nowait())
        except asyncio.QueueEmpty:
            return out


# --- Anti-spam: the first poll seeds the seen-set and emits nothing ---


async def test_first_poll_emits_nothing_but_seeds(tmp_path):
    client = _FakeClient([_FakeResp(payload=_collection(_F1, _F2))])
    poller = _poller(client)
    await poller.poll_once()
    assert _drain(poller) == []  # events present at startup are not alerted
    assert poller._seen == {_funvisis_id(_F1), _funvisis_id(_F2)}


async def test_second_poll_emits_only_new_events(tmp_path):
    client = _FakeClient(
        [
            _FakeResp(payload=_collection(_F1, _F2)),  # startup batch -> seeded, silent
            _FakeResp(payload=_collection(_F3, _F1, _F2)),  # F3 is new
        ]
    )
    poller = _poller(client)
    await poller.poll_once()
    await poller.poll_once()

    msgs = _drain(poller)
    assert len(msgs) == 1
    assert all(isinstance(m, RawMessage) for m in msgs)
    assert msgs[0].source == "FUNVISIS" and msgs[0].action == "create"
    assert msgs[0].feature["id"] == _funvisis_id(_F3)


async def test_same_event_not_reemitted_across_polls(tmp_path):
    client = _FakeClient(
        [
            _FakeResp(payload=_collection(_F1)),
            _FakeResp(payload=_collection(_F3, _F1)),  # F3 new
            _FakeResp(payload=_collection(_F3, _F1)),  # nothing new
        ]
    )
    poller = _poller(client)
    for _ in range(3):
        await poller.poll_once()
    assert len(_drain(poller)) == 1  # only F3, once


# --- The poller injects the deterministic id onto the feature ---


async def test_injects_deterministic_id(tmp_path):
    client = _FakeClient(
        [_FakeResp(payload=_collection(_F1)), _FakeResp(payload=_collection(_F2, _F1))]
    )
    poller = _poller(client)
    await poller.poll_once()
    await poller.poll_once()
    msg = _drain(poller)[0]
    assert msg.feature["id"] == "funvisis-05-07-2026-08:36-10.5--68.47"


# --- Resilience: failures never crash and never emit ---


async def test_network_error_is_swallowed(tmp_path):
    poller = _poller(_FakeClient(exc=httpx.ConnectTimeout("boom")))
    wait = await poller.poll_once()
    assert wait == float(FUNVISISSource().poll_interval_s)
    assert _drain(poller) == []
    assert poller._seen is None  # not seeded, so a later good poll still seeds silently


async def test_non_200_is_swallowed(tmp_path):
    poller = _poller(_FakeClient([_FakeResp(status=503, payload=None)]))
    await poller.poll_once()
    assert _drain(poller) == []
    assert poller._seen is None


async def test_invalid_json_is_swallowed(tmp_path):
    poller = _poller(_FakeClient([_FakeResp(json_error=True)]))
    await poller.poll_once()
    assert _drain(poller) == []


async def test_features_not_a_list_is_swallowed(tmp_path):
    poller = _poller(_FakeClient([_FakeResp(payload={"features": "nope"})]))
    await poller.poll_once()
    assert _drain(poller) == []


async def test_run_polls_then_sleeps_until_cancelled(tmp_path):
    # One good poll then a sentinel to stop the loop via CancelledError on sleep.
    client = _FakeClient([_FakeResp(payload=_collection(_F1))])

    async def _stop(_seconds):
        raise asyncio.CancelledError

    poller = FUNVISISPoller(FUNVISISSource(), asyncio.Queue(), client=client, sleep=_stop)
    try:
        await poller.run()
    except asyncio.CancelledError:
        pass
    assert client.calls  # it polled at least once
