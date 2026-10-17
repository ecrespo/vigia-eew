"""The one Flet window every view of the agent is drawn in (ADR-006, ADR-030).

Flet drives a single native window per process, so the alert, the
configuration panel, the history and the About screen are not four windows
but four *contents* of this one. What the window shows is decided by a fixed
precedence, re-applied on every change:

  1. **an alert**, whenever there is one. It takes the window over -- always
     on top, no title bar, the X intercepted -- because nothing the user was
     doing in the panel outranks an earthquake (RF-15, RF-19);
  2. otherwise **the screen** the user opened (panel, history, About), in an
     ordinary resizable window;
  3. otherwise **nothing**: the agent hides the window and lives in the tray.
     A standalone run (`--simulate`, `--settings`) has nothing to go back to,
     so it ends instead.

Acknowledging an alert therefore puts back whatever was open before it, with
the user's unsaved edits intact -- the screen's controls were never destroyed,
only taken off the page.

Thread rule, unchanged from the Tk era: controls are touched only on the
thread running Flet's event loop (the main thread). `after()` is the one door
in from other threads -- the asyncio worker and the tray -- and it is
thread-safe.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from vigia_eew.notify import ui_scale

#: Keys that acknowledge an alert, as Flet names them (CA-106.7).
ENTER_KEYS = frozenset({"Enter", "Numpad Enter"})


@dataclass(slots=True)
class _Alert:
    view: Any
    configure: Callable[[Any], None]
    on_enter: Callable[[], None]
    bgcolor: str


@dataclass(slots=True)
class _Screen:
    key: str
    title: str
    view: Any


class FletShell:
    """Owns the page and decides, on every change, what the window shows."""

    def __init__(
        self,
        page: Any,
        *,
        standalone: bool = False,
        loop: asyncio.AbstractEventLoop | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.page = page
        self.standalone = standalone
        self._loop = loop
        self._log = logger or logging.getLogger("vigia_eew.notify.shell")
        self._alert: _Alert | None = None
        self._screen: _Screen | None = None
        self._closed = False
        page.title = "Vigía-eew"
        page.padding = 0
        page.window.prevent_close = True  # every close goes through `_on_window_event`
        page.window.on_event = self._on_window_event
        page.on_keyboard_event = self._on_key

    # --- Crossing in from other threads ---

    def after(self, ms: int, action: Callable[[], Any]) -> None:
        """Runs `action` on the UI loop after `ms` milliseconds. Thread-safe.

        The same contract `tk.Widget.after` had, which is what lets the
        asyncio bridge and the tray callbacks keep working unchanged.
        """
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        delay = max(0, ms) / 1000

        def schedule() -> None:
            loop.call_later(delay, self._run, action)

        loop.call_soon_threadsafe(schedule)

    def _run(self, action: Callable[[], Any]) -> None:
        if self._closed:
            return
        try:
            action()
        except Exception as exc:  # noqa: BLE001 - a callback must not take the UI loop down
            self._log.warning("ui_callback_failed type=%s detail=%s", type(exc).__name__, exc)
        self.update()

    def update(self) -> None:
        """Pushes pending control changes to the window, best-effort."""
        if self._closed:
            return
        try:
            self.page.update()
        except Exception as exc:  # noqa: BLE001 - a window mid-teardown is not an error
            self._log.debug("ui_update_skipped detail=%s", exc)

    # --- What is shown ---

    @property
    def alert_view(self) -> Any:
        return None if self._alert is None else self._alert.view

    @property
    def screen_key(self) -> str | None:
        return None if self._screen is None else self._screen.key

    def show_alert(
        self,
        view: Any,
        *,
        configure: Callable[[Any], None],
        on_enter: Callable[[], None],
        bgcolor: str,
    ) -> None:
        """Takes the window over for an alert (RF-15)."""
        self._alert = _Alert(view, configure, on_enter, bgcolor)
        self._render()

    def clear_alert(self, view: Any) -> None:
        """Gives the window back once *that* alert was acknowledged."""
        if self._alert is not None and self._alert.view is view:
            self._alert = None
            self._render()

    def show_screen(self, key: str, title: str, view: Any) -> None:
        """Opens a screen, replacing the one that was open, if any."""
        self._screen = _Screen(key, title, view)
        self._render()

    def close_screen(self) -> None:
        self._screen = None
        self._render()

    def quit(self) -> None:
        """Destroys the window, which ends `flet.run` and with it the run mode."""
        if self._closed:
            return
        self._closed = True
        self.page.window.prevent_close = False
        self._call_async(self._destroy)

    def quit_on_terminate(self) -> bool:
        """Makes SIGTERM end the run the way closing the window does.

        Flet's loop owns the main thread and installs no handler, so SIGTERM --
        what `systemctl --user stop`, a logout or a plain `kill` send -- was
        ignored until something escalated to SIGKILL, and shutdown never ran.
        Returns False where the loop cannot take signal handlers (Windows,
        which ends a GUI process another way).
        """
        loop = self._loop
        if loop is None:
            return False

        def terminate() -> None:
            self._log.info("terminate_requested signal=SIGTERM")
            self.quit()

        try:
            loop.add_signal_handler(signal.SIGTERM, terminate)
        except (NotImplementedError, RuntimeError, ValueError):
            return False
        return True

    async def _destroy(self) -> None:
        # Destroying the window ends the session the call travels on, so the
        # call itself can fail on the way back. That is the outcome asked for.
        try:
            await self.page.window.destroy()
        except Exception as exc:  # noqa: BLE001
            self._log.debug("ui_destroy_finished detail=%s", exc)

    # --- Rendering ---

    def _render(self) -> None:
        window = self.page.window
        if self._alert is not None:
            self.page.bgcolor = self._alert.bgcolor
            self.page.controls = [self._alert.view]
            self._alert.configure(window)
            window.visible = True
            self.update()
            self._call_async(window.to_front)
            return
        if self._screen is not None:
            self._restore_ordinary_window(window)
            self.page.title = self._screen.title
            self.page.bgcolor = None
            self.page.controls = [self._screen.view]
            window.visible = True
            self.update()
            self._call_async(window.center)
            return
        if self.standalone:
            self.quit()
            return
        self.page.controls = []
        window.visible = False
        self.update()

    @staticmethod
    def _restore_ordinary_window(window: Any) -> None:
        """Undoes what an alert did to the window, if one had it."""
        window.always_on_top = False
        window.title_bar_hidden = False
        window.full_screen = False
        window.resizable = True
        window.minimizable = True
        window.width, window.height = ui_scale.PREFERRED_SIZE
        window.min_width, window.min_height = ui_scale.MINIMUM_SIZE

    def _call_async(self, method: Callable[[], Any]) -> None:
        try:
            self.page.run_task(method)
        except Exception as exc:  # noqa: BLE001 - no session yet or already gone
            self._log.debug("ui_window_call_skipped detail=%s", exc)

    # --- Events ---

    def _on_window_event(self, event: Any) -> None:
        kind = str(getattr(getattr(event, "type", None), "value", getattr(event, "type", "")))
        if kind == "close":
            self._close_requested()
        elif kind == "blur" and self._alert is not None:
            # Losing focus brings the alert back (RF-16).
            self._call_async(self.page.window.to_front)

    def _close_requested(self) -> None:
        if self._alert is not None:
            self._log.info("alert_close_ignored")  # only ACKNOWLEDGED closes it (RF-19)
            return
        if self._screen is not None:
            self.close_screen()
            return
        if self.standalone:
            self.quit()

    def _on_key(self, event: Any) -> None:
        if self._alert is not None and getattr(event, "key", None) in ENTER_KEYS:
            self._alert.on_enter()
