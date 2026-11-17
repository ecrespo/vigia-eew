"""Tests for the navigation between screens (REQ-GUI-012, ADR-031, HU-113).

Every screen leads to the others, so that none of them depends on the tray
menu -- which on GNOME/Wayland may not open. The bar is part of each screen's
view, never of the shell: that is what keeps it off the window while an alert
is on it (see `test_flet_shell.py`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vigia_eew.agent_state import AgentState
from vigia_eew.config import Settings, bundled_example
from vigia_eew.notify import navigation
from vigia_eew.state import StateStore
from vigia_eew.wiring import Wiring


def _buttons(view) -> dict[str, object]:
    """The navigation's buttons in a screen's view, by the screen they lead to."""
    bar = navigation.bar_of(view)
    assert bar is not None, "this screen has no navigation"
    return {button.data: button for button in bar.content.controls}


@pytest.fixture
def wiring(tmp_path: Path) -> Wiring:
    made = Wiring(Settings(), StateStore(tmp_path / "state.json"), AgentState())
    path = tmp_path / "config.toml"
    path.write_text(bundled_example(), encoding="utf-8")
    made.config_file = path
    yield made
    made.close_history()


# --- The bar itself ---


def test_the_bar_offers_the_three_screens_in_one_order() -> None:
    entries = navigation.entries("history", locale_code="en")

    assert [entry.key for entry in entries] == ["history", "panel", "about"]
    assert [entry.label for entry in entries] == ["History", "Settings", "About"]


def test_the_bar_marks_the_screen_it_is_on() -> None:
    entries = navigation.entries("panel", locale_code="en")

    assert [entry.current for entry in entries] == [False, True, False]


def test_the_bar_is_translated() -> None:
    labels = [entry.label for entry in navigation.entries("history", locale_code="es")]

    assert labels == ["Histórico", "Configuración", "Acerca de"]


def test_choosing_a_destination_reports_its_key() -> None:
    chosen: list[str] = []
    view = navigation.framed(object(), "history", chosen.append, locale_code="en")

    _buttons(view)["panel"].on_click(None)

    assert chosen == ["panel"]


def test_the_screen_it_is_on_is_marked_by_more_than_colour() -> None:
    """The current destination cannot be pressed: it differs in state, not in hue."""
    view = navigation.framed(object(), "history", lambda _key: None, locale_code="en")
    buttons = _buttons(view)

    assert buttons["history"].disabled is True
    assert buttons["panel"].disabled is False
    assert buttons["about"].disabled is False


def test_framing_keeps_the_screen_itself_as_the_last_control() -> None:
    screen = object()

    view = navigation.framed(screen, "about", lambda _key: None, locale_code="en")

    assert navigation.screen_of(view) is screen


# --- Wired: every screen leads to the others (CA-113.4) ---


def test_every_screen_carries_the_navigation(wiring: Wiring, fake_shell) -> None:
    wiring.open_history(fake_shell)
    wiring.open_panel(fake_shell, wiring.config_file)
    wiring.open_about(fake_shell)

    assert [key for key, _title, _view in fake_shell.screens] == ["history", "panel", "about"]
    for _key, _title, view in fake_shell.screens:
        assert set(_buttons(view)) == {"history", "panel", "about"}


def test_from_the_panel_the_history_is_reached_and_returned_from(wiring, fake_shell) -> None:
    """CA-113.4: opened with `--settings`, no tray and no terminal needed."""
    panel = wiring.open_panel(fake_shell, wiring.config_file)

    _buttons(fake_shell.screens[-1][2])["history"].on_click(None)
    assert fake_shell.screen_key == "history"

    _buttons(fake_shell.screens[-1][2])["panel"].on_click(None)
    assert fake_shell.screen_key == "panel"
    assert navigation.screen_of(fake_shell.screens[-1][2]) is panel.view


def test_from_the_history_the_panel_opens_on_the_configured_file(wiring, fake_shell) -> None:
    """Opened with `--history`: the panel reached from there edits the same file."""
    wiring.open_history(fake_shell)

    _buttons(fake_shell.screens[-1][2])["panel"].on_click(None)

    assert fake_shell.screen_key == "panel"
    assert wiring._panel.model.value("filter.radius_km") == Settings().filter.radius_km


def test_about_is_reached_from_the_history(wiring, fake_shell) -> None:
    wiring.open_history(fake_shell)

    _buttons(fake_shell.screens[-1][2])["about"].on_click(None)

    assert fake_shell.screen_key == "about"


def test_a_history_that_cannot_be_opened_still_leads_to_the_others(
    wiring, fake_shell, monkeypatch
) -> None:
    """CA-113.3: the notice is a screen like the others, not a dead end."""
    import vigia_eew.wiring as wiring_module

    def refuse(self):
        raise OSError("read-only file system")

    monkeypatch.setattr(wiring_module.HistoryStore, "open", refuse)

    wiring.open_history(fake_shell)
    _buttons(fake_shell.screens[-1][2])["panel"].on_click(None)

    assert fake_shell.screen_key == "panel"


# --- Switching screens discards nothing (CA-113.5) ---


def test_an_unsaved_edit_survives_the_trip(wiring, fake_shell) -> None:
    panel = wiring.open_panel(fake_shell, wiring.config_file)
    panel.model.edit("filter.radius_km", 777.0)
    assert panel.model.changes() == {"filter.radius_km": 777.0}

    _buttons(fake_shell.screens[-1][2])["history"].on_click(None)
    _buttons(fake_shell.screens[-1][2])["panel"].on_click(None)

    assert wiring._panel is panel
    assert panel.model.value("filter.radius_km") == 777.0
    assert panel.model.changes() == {"filter.radius_km": 777.0}  # still marked unsaved


def test_a_filter_set_on_the_history_survives_the_trip(wiring, fake_shell) -> None:
    window = wiring.open_history(fake_shell)
    window.listing.set_filter(min_magnitude=5.0)

    _buttons(fake_shell.screens[-1][2])["panel"].on_click(None)
    _buttons(fake_shell.screens[-1][2])["history"].on_click(None)

    assert wiring._history_window is window
    assert window.listing.query.min_magnitude == 5.0


# --- T-155 · navigation never competes with an alert (REQ-GUI-013) ---------------


class _Window:
    def __init__(self) -> None:
        self.visible = False
        self.prevent_close = False
        self.on_event = None
        self.always_on_top = False

    async def to_front(self) -> None:
        return None

    async def center(self) -> None:
        return None

    async def destroy(self) -> None:
        return None


class _Page:
    def __init__(self) -> None:
        self.window = _Window()
        self.controls: list[object] = []
        self.title = ""
        self.padding = None
        self.bgcolor = None
        self.on_keyboard_event = None

    def update(self) -> None:
        pass

    def run_task(self, method) -> None:
        pass


def _alerted(shell) -> object:
    view = object()
    shell.show_alert(view, configure=lambda _w: None, on_enter=lambda: None, bgcolor="#C62828")
    return view


def test_with_an_alert_up_the_window_holds_the_alert_and_no_navigation(wiring) -> None:
    """CA-113.6: the bar is inside the screen, so the alert leaves it nowhere to be."""
    from vigia_eew.notify.flet_shell import FletShell

    page = _Page()
    shell = FletShell(page)
    wiring.open_history(shell)
    assert navigation.bar_of(page.controls[0]) is not None

    alert = _alerted(shell)

    assert page.controls == [alert]


def test_no_navigation_changes_what_the_window_shows_under_an_alert(wiring) -> None:
    """CA-113.6: by control, by the tray, by anything that asks the wiring to go."""
    from vigia_eew.notify.flet_shell import FletShell

    page = _Page()
    shell = FletShell(page)
    wiring.open_history(shell)
    covered = _buttons(page.controls[0])
    alert = _alerted(shell)

    covered["panel"].on_click(None)  # a handler of the covered screen, still callable
    wiring.navigate(shell, "about")
    wiring.open_history(shell)

    assert page.controls == [alert]
    assert page.window.visible is True


def test_after_the_alert_the_screen_is_back_as_it_was(wiring) -> None:
    """CA-113.7: the same window object, with the filter that was set."""
    from vigia_eew.notify.flet_shell import FletShell

    page = _Page()
    shell = FletShell(page)
    window = wiring.open_history(shell)
    window.listing.set_filter(min_magnitude=5.0)
    shown = page.controls[0]

    alert = _alerted(shell)
    shell.clear_alert(alert)

    assert page.controls == [shown]
    assert navigation.screen_of(page.controls[0]) is window.view
    assert window.listing.query.min_magnitude == 5.0
