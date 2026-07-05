"""Tests for the undismissable alert window (RF-15, RF-16, RF-19)."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from vigia_eew.models import SeismicEvent
from vigia_eew.notify.alert_window import (
    AlertWindow,
    configure_undismissable,
    take_focus,
)
from vigia_eew.notify.presentation import AlertData, format_event


def _data() -> AlertData:
    ev = SeismicEvent(
        id="x",
        source="EMSC",
        magnitude=6.1,
        mag_type="mw",
        place="NEAR COAST OF VENEZUELA",
        lat=10.6,
        lon=-66.93,
        depth_km=12.0,
        time_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distance_km=162.0,
        severity="critical",
    )
    return format_event(ev, reference_name="Caracas")


class _FakeRoot:
    """Fake Tk root that records the configuration applied to it."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.binds: dict = {}
        self.protocols: dict = {}
        self.destroyed = False

    def overrideredirect(self, v):
        self.calls.append(("overrideredirect", v))

    def attributes(self, *a):
        self.calls.append(("attributes", *a))

    def protocol(self, name, fn):
        self.protocols[name] = fn

    def bind(self, seq, fn):
        self.binds[seq] = fn

    def lift(self):
        self.calls.append(("lift",))

    def focus_force(self):
        self.calls.append(("focus_force",))

    def destroy(self):
        self.destroyed = True


# --- Undismissable policy (RF-15, RF-16, RF-19) ---


def test_policy_topmost_and_undecorated():
    r = _FakeRoot()
    configure_undismissable(r, on_close_attempt=lambda: None)
    assert ("overrideredirect", True) in r.calls
    assert ("attributes", "-topmost", True) in r.calls


def test_policy_x_does_not_close():
    r = _FakeRoot()

    def close():
        return None

    configure_undismissable(r, on_close_attempt=close)
    assert r.protocols["WM_DELETE_WINDOW"] is close


def test_policy_escape_does_not_close():
    r = _FakeRoot()
    configure_undismissable(r, on_close_attempt=lambda: None)
    assert "<Escape>" in r.binds
    assert r.binds["<Escape>"](None) == "break"  # interrupts the event, doesn't close


def test_policy_focusout_re_raises():
    r = _FakeRoot()
    configure_undismissable(r, on_close_attempt=lambda: None)
    assert "<FocusOut>" in r.binds
    r.binds["<FocusOut>"](None)
    assert ("lift",) in r.calls and ("focus_force",) in r.calls


def test_take_focus_raises_and_forces_focus():
    r = _FakeRoot()
    take_focus(r)
    assert ("lift",) in r.calls and ("focus_force",) in r.calls


# --- Acknowledgement (RF-19, CU-5) ---


def test_acknowledge_calls_callback_and_destroys():
    ack: list[int] = []
    w = AlertWindow(_data(), on_acknowledge=lambda: ack.append(1), root=_FakeRoot(), build=False)
    w.acknowledge()
    assert ack == [1]
    assert w.root.destroyed is True


def test_acknowledge_is_idempotent():
    ack: list[int] = []
    w = AlertWindow(_data(), on_acknowledge=lambda: ack.append(1), root=_FakeRoot(), build=False)
    w.acknowledge()
    w.acknowledge()
    assert ack == [1]  # only acknowledged once even if invoked twice


def test_close_attempt_does_not_destroy():
    w = AlertWindow(_data(), on_acknowledge=lambda: None, root=_FakeRoot(), build=False)
    w._close_attempt()  # X / WM_DELETE_WINDOW
    assert w.root.destroyed is False


# --- Smoke test with real Tkinter (opt-in: VIGIA_GUI_TESTS=1) ---


@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_builds_real_window():
    import tkinter as tk

    root = tk.Tk()
    ack: list[int] = []
    w = AlertWindow(_data(), on_acknowledge=lambda: ack.append(1), root=root)
    root.update()
    # The widget tree was built (labels + ACKNOWLEDGED button).
    # `-topmost` is not queried here: with overrideredirect the window is left
    # unmanaged by the WM and the attribute isn't reliably queryable.
    assert len(root.winfo_children()) > 0
    w.acknowledge()
    assert ack == [1]


@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_detail_has_wraplength():
    # Without wraplength, a long line (e.g. "Local time (Venezuela): ...") gets
    # clipped against the window edge instead of wrapping (fixed, non-resizable
    # window). See alert_window.py::_build.
    import tkinter as tk

    root = tk.Tk()
    AlertWindow(_data(), on_acknowledge=lambda: None, root=root)
    root.update()
    labels = [w for w in root.winfo_children() if isinstance(w, tk.Label)]
    detail = next(w for w in labels if "Local time" in w.cget("text"))
    assert int(detail.cget("wraplength")) > 0


@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_window_height_fits_the_content():
    # The window is neither resizable nor scrollable (overrideredirect, RF-15): the
    # fixed height must always be >= what the packed content actually requests,
    # measured on the real screen (real fonts/DPI), not a guessed fixed number.
    import tkinter as tk

    root = tk.Tk()
    w = AlertWindow(_data(), on_acknowledge=lambda: None, root=root)
    root.update_idletasks()
    window_height = int(root.geometry().split("+")[0].split("x")[1])
    assert window_height >= root.winfo_reqheight()
    w.acknowledge()
