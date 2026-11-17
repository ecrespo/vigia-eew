"""Tests for the alert controller (orchestrates queue + window + sound + toast)."""

from __future__ import annotations

import contextlib
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
    ctrl = AlertController(create_window=cap.create_window, reference_name="Caracas", state=state)
    ctrl.enqueue(_ev())
    assert state.last_alert is not None
    assert "M 6.1" in state.last_alert
    assert "La Guaira" in state.last_alert


def test_the_window_is_logged_as_shown_only_once_it_exists(caplog):
    """REQ-OPS-008: the release smoke waits for this line, so it must mean it."""
    cap = _Cap()
    with caplog.at_level("INFO", logger="vigia_eew.notify.controller"):
        _controller(cap).enqueue(_ev())

    assert any("alert_window_shown" in r.getMessage() for r in caplog.records)


def test_a_window_that_fails_to_build_is_not_logged_as_shown(caplog):
    def broken(data, severity, on_acknowledge):
        raise FileNotFoundError("icons.json")

    ctrl = AlertController(create_window=broken, reference_name="Caracas")
    with caplog.at_level("INFO", logger="vigia_eew.notify.controller"):
        with contextlib.suppress(FileNotFoundError):
            ctrl.enqueue(_ev())

    messages = [r.getMessage() for r in caplog.records]
    assert any("alert_presented" in m for m in messages)
    assert not any("alert_window_shown" in m for m in messages)


# --- T-178 · the estimate never conditions the alert (REQ-ALE-013) -----------------

from datetime import timedelta  # noqa: E402


def test_the_alert_carries_the_arrival_of_the_shaking():
    cap = _Cap()
    ctrl = AlertController(
        create_window=cap.create_window, now=lambda: datetime(2026, 6, 28, 14, 0, tzinfo=UTC)
    )

    ctrl.enqueue(_ev())

    arrival = cap.windows[0].data.shaking_arrival
    assert arrival is not None
    assert timedelta(0) < arrival - _ev().time_utc < timedelta(seconds=10)


def test_an_origin_time_ahead_of_the_clock_still_alerts_and_the_log_says_why(caplog):
    """CA-119.7: window, sound and toast as ever; only the line is missing."""
    cap = _Cap()
    ctrl = AlertController(
        create_window=cap.create_window,
        play_sound=cap.sounds.append,
        send_toast=cap.toasts.append,
        now=lambda: _ev().time_utc - timedelta(minutes=10),
    )

    with caplog.at_level("INFO", logger="vigia_eew.notify.controller"):
        ctrl.enqueue(_ev())

    assert len(cap.windows) == 1
    assert cap.windows[0].data.shaking_arrival is None
    assert cap.windows[0].data.magnitude == "M 6.1"
    assert cap.sounds == ["critical"] and len(cap.toasts) == 1
    said = [r.getMessage() for r in caplog.records]
    assert any("shaking_estimate_unavailable" in m and "ahead of the clock" in m for m in said)


def test_a_revision_of_the_event_recomputes_the_arrival():
    """CA-119.8."""
    cap = _Cap()
    ctrl = AlertController(
        create_window=cap.create_window, now=lambda: datetime(2026, 6, 28, 14, 0, tzinfo=UTC)
    )
    ctrl.enqueue(_ev())
    first = cap.windows[0].data.shaking_arrival

    revised = _ev(action="update").model_copy(update={"distance_km": 365.0})
    ctrl.enqueue(revised)

    # 15 km became 365 km: a hundred seconds more for the wave, give or take the depth.
    later = cap.windows[0].refreshed.shaking_arrival - first
    assert timedelta(seconds=98) < later < timedelta(seconds=101)


# --- T-180, T-181 · drills (REQ-UX-007..009, ADR-040) ------------------------------


def _drill() -> SeismicEvent:
    return _ev("SIM-0001").model_copy(update={"source": "SIMULATED"})


class _Closable(_FakeWindow):
    closed = False

    def close(self):
        self.closed = True


class _DrillCap(_Cap):
    def __init__(self):
        super().__init__()
        self.record: list[str] = []

    def create_window(self, data, severity, on_acknowledge):
        w = _Closable(data, severity, on_acknowledge)
        self.windows.append(w)
        return w


def _drill_controller(cap: _DrillCap) -> AlertController:
    return AlertController(
        create_window=cap.create_window,
        play_sound=cap.sounds.append,
        on_drill_presented=lambda: cap.record.append("presented"),
        on_drill_acknowledged=lambda: cap.record.append("acknowledged"),
    )


def test_a_drill_is_a_whole_alert_labelled_as_one():
    """It tests the alert, so it is the alert: window and sound included."""
    cap = _DrillCap()
    ctrl = _drill_controller(cap)

    assert ctrl.offer_drill(_drill()) is True
    assert cap.windows[0].data.drill is True
    assert cap.sounds == ["critical"]


def test_a_drill_presented_and_acknowledged_is_recorded_as_both():
    """CA-120.3."""
    cap = _DrillCap()
    ctrl = _drill_controller(cap)
    ctrl.offer_drill(_drill())
    assert cap.record == ["presented"]

    cap.windows[0].on_acknowledge()

    assert cap.record == ["presented", "acknowledged"]


def test_the_manual_simulation_is_recorded_like_a_drill():
    cap = _DrillCap()
    ctrl = _drill_controller(cap)

    ctrl.enqueue(_drill())  # what `--simulate` does
    cap.windows[0].on_acknowledge()

    assert cap.record == ["presented", "acknowledged"]


def test_a_real_alert_is_not_recorded_as_a_drill():
    cap = _DrillCap()
    ctrl = _drill_controller(cap)

    ctrl.enqueue(_ev())
    cap.windows[0].on_acknowledge()

    assert cap.record == []


def test_a_real_alert_closes_the_drill_window_and_takes_the_screen():
    """CA-120.8, CA-120.4: closed, and never recorded as acknowledged."""
    cap = _DrillCap()
    ctrl = _drill_controller(cap)
    ctrl.offer_drill(_drill())

    ctrl.enqueue(_ev("real"))

    assert cap.windows[0].closed is True
    assert len(cap.windows) == 2 and cap.windows[1].data.drill is False
    assert cap.record == ["presented"]
    cap.windows[1].on_acknowledge()
    assert cap.record == ["presented"]


def test_a_drill_that_cannot_be_recorded_is_still_shown(caplog):
    """The record is a consequence of the alert, never a condition of it."""

    def broken():
        raise OSError("disk full")

    cap = _DrillCap()
    ctrl = AlertController(create_window=cap.create_window, on_drill_presented=broken)

    with caplog.at_level("WARNING", logger="vigia_eew.notify.controller"):
        assert ctrl.offer_drill(_drill()) is True

    assert len(cap.windows) == 1
    assert any("drill_record_failed" in r.getMessage() for r in caplog.records)


def test_a_drill_is_refused_while_paused_or_busy():
    cap = _DrillCap()
    ctrl = _drill_controller(cap)
    ctrl.pause()
    assert ctrl.offer_drill(_drill()) is False
    ctrl.resume()
    ctrl.enqueue(_ev("real"))

    assert ctrl.offer_drill(_drill()) is False
    assert len(cap.windows) == 1
