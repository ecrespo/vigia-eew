"""Tests for the alert controller (orchestrates queue + window + sound + toast)."""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.agent_state import AgentState
from vigia_eew.models import SeismicEvent
from vigia_eew.notify.controller import AlertController


def _ev(id="e1", action="create", mag=6.1) -> SeismicEvent:
    return SeismicEvent(
        id=id,
        source="EMSC",
        magnitude=mag,
        mag_type="mw",
        place="La Guaira",
        lat=10.6,
        lon=-66.93,
        depth_km=10.0,
        time_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distance_km=15.0,
        severity="critical",
        action=action,
    )


class _FakeWindow:
    def __init__(self, data, severity, on_acknowledge):
        self.data = data
        self.severity = severity
        self.on_acknowledge = on_acknowledge
        self.refreshed = None

    def refresh(self, data):
        self.refreshed = data


class _Cap:
    def __init__(self):
        self.windows: list[_FakeWindow] = []
        self.sounds: list[str] = []
        self.toasts: list[SeismicEvent] = []

    def create_window(self, data, severity, on_acknowledge):
        w = _FakeWindow(data, severity, on_acknowledge)
        self.windows.append(w)
        return w


def _controller(cap, *, with_sound=True, with_toast=True):
    return AlertController(
        create_window=cap.create_window,
        play_sound=cap.sounds.append if with_sound else None,
        send_toast=cap.toasts.append if with_toast else None,
        reference_name="Caracas",
    )


def test_enqueue_shows_window_sound_and_toast():
    cap = _Cap()
    ctrl = _controller(cap)
    ctrl.enqueue(_ev())
    assert len(cap.windows) == 1
    assert cap.windows[0].data.magnitude == "M 6.1"
    assert cap.sounds == ["critical"]
    assert [e.id for e in cap.toasts] == ["e1"]


def test_one_at_a_time_and_acknowledge_shows_next():
    cap = _Cap()
    ctrl = _controller(cap)
    ctrl.enqueue(_ev("a"))
    ctrl.enqueue(_ev("b"))
    assert len(cap.windows) == 1  # b waits
    cap.windows[0].on_acknowledge()  # user clicks ACKNOWLEDGED
    assert len(cap.windows) == 2
    assert cap.windows[1].data is not None


def test_update_refreshes_current_window():
    cap = _Cap()
    ctrl = _controller(cap)
    ctrl.enqueue(_ev("x", mag=6.1))
    ctrl.enqueue(_ev("x", action="update", mag=6.5))
    assert len(cap.windows) == 1  # no new window created
    assert cap.windows[0].refreshed is not None
    assert cap.windows[0].refreshed.magnitude == "M 6.5"


def test_without_sound_or_toast_does_not_fail():
    cap = _Cap()
    ctrl = _controller(cap, with_sound=False, with_toast=False)
    ctrl.enqueue(_ev())
    assert len(cap.windows) == 1
    assert cap.sounds == [] and cap.toasts == []


# --- Pause/resume (RF-34) ---


def test_pause_and_resume_delegate_to_the_queue():
    cap = _Cap()
    ctrl = _controller(cap)
    ctrl.pause()
    assert ctrl.paused is True
    ctrl.enqueue(_ev("a"))
    assert cap.windows == []  # not shown while paused
    ctrl.resume()
    assert ctrl.paused is False
    assert len(cap.windows) == 1


# --- AgentState: last alert (RF-34) ---


def test_show_updates_agent_state():
    cap = _Cap()
    state = AgentState()
    ctrl = AlertController(
        create_window=cap.create_window, reference_name="Caracas", state=state
    )
    ctrl.enqueue(_ev())
    assert state.last_alert is not None
    assert "M 6.1" in state.last_alert
    assert "La Guaira" in state.last_alert
