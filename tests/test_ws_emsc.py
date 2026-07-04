"""Tests for the EMSC WebSocket ingestor (RF-01, RF-02, RF-03, RF-04)."""

from __future__ import annotations

import asyncio
import json

import pytest

from vigia_eew.agent_state import AgentState
from vigia_eew.config import EMSCSource
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.ws_emsc import WSIngestor

# Sample EMSC message (API-SPEC §1.3).
_EMSC_MESSAGE = {
    "action": "create",
    "data": {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-66.90, 10.48, 12.0]},
        "id": "20260628_0000123",
        "properties": {
            "lat": 10.48,
            "lon": -66.90,
            "depth": 12.0,
            "mag": 6.1,
            "magtype": "mw",
            "time": "2026-06-28T13:39:00.0Z",
            "lastupdate": "2026-06-28T13:41:00.0Z",
            "unid": "20260628_0000123",
            "flynn_region": "NEAR COAST OF VENEZUELA",
        },
    },
}


# --- Test doubles for the WebSocket transport ---


class _FakeWS:
    """Fake WS connection: context manager + async iterator of messages."""

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
    """Injectable connection factory that records the kwargs (keepalive)."""

    def __init__(self, connections):
        self._connections = list(connections)
        self.calls = []

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        return self._connections.pop(0)


class _ControlledSleep:
    """Fake sleep that records waits and breaks the loop after N calls."""

    def __init__(self, break_at):
        self.waits = []
        self._break_at = break_at

    async def __call__(self, seconds):
        self.waits.append(seconds)
        if len(self.waits) >= self._break_at:
            raise asyncio.CancelledError


# --- Message parsing ---


def _ingestor(output=None, **kw):
    return WSIngestor(EMSCSource(), output or asyncio.Queue(), **kw)


def test_parse_valid_message():
    ing = _ingestor()
    msg = ing._parse(json.dumps(_EMSC_MESSAGE))
    assert isinstance(msg, RawMessage)
    assert msg.source == "EMSC"
    assert msg.action == "create"
    assert msg.feature["properties"]["unid"] == "20260628_0000123"


def test_parse_action_update():
    ing = _ingestor()
    raw = dict(_EMSC_MESSAGE, action="update")
    msg = ing._parse(json.dumps(raw))
    assert msg is not None
    assert msg.action == "update"


def test_parse_accepts_bytes():
    ing = _ingestor()
    msg = ing._parse(json.dumps(_EMSC_MESSAGE).encode("utf-8"))
    assert msg is not None and msg.source == "EMSC"


def test_parse_invalid_json_returns_none():
    ing = _ingestor()
    assert ing._parse("{ not json ") is None


def test_parse_without_data_returns_none():
    ing = _ingestor()
    assert ing._parse(json.dumps({"action": "create"})) is None


# --- Connect / reconnect loop ---


async def test_receives_and_enqueues_event():
    output: asyncio.Queue[RawMessage] = asyncio.Queue()
    connect = _FakeConnect([_FakeWS([json.dumps(_EMSC_MESSAGE)])])
    sleep = _ControlledSleep(break_at=1)  # breaks on the first backoff (once messages run out)
    ing = _ingestor(output, connect=connect, sleep=sleep)

    with pytest.raises(asyncio.CancelledError):
        await ing.run()

    msg = output.get_nowait()
    assert msg.source == "EMSC" and msg.action == "create"


async def test_passes_keepalive_to_connect():
    cfg = EMSCSource(ping_interval_s=15, ping_timeout_s=20)
    connect = _FakeConnect([_FakeWS([])])
    sleep = _ControlledSleep(break_at=1)
    ing = WSIngestor(cfg, asyncio.Queue(), connect=connect, sleep=sleep)

    with pytest.raises(asyncio.CancelledError):
        await ing.run()

    _, kwargs = connect.calls[0]
    assert kwargs["ping_interval"] == 15
    assert kwargs["ping_timeout"] == 20


async def test_reconnects_after_drop():
    # 1st connection drops with an error; it must reconnect (2nd connect) after a backoff.
    connect = _FakeConnect(
        [
            _FakeWS([], error=ConnectionResetError("dropped")),
            _FakeWS([json.dumps(_EMSC_MESSAGE)]),
        ]
    )
    sleep = _ControlledSleep(break_at=2)  # allows one reconnect, breaks on the 2nd backoff
    output: asyncio.Queue[RawMessage] = asyncio.Queue()
    ing = _ingestor(output, connect=connect, sleep=sleep)

    with pytest.raises(asyncio.CancelledError):
        await ing.run()

    assert len(connect.calls) == 2  # reconnected
    assert output.get_nowait().action == "create"  # 2nd connection did deliver


async def test_backoff_grows_between_retries():
    # Without jitter, the waits must grow: 1 s, then 2 s.
    connect = _FakeConnect([_FakeWS([]), _FakeWS([]), _FakeWS([])])
    sleep = _ControlledSleep(break_at=2)
    ing = _ingestor(asyncio.Queue(), connect=connect, sleep=sleep, jitter=False)

    with pytest.raises(asyncio.CancelledError):
        await ing.run()

    assert sleep.waits == [1.0, 2.0]


# --- AgentState: connected/reconnecting (RF-34) ---


async def test_connecting_marks_state_connected():
    state = AgentState()
    # Cancelled while still connected (no drop): the state must not switch to
    # "reconnecting" (that path is only hit if the connection actually closes).
    connect = _FakeConnect(
        [_FakeWS([json.dumps(_EMSC_MESSAGE)], error=asyncio.CancelledError())]
    )
    sleep = _ControlledSleep(break_at=1)
    ing = _ingestor(asyncio.Queue(), connect=connect, sleep=sleep, state=state)

    with pytest.raises(asyncio.CancelledError):
        await ing.run()

    assert state.ws_connected is True


async def test_drop_marks_state_reconnecting():
    state = AgentState()
    state.mark_connected()
    connect = _FakeConnect([_FakeWS([], error=ConnectionResetError("dropped")), _FakeWS([])])
    sleep = _ControlledSleep(break_at=1)
    ing = _ingestor(asyncio.Queue(), connect=connect, sleep=sleep, state=state)

    with pytest.raises(asyncio.CancelledError):
        await ing.run()

    assert state.ws_connected is False
