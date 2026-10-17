"""Tests for the one window every view is drawn in (ADR-006, ADR-030).

The shell decides what the window shows -- alert, else screen, else nothing --
and enforces the alert's undismissable contract on close and key events. All
of that is checked on a fake page: no Flet client, no display.
"""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

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
