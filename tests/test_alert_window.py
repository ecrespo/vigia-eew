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


# --- T-178 · the alert says when the shaking arrives, or when it did ---------------

from dataclasses import replace  # noqa: E402
from datetime import timedelta  # noqa: E402

_ARRIVES = datetime(2026, 6, 28, 13, 40, tzinfo=UTC)


class _Clock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, seconds: float) -> None:
        self.moment += timedelta(seconds=seconds)


def _all_text(control) -> list[str]:
    found: list[str] = []
    value = getattr(control, "value", None)
    if isinstance(value, str) and value and getattr(control, "visible", True):
        found.append(value)
    for span in getattr(control, "spans", None) or []:
        if getattr(span, "text", None):
            found.append(span.text)
    for child in getattr(control, "controls", None) or []:
        found.extend(_all_text(child))
    content = getattr(control, "content", None)
    if content is not None and not isinstance(content, str):
        found.extend(_all_text(content))
    return found


def _shaking(**changes) -> AlertData:
    return replace(_data(), shaking_arrival=_ARRIVES, **changes)


def test_the_alert_shows_the_line_about_the_shaking():
    clock = _Clock(_ARRIVES + timedelta(minutes=20))

    window = AlertWindow(_shaking(), on_acknowledge=lambda: None, now=clock)

    assert "The shaking should already have arrived ≈ 20 min ago" in _all_text(window.view)


def test_the_count_decreases_while_the_alert_is_on_screen(fake_shell):
    """CA-119.1: recounted once a second, on the shell's timer."""
    clock = _Clock(_ARRIVES - timedelta(seconds=30))
    window = AlertWindow(_shaking(), on_acknowledge=lambda: None, host=fake_shell, now=clock)
    assert window.shaking.value == "Shaking expected in ≈ 30 s"
    assert [ms for ms, _ in fake_shell.after_calls] == [1000]

    clock.advance(1)
    fake_shell.run_pending()

    assert window.shaking.value == "Shaking expected in ≈ 29 s"
    assert [ms for ms, _ in fake_shell.after_calls] == [1000]  # and it asks for the next
    assert fake_shell.updates >= 1


def test_a_count_that_runs_out_becomes_the_elapsed_sentence_on_screen(fake_shell):
    """CA-119.3."""
    clock = _Clock(_ARRIVES - timedelta(seconds=1))
    window = AlertWindow(_shaking(), on_acknowledge=lambda: None, host=fake_shell, now=clock)
    assert window.shaking.value == "Shaking expected in ≈ 1 s"

    for _ in range(3):
        clock.advance(1)
        fake_shell.run_pending()
        assert "-" not in window.shaking.value

    assert window.shaking.value == "The shaking should already have arrived ≈ 2 s ago"


def test_once_acknowledged_the_alert_stops_counting(fake_shell):
    clock = _Clock(_ARRIVES)
    window = AlertWindow(_shaking(), on_acknowledge=lambda: None, host=fake_shell, now=clock)

    window.acknowledge()
    fake_shell.run_pending()

    assert fake_shell.after_calls == []


def test_without_an_estimate_the_alert_is_whole_and_has_no_line(fake_shell):
    """CA-119.7: every other guarantee unchanged."""
    acknowledged = []
    without = replace(_data(), shaking_arrival=None)
    window = AlertWindow(without, on_acknowledge=lambda: acknowledged.append(1), host=fake_shell)

    said = _all_text(window.view)
    assert window.shaking.visible is False
    assert not any("haking" in text for text in said)
    assert "M 6.1" in said and "NEAR COAST OF VENEZUELA" in said
    assert len(fake_shell.alerts) == 1
    fake_shell.on_enter()
    assert acknowledged == [1] and fake_shell.alerts == []


def test_a_revision_recomputes_the_line(fake_shell):
    """CA-119.8: a revised origin time or location moves the arrival."""
    clock = _Clock(_ARRIVES + timedelta(minutes=5))
    window = AlertWindow(_shaking(), on_acknowledge=lambda: None, host=fake_shell, now=clock)
    assert "≈ 5 min ago" in window.shaking.value

    window.refresh(replace(_shaking(), shaking_arrival=_ARRIVES + timedelta(minutes=3)))

    assert "≈ 2 min ago" in window.shaking.value
    assert sum(1 for ms, _ in fake_shell.after_calls if ms == 1000) == 1  # still one timer


def test_a_revision_that_brings_an_estimate_starts_showing_it(fake_shell):
    clock = _Clock(_ARRIVES + timedelta(seconds=10))
    without = replace(_data(), shaking_arrival=None)
    window = AlertWindow(without, on_acknowledge=lambda: None, host=fake_shell, now=clock)
    assert window.shaking.visible is False

    window.refresh(_shaking())
    clock.advance(1)
    fake_shell.run_pending()

    assert window.shaking.visible is True
    assert window.shaking.value == "The shaking should already have arrived ≈ 11 s ago"


# --- T-179 · a drill says it is a drill (REQ-UX-008) -------------------------------


def test_a_drill_is_labelled_above_everything_else():
    window = AlertWindow(replace(_data(), drill=True), on_acknowledge=lambda: None)

    said = _all_text(window.view)
    assert said[0] == "DRILL — this is not a real earthquake"


def test_a_drill_is_labelled_in_spanish_too():
    window = AlertWindow(replace(_data(), drill=True), on_acknowledge=lambda: None, locale="es")

    assert "SIMULACRO — no es un sismo real" in _all_text(window.view)


def test_a_real_alert_carries_no_drill_label():
    window = AlertWindow(_data(), on_acknowledge=lambda: None)

    assert not any("DRILL" in text for text in _all_text(window.view))


def test_an_alert_can_be_closed_without_being_acknowledged(fake_shell):
    """What a real alert does to a drill on screen (REQ-UX-009)."""
    acknowledged = []
    window = AlertWindow(_data(), on_acknowledge=lambda: acknowledged.append(1), host=fake_shell)

    window.close()
    fake_shell.run_pending()

    assert acknowledged == []
    assert fake_shell.alerts == []
    assert fake_shell.after_calls == []  # and it stopped counting


# --- The time says which zone it is in ---------------------------------------------


def test_the_alert_names_the_zone_of_its_time():
    ev_data = replace(
        _data(),
        local_time="2026-06-28 15:39:00",
        zone_abbreviation="CEST",
        zone_name="Europe/Madrid",
    )

    window = AlertWindow(ev_data, on_acknowledge=lambda: None)

    assert "2026-06-28 15:39:00 CEST (Europe/Madrid)" in _all_text(window.view)
