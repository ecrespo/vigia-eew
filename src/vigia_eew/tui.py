"""Headless TUI dashboard (RF-36, ADR-013).

Alternative frontend to Tkinter+tray for running the agent on a headless
server over SSH, with no desktop session: a live status dashboard (WS
connected/reconnecting, alerts log) and a **non-dismissable** modal alert
(parity with RF-19) built on Textual, which is already asyncio-native — no
thread/bridge is needed here (unlike the Tk model in ADR-006), the
`Supervisor` just runs as a Textual worker on the same event loop.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, RichLog, Static

from vigia_eew.agent_state import AgentState
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.models import SeverityLevel
from vigia_eew.notify.presentation import AlertData, severity_color

_StatusSubscriber = Callable[[], None]


class AlertScreen(ModalScreen[None]):
    """Non-dismissable modal alert (RF-19): only ENTER acknowledges it."""

    BINDINGS = [
        Binding("enter", "acknowledge", "Acknowledge"),
        Binding("escape", "noop", "", show=False),
    ]

    def __init__(
        self,
        data: AlertData,
        *,
        on_acknowledge: Callable[[], None],
        locale_code: str = DEFAULT_LOCALE,
    ) -> None:
        super().__init__()
        self._data = data
        self._on_acknowledge = on_acknowledge
        self._locale = locale_code

    def compose(self) -> ComposeResult:
        yield Static(id="alert-body")

    def on_mount(self) -> None:
        self._paint()

    def update_data(self, data: AlertData) -> None:
        """Refreshes the displayed fields without recreating the screen (RF-11).

        Named differently from `Widget.refresh()` (which takes no arguments
        and just forces a re-render) to avoid colliding with it. Also named
        differently from `Widget._render()`, the internal hook the compositor
        calls to get the widget's `Visual` — overriding *that* silently breaks
        rendering (it returns `None` instead of the real content).
        """
        self._data = data
        self._paint()

    def _paint(self) -> None:
        data = self._data
        body = self.query_one("#alert-body", Static)
        text = (
            f"{t('seismic_alert_title', self._locale)}\n\n"
            f"{data.magnitude}\n"
            f"{data.place}\n"
            f"{data.distance}\n"
            f"{t('depth_label', self._locale)}: {data.depth}\n"
            f"{t('local_time_label', self._locale)}: {data.local_time}\n"
            f"{t('source_label', self._locale)}: {data.source}\n\n"
            f"[{t('acknowledged_button', self._locale)}: ENTER]"
        )
        body.update(text)
        body.styles.background = severity_color(data.severity)

    def action_acknowledge(self) -> None:
        self._on_acknowledge()
        self.dismiss()

    def action_noop(self) -> None:
        """Escape must not close the alert (RF-19 parity)."""


class _AlertHandle:
    """Handle returned to `AlertController` in place of a window object."""

    def __init__(self, screen: AlertScreen) -> None:
        self._screen = screen

    def refresh(self, data: AlertData) -> None:
        self._screen.update_data(data)


class VigiaTuiApp(App[None]):
    """Live status dashboard: WS status, alerts log, non-dismissable modal."""

    BINDINGS = [
        Binding("p", "toggle_pause", "Pause/Resume"),
        Binding("q", "quit_agent", "Quit"),
    ]

    def __init__(
        self,
        *,
        state: AgentState,
        locale_code: str = DEFAULT_LOCALE,
        on_start: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._state = state
        self._locale = locale_code
        self._on_start = on_start
        self._controller: Any = None
        self._supervisor: Any = None

    def bind_controller(self, controller: Any) -> None:
        """Wires the `p` binding to `AlertController.pause()`/`resume()`."""
        self._controller = controller

    def bind_supervisor(self, supervisor: Any) -> None:
        """Wires the `q` binding to `Supervisor.request_stop()` and starts its worker."""
        self._supervisor = supervisor

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="status-bar")
        yield RichLog(id="alerts-log")
        yield Footer()

    def on_mount(self) -> None:
        if self._supervisor is not None:
            self.run_worker(self._supervisor.run(), exclusive=True)
        self._refresh_status()
        self.set_interval(1.0, self._refresh_status)
        if self._on_start is not None:
            self._on_start()

    def _refresh_status(self) -> None:
        status = self.query_one("#status-bar", Static)
        key = "tray_ws_connected" if self._state.ws_connected else "tray_ws_reconnecting"
        status.update(t(key, self._locale))

    def action_toggle_pause(self) -> None:
        if self._controller is None:
            return
        if self._controller.paused:
            self._controller.resume()
        else:
            self._controller.pause()

    def action_quit_agent(self) -> None:
        if self._supervisor is not None:
            self._supervisor.request_stop()
        self.exit()

    def push_alert(
        self,
        data: AlertData,
        severity: SeverityLevel,
        on_acknowledge: Callable[[], None],
    ) -> _AlertHandle:
        """Shows the modal alert and logs it; matches `_WindowFactory` (RF-19, RF-20)."""
        screen = AlertScreen(data, on_acknowledge=on_acknowledge, locale_code=self._locale)
        self.push_screen(screen)
        log = self.query_one("#alerts-log", RichLog)
        log.write(f"{data.magnitude} · {data.place} · {data.local_time}")
        return _AlertHandle(screen)