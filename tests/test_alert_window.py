"""Tests for the undismissable alert and its map (RF-15, RF-16, RF-19, ADR-030).

The window policy is checked on a fake window; the content is checked on the
real Flet controls, which are plain dataclasses and need no display. How the
X, Escape, ENTER and focus loss behave is the shell's job (`test_flet_shell`).
"""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.models import SeismicEvent
from vigia_eew.notify.alert_window import (
    MAP_HEIGHT,
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
    return format_event(ev, reference_name="Caracas", reference=(10.48, -66.90))


class _FakeWindow:
    """Fake Flet window: plain attributes, like the real one."""

    def __init__(self) -> None:
        self.always_on_top = False
        self.title_bar_hidden = False
        self.title_bar_buttons_hidden = False
        self.prevent_close = False
        self.minimizable = True
        self.resizable = True
        self.full_screen = False
        self.skip_task_bar = True
        self.width = self.height = None
        self.visible = False
        self.focused = False

    async def to_front(self) -> None:  # pragma: no cover - only scheduled
        return None


# --- Undismissable policy (RF-15, RF-16, RF-19) ---


def test_policy_topmost_and_undecorated():
    w = _FakeWindow()
    configure_undismissable(w)
    assert w.always_on_top is True
    assert w.title_bar_hidden is True
    assert w.title_bar_buttons_hidden is True


def test_policy_x_does_not_close():
    w = _FakeWindow()
    configure_undismissable(w)
    assert w.prevent_close is True  # the close request reaches the shell, which ignores it


def test_policy_cannot_be_minimised_away():
    w = _FakeWindow()
    configure_undismissable(w)
    assert w.minimizable is False
    assert w.skip_task_bar is False


def test_policy_sizes_a_window_or_fills_the_screen():
    from vigia_eew.notify import ui_scale

    windowed, full = _FakeWindow(), _FakeWindow()
    configure_undismissable(windowed)
    configure_undismissable(full, fullscreen=True)

    assert (windowed.width, windowed.height) == ui_scale.ALERT_SIZE
    assert windowed.full_screen is False
    assert full.full_screen is True


def test_take_focus_raises_and_brings_to_front():
    w = _FakeWindow()
    scheduled: list[object] = []
    take_focus(w, scheduled.append)
    assert w.visible is True and w.focused is True
    assert scheduled == [w.to_front]


# --- Acknowledgement (RF-19, CU-5) ---


def test_acknowledge_calls_callback_and_gives_the_window_back(fake_shell):
    ack: list[int] = []
    w = AlertWindow(_data(), on_acknowledge=lambda: ack.append(1), host=fake_shell)
    assert fake_shell.alerts == [w.view]

    w.acknowledge()

    assert ack == [1]
    assert fake_shell.alerts == []


def test_acknowledge_is_idempotent(fake_shell):
    ack: list[int] = []
    w = AlertWindow(_data(), on_acknowledge=lambda: ack.append(1), host=fake_shell)
    w.acknowledge()
    w.acknowledge()
    assert ack == [1]  # only acknowledged once even if invoked twice


def test_enter_is_routed_to_the_acknowledgement(fake_shell):
    """CA-106.7: ENTER acknowledges, as in the TUI (the shell calls `on_enter`)."""
    ack: list[int] = []
    AlertWindow(_data(), on_acknowledge=lambda: ack.append(1), host=fake_shell)
    fake_shell.on_enter()
    assert ack == [1]


def test_refresh_replaces_the_content_in_place(fake_shell):
    """RF-11: an update rewrites the alert on screen instead of opening another."""
    w = AlertWindow(_data(), on_acknowledge=lambda: None, host=fake_shell)
    view = w.view
    newer = format_event(
        SeismicEvent(
            id="x",
            source="EMSC",
            magnitude=6.4,
            mag_type="mw",
            place="NEAR COAST OF VENEZUELA",
            lat=10.6,
            lon=-66.93,
            depth_km=12.0,
            time_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
            distance_km=162.0,
            severity="critical",
        )
    )

    w.refresh(newer)

    assert w.view is view
    assert fake_shell.alerts == [view]
    assert "M 6.4" in _texts(w.view)


# --- What the alert shows ---


def _texts(control) -> str:
    """Every string in a control tree, for asserting on what reaches the screen."""
    found: list[str] = []

    def walk(node) -> None:
        if node is None:
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
            return
        for attr in ("value", "text"):
            value = getattr(node, attr, None)
            if isinstance(value, str):
                found.append(value)
        for attr in ("content", "controls", "spans", "layers", "markers"):
            walk(getattr(node, attr, None))

    walk(control)
    return "\n".join(found)


def _map_of(window):
    import flet_map as fm

    found = []

    def walk(node) -> None:
        if isinstance(node, fm.Map):
            found.append(node)
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
            return
        for attr in ("content", "controls"):
            child = getattr(node, attr, None)
            if child is not None:
                walk(child)

    walk(window.view)
    assert found, "the alert has no map"
    return found[0]


def test_the_alert_shows_place_magnitude_and_coordinates():
    w = AlertWindow(_data(), on_acknowledge=lambda: None)
    text = _texts(w.view)

    assert "M 6.1" in text
    assert "NEAR COAST OF VENEZUELA" in text
    assert "10.60° N, 66.93° W" in text
    assert "ACKNOWLEDGED" in text


def test_the_map_pins_the_epicentre_with_its_caption():
    """The point on the map carries the zone, the coordinates and the magnitude."""
    import flet_map as fm

    the_map = _map_of(AlertWindow(_data(), on_acknowledge=lambda: None))
    markers = next(layer for layer in the_map.layers if isinstance(layer, fm.MarkerLayer))
    epicentre = markers.markers[0]

    assert (epicentre.coordinates.latitude, epicentre.coordinates.longitude) == (10.6, -66.93)
    caption = _texts(epicentre)
    assert "M 6.1" in caption
    assert "NEAR COAST OF VENEZUELA" in caption
    assert "10.60° N, 66.93° W" in caption


def test_the_map_marks_the_reference_point_too():
    import flet_map as fm

    the_map = _map_of(AlertWindow(_data(), on_acknowledge=lambda: None))
    markers = next(layer for layer in the_map.layers if isinstance(layer, fm.MarkerLayer))

    assert len(markers.markers) == 2
    assert "Caracas" in _texts(markers.markers[1])


def test_the_map_sizes_a_circle_by_magnitude_and_credits_its_tiles():
    import flet_map as fm

    the_map = _map_of(AlertWindow(_data(), on_acknowledge=lambda: None))
    kinds = {type(layer) for layer in the_map.layers}

    assert {fm.TileLayer, fm.CircleLayer, fm.MarkerLayer, fm.SimpleAttribution} <= kinds


def test_the_text_and_the_map_stack_on_a_narrow_window():
    """Responsive: side by side from `md`, one above the other below it."""
    from vigia_eew.notify import ui_scale

    assert ui_scale.ALERT_TEXT_COLUMNS["xs"] == ui_scale.ALERT_MAP_COLUMNS["xs"] == 12
    assert MAP_HEIGHT > 0


def test_an_alert_without_a_reference_still_draws_the_epicentre():
    import flet_map as fm

    data = format_event(
        SeismicEvent(
            id="y",
            source="USGS",
            magnitude=4.0,
            mag_type="ml",
            place=None,
            region="SOMEWHERE",
            lat=-33.0,
            lon=-70.0,
            depth_km=30.0,
            time_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
            distance_km=4000.0,
            severity="info",
        )
    )
    the_map = _map_of(AlertWindow(data, on_acknowledge=lambda: None))
    markers = next(layer for layer in the_map.layers if isinstance(layer, fm.MarkerLayer))

    assert len(markers.markers) == 1
