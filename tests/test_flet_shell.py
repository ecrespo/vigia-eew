"""Tests for the one window every view is drawn in (ADR-006, ADR-030).

The shell decides what the window shows -- alert, else screen, else nothing --
and enforces the alert's undismissable contract on close and key events. All
of that is checked on a fake page: no Flet client, no display.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import threading
from types import SimpleNamespace

import pytest

from vigia_eew.notify.flet_shell import FletShell


class _Window(SimpleNamespace):
    def __init__(self) -> None:
        super().__init__(
            visible=False,
            prevent_close=False,
            on_event=None,
            always_on_top=False,
            title_bar_hidden=False,
            full_screen=False,
            resizable=True,
            minimizable=True,
            width=None,
            height=None,
            min_width=None,
            min_height=None,
        )

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
        self.updates = 0
        self.tasks: list[object] = []

    def update(self) -> None:
        self.updates += 1

    def run_task(self, method) -> None:
        self.tasks.append(method)


def _event(kind: str) -> SimpleNamespace:
    return SimpleNamespace(type=SimpleNamespace(value=kind))


def _alert(shell: FletShell, view: object = "ALERT", on_enter=lambda: None) -> object:
    shell.show_alert(
        view,
        configure=lambda w: setattr(w, "always_on_top", True),
        on_enter=on_enter,
        bgcolor="#C62828",
    )
    return view


# --- What the window shows --------------------------------------------------------


def test_the_agent_starts_hidden_with_every_close_intercepted() -> None:
    page = _Page()
    FletShell(page)

    assert page.window.prevent_close is True
    assert page.window.visible is False


def test_an_alert_takes_the_window_over() -> None:
    page = _Page()
    shell = FletShell(page)

    _alert(shell)

    assert page.controls == ["ALERT"]
    assert page.window.visible is True
    assert page.window.always_on_top is True
    assert page.bgcolor == "#C62828"
    assert page.window.to_front in page.tasks


def test_an_alert_outranks_an_open_screen_and_gives_it_back() -> None:
    """Acknowledging puts back what was open, edits intact (same controls)."""
    page = _Page()
    shell = FletShell(page)
    shell.show_screen("panel", "Settings", "PANEL")

    view = _alert(shell)
    assert page.controls == ["ALERT"]

    shell.clear_alert(view)

    assert page.controls == ["PANEL"]
    assert page.window.always_on_top is False
    assert page.window.title_bar_hidden is False


def test_clearing_another_alert_changes_nothing() -> None:
    page = _Page()
    shell = FletShell(page)
    _alert(shell, "FIRST")

    shell.clear_alert("SOMETHING ELSE")

    assert page.controls == ["FIRST"]


def test_with_nothing_to_show_the_agent_hides_the_window() -> None:
    page = _Page()
    shell = FletShell(page)
    shell.show_screen("about", "About", "ABOUT")

    shell.close_screen()

    assert page.window.visible is False
    assert page.controls == []


def test_a_standalone_run_ends_when_nothing_is_left() -> None:
    """`--simulate` and `--settings` have nothing to go back to."""
    page = _Page()
    shell = FletShell(page, standalone=True)
    view = _alert(shell)

    shell.clear_alert(view)

    assert page.window.prevent_close is False
    assert len(page.tasks) >= 2  # to_front, then the destroy


# --- The undismissable contract (RF-16, RF-19, CA-106.7) --------------------------


def test_the_x_does_not_close_an_alert() -> None:
    page = _Page()
    shell = FletShell(page, standalone=True)
    _alert(shell)

    page.window.on_event(_event("close"))

    assert page.controls == ["ALERT"]
    assert page.window.prevent_close is True


def test_the_x_closes_an_ordinary_screen() -> None:
    page = _Page()
    shell = FletShell(page)
    shell.show_screen("history", "History", "HISTORY")

    page.window.on_event(_event("close"))

    assert shell.screen_key is None
    assert page.window.visible is False


def test_losing_focus_brings_the_alert_back() -> None:
    page = _Page()
    shell = FletShell(page)
    _alert(shell)
    page.tasks.clear()

    page.window.on_event(_event("blur"))

    assert page.tasks == [page.window.to_front]


def test_enter_acknowledges_and_escape_does_not() -> None:
    page = _Page()
    shell = FletShell(page)
    acknowledged: list[int] = []
    _alert(shell, on_enter=lambda: acknowledged.append(1))

    page.on_keyboard_event(SimpleNamespace(key="Escape"))
    assert acknowledged == []
    page.on_keyboard_event(SimpleNamespace(key="Enter"))
    page.on_keyboard_event(SimpleNamespace(key="Numpad Enter"))
    assert acknowledged == [1, 1]


def test_enter_does_nothing_without_an_alert() -> None:
    page = _Page()
    FletShell(page)
    page.on_keyboard_event(SimpleNamespace(key="Enter"))  # no error, no effect


# --- Crossing threads (ADR-006) ---------------------------------------------------


def test_after_runs_the_action_on_the_loop_from_another_thread() -> None:
    page = _Page()
    seen: list[str] = []

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        shell = FletShell(page, loop=loop)
        done = asyncio.Event()

        def action() -> None:
            seen.append(threading.current_thread().name)
            loop.call_soon(done.set)

        thread = threading.Thread(target=shell.after, args=(0, action), name="tray")
        thread.start()
        thread.join()
        await asyncio.wait_for(done.wait(), timeout=2)

    asyncio.run(scenario())

    assert seen == ["MainThread"]
    assert page.updates >= 1  # the change reached the window


def test_a_failing_callback_does_not_take_the_loop_down() -> None:
    page = _Page()

    async def scenario() -> None:
        shell = FletShell(page, loop=asyncio.get_running_loop())
        shell.after(0, lambda: 1 / 0)
        await asyncio.sleep(0.05)

    asyncio.run(scenario())  # no exception escapes


def test_after_is_a_no_op_once_the_window_is_gone() -> None:
    page = _Page()
    shell = FletShell(page)  # no loop: nothing to schedule on
    shell.after(0, lambda: (_ for _ in ()).throw(AssertionError("ran")))


# --- T-155 · a screen is told when an alert covers it (ADR-031, X-4) --------------


def _watched(shell: FletShell, view: object = "HISTORY") -> list[str]:
    seen: list[str] = []
    shell.show_screen(
        "history",
        "History",
        view,
        on_covered=lambda: seen.append("covered"),
        on_uncovered=lambda: seen.append("uncovered"),
    )
    return seen


def test_a_screen_is_told_when_an_alert_takes_the_window_and_when_it_returns() -> None:
    """What a playback pauses on: once each, in order (REQ-TLP-006)."""
    shell = FletShell(_Page())
    seen = _watched(shell)

    view = _alert(shell)
    assert seen == ["covered"]

    shell.clear_alert(view)
    assert seen == ["covered", "uncovered"]


def test_a_second_alert_does_not_cover_the_screen_twice() -> None:
    """The queue shows the next alert as the first is acknowledged."""
    shell = FletShell(_Page())
    seen = _watched(shell)

    first = _alert(shell, "FIRST")
    second = _alert(shell, "SECOND")
    shell.clear_alert(first)  # not the one on screen any more
    assert seen == ["covered"]

    shell.clear_alert(second)
    assert seen == ["covered", "uncovered"]


def test_a_screen_opened_under_an_alert_is_born_covered() -> None:
    page = _Page()
    shell = FletShell(page)
    view = _alert(shell)

    seen = _watched(shell)

    assert page.controls == ["ALERT"]
    assert seen == ["covered"]
    shell.clear_alert(view)
    assert seen == ["covered", "uncovered"]
    assert page.controls == ["HISTORY"]


def test_a_screen_closed_under_an_alert_is_not_told_it_is_back() -> None:
    shell = FletShell(_Page())
    seen = _watched(shell)
    view = _alert(shell)

    shell.close_screen()
    shell.clear_alert(view)

    assert seen == ["covered"]


def test_a_screen_that_does_not_ask_is_not_told() -> None:
    """The callbacks are optional: the panel and About have nothing to pause."""
    page = _Page()
    shell = FletShell(page)
    shell.show_screen("panel", "Settings", "PANEL")

    view = _alert(shell)
    shell.clear_alert(view)

    assert page.controls == ["PANEL"]


def test_a_callback_that_fails_does_not_cost_the_alert() -> None:
    """Art. 1: nothing a screen does on being covered may keep the alert off."""
    page = _Page()
    shell = FletShell(page)

    def explode() -> None:
        raise RuntimeError("the playback could not pause")

    shell.show_screen("history", "History", "HISTORY", on_covered=explode)

    _alert(shell)

    assert page.controls == ["ALERT"]
    assert page.window.always_on_top is True


# --- Termination ------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="no POSIX signal handlers on Windows")
def test_sigterm_ends_the_run_like_closing_the_window() -> None:
    """`systemctl stop`, a logout, `kill`: the agent quits instead of ignoring it."""
    page = _Page()

    async def scenario() -> None:
        shell = FletShell(page, loop=asyncio.get_running_loop())
        assert shell.quit_on_terminate() is True
        _alert(shell)  # even with an alert up: termination is not the user's X
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.sleep(0.05)

    asyncio.run(scenario())

    assert page.window.prevent_close is False
    assert any(getattr(t, "__name__", "") == "_destroy" for t in page.tasks)


def test_without_a_loop_there_is_nothing_to_install_a_handler_on() -> None:
    assert FletShell(_Page()).quit_on_terminate() is False
