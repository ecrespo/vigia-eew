"""Tests for the alert queue and the asyncio<->Tk bridge (RF-20, RF-11, ADR-006)."""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.models import SeismicEvent
from vigia_eew.notify.queue import AlertQueue, AsyncioTkBridge


def _ev(id="e1", action="create", mag=6.0) -> SeismicEvent:
    return SeismicEvent(
        id=id,
        source="EMSC",
        magnitude=mag,
        mag_type="mw",
        lat=10.5,
        lon=-66.9,
        depth_km=10.0,
        time_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distance_km=20.0,
        severity="critical",
        action=action,
    )


class _Sink:
    def __init__(self):
        self.shown: list[SeismicEvent] = []
        self.updated: list[SeismicEvent] = []
        self.acknowledged: list[SeismicEvent] = []


def _make_queue(sink: _Sink) -> AlertQueue:
    return AlertQueue(
        show=sink.shown.append,
        update=sink.updated.append,
        on_acknowledge=sink.acknowledged.append,
    )


# --- Queue: one alert at a time, in order (RF-20) ---


def test_shows_on_enqueue():
    s = _Sink()
    q = _make_queue(s)
    q.enqueue(_ev("a"))
    assert [e.id for e in s.shown] == ["a"]
    assert q.current is not None and q.current.id == "a"


def test_one_at_a_time():
    s = _Sink()
    q = _make_queue(s)
    q.enqueue(_ev("a"))
    q.enqueue(_ev("b"))
    assert [e.id for e in s.shown] == ["a"]  # b waits
    assert q.pending == 1


def test_acknowledge_shows_next():
    s = _Sink()
    q = _make_queue(s)
    q.enqueue(_ev("a"))
    q.enqueue(_ev("b"))
    q.acknowledge()
    assert [e.id for e in s.shown] == ["a", "b"]
    assert [e.id for e in s.acknowledged] == ["a"]
    assert q.current is not None and q.current.id == "b"


def test_fifo_order():
    s = _Sink()
    q = _make_queue(s)
    for x in ("a", "b", "c"):
        q.enqueue(_ev(x))
    q.acknowledge()
    q.acknowledge()
    assert [e.id for e in s.shown] == ["a", "b", "c"]


def test_acknowledge_without_current_does_not_break():
    s = _Sink()
    q = _make_queue(s)
    q.acknowledge()  # must not raise
    assert s.shown == []
    assert q.current is None


# --- Pause/resume (RF-34, tray icon) ---


def test_paused_does_not_show_but_enqueues():
    s = _Sink()
    q = _make_queue(s)
    q.pause()
    assert q.paused is True
    q.enqueue(_ev("a"))
    assert s.shown == []  # not shown while paused
    assert q.pending == 1
    assert q.current is None


def test_resume_shows_pending():
    s = _Sink()
    q = _make_queue(s)
    q.pause()
    q.enqueue(_ev("a"))
    q.enqueue(_ev("b"))
    q.resume()
    assert q.paused is False
    assert [e.id for e in s.shown] == ["a"]  # still one at a time
    assert q.pending == 1


def test_pause_does_not_interrupt_the_current_alert():
    s = _Sink()
    q = _make_queue(s)
    q.enqueue(_ev("a"))
    q.pause()
    assert q.current is not None and q.current.id == "a"  # still shown


# --- On-screen update (RF-11) ---


def test_update_of_current_event_refreshes_without_requeuing():
    s = _Sink()
    q = _make_queue(s)
    q.enqueue(_ev("x", mag=6.0))
    q.enqueue(_ev("x", action="update", mag=6.4))
    assert [e.id for e in s.shown] == ["x"]  # not shown again
    assert [e.magnitude for e in s.updated] == [6.4]  # refreshed on screen
    assert q.current is not None and q.current.magnitude == 6.4
    assert q.pending == 0


def test_update_of_another_id_gets_queued():
    s = _Sink()
    q = _make_queue(s)
    q.enqueue(_ev("x"))
    q.enqueue(_ev("y", action="update"))
    assert q.pending == 1
    assert s.updated == []


# --- asyncio<->Tk bridge (ADR-006) ---


def test_bridge_drains_in_order():
    received: list[SeismicEvent] = []
    bridge = AsyncioTkBridge(sink=received.append)
    for x in ("a", "b", "c"):
        bridge.publish(_ev(x))
    bridge.drain()
    assert [e.id for e in received] == ["a", "b", "c"]


def test_bridge_drain_empty_does_nothing():
    received: list[SeismicEvent] = []
    AsyncioTkBridge(sink=received.append).drain()
    assert received == []


class _FakeWidget:
    def __init__(self):
        self.after_calls: list[tuple[int, object]] = []

    def after(self, ms, callback):
        self.after_calls.append((ms, callback))


def test_bridge_start_polling_schedules_after():
    bridge = AsyncioTkBridge(sink=lambda e: None)
    widget = _FakeWidget()
    bridge.start_polling(widget, interval_ms=200)
    assert widget.after_calls[0][0] == 200
    assert callable(widget.after_calls[0][1])
