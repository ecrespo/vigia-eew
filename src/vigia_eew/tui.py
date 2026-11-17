"""Headless TUI dashboard (RF-36, ADR-013).

Alternative frontend to Flet+tray for running the agent on a headless
server over SSH, with no desktop session: a live status dashboard (WS
connected/reconnecting, alerts log) and a **non-dismissable** modal alert
(parity with RF-19) built on Textual, which is already asyncio-native — no
thread/bridge is needed here (unlike the Flet model in ADR-006), the
`Supervisor` just runs as a Textual worker on the same event loop.

It also lists the history (REQ-HIS-015, ADR-041): a machine with no display is
where "why did it not alert?" is otherwise answered by reading a log. Only the
list -- a map and a playback do not fit in a terminal -- and through the same
`HistoryList` the window draws, so a filter means one thing in both.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Footer, Header, Input, RichLog, Select, Static

from vigia_eew.agent_state import AgentState
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.models import SeverityLevel
from vigia_eew.notify.history_list import (
    COLUMNS,
    DATE_HINT,
    NOT_YET,
    HistoryList,
    day_in,
    number_in,
)
from vigia_eew.notify.presentation import AlertData, severity_color

_StatusSubscriber = Callable[[], None]

#: Opens the history for reading and hands over the list; raises when the
#: file cannot be read. The dashboard is given this rather than a store so
#: that it knows nothing about where the history is or how it is opened.
OpenHistory = Callable[[], HistoryList]


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
        # `markup=False`: the place is whatever a network sent, and a string
        # with square brackets in it is markup to Textual -- an unbalanced tag
        # raises, and this is the one screen that must not fail to draw.
        # @lat: [[notification#Text from a network is never markup]]
        yield Static(id="alert-body", markup=False)

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


class HistoryScreen(Screen[None]):
    """The history list in the terminal: the table, its filters, its pager.

    Draws what `HistoryList` decided and sets its filters; it decides nothing
    itself, which is what makes the same filter give the same entries here
    and in the window (CA-121.2).

    The table has the focus when the screen opens, so the keys below work at
    once; TAB reaches the filter fields, where a letter is a letter.
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("n", "next_page", "Next page"),
        Binding("b", "previous_page", "Previous page"),
        Binding("e", "toggle_reading", "Per earthquake"),
        Binding("c", "clear_filters", "Clear filters"),
    ]

    DEFAULT_CSS = """
    HistoryScreen #history-filters { height: 3; }
    HistoryScreen #history-filters Input { width: 1fr; }
    HistoryScreen #history-filters Select { width: 1fr; }
    HistoryScreen #history-table { height: 1fr; }
    HistoryScreen #history-status { height: 1; }
    """

    #: The text fields, and the phrase each one is labelled with.
    _FIELDS = (
        ("since", "history_filter_since"),
        ("until", "history_filter_until"),
        ("magnitude", "history_filter_magnitude"),
        ("distance", "history_filter_distance"),
        ("sources", "history_filter_source"),
    )

    def __init__(self, listing: HistoryList, *, locale_code: str = DEFAULT_LOCALE) -> None:
        super().__init__()
        self.listing = listing
        self._locale = locale_code
        self._period_refused = False
        #: What the status line under the table says.
        self.status_text = ""
        #: The verdicts the filter offers: the ones this history holds.
        self.verdicts_offered: list[str] = []

    def compose(self) -> ComposeResult:
        loc = self._locale
        yield Header()
        with Horizontal(id="history-filters"):
            for name, label_key in self._FIELDS:
                hint = f" ({DATE_HINT})" if name in ("since", "until") else ""
                yield Input(placeholder=t(label_key, loc) + hint, id=f"filter-{name}")
            yield Select[str]([], prompt=t("history_filter_verdict", loc), id="filter-verdict")
        yield DataTable(id="history-table", cursor_type="row", zebra_stripes=True)
        yield Static(id="history-status", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns(*(self.listing.label(column) for column in COLUMNS))
        table.focus()
        self._draw()

    # --- Drawing ---

    @property
    def shown(self) -> list[tuple[str, ...]]:
        """The rows on screen, cell by cell, as the table holds them."""
        table = self.query_one("#history-table", DataTable)
        return [
            tuple(str(cell) for cell in table.get_row_at(index)) for index in range(table.row_count)
        ]

    def _draw(self) -> None:
        """Redraws the table and the status line from what the list holds."""
        listing = self.listing
        table = self.query_one("#history-table", DataTable)
        table.clear()
        for row in listing.rows:
            # `Text`, not `str`: a string cell is read as markup, and these
            # are the networks' words (see `AlertScreen.compose`).
            table.add_row(*(Text(str(getattr(row, column.key))) for column in COLUMNS))
        self._offer_verdicts()
        if self._period_refused:
            said = t("history_period_invalid", self._locale)
        elif listing.total:
            said = listing.stretch_text
        else:
            said = t("history_empty", self._locale)
        if listing.reading == "earthquake":
            said += " · " + t("history_reading_earthquake", self._locale)
        self.status_text = said
        self.query_one("#history-status", Static).update(said)

    def _offer_verdicts(self) -> None:
        """Offers the verdicts the history holds; keeps the one chosen."""
        available = list(self.listing.available_verdicts)
        if available == self.verdicts_offered:
            return
        self.verdicts_offered = available
        select = self.query_one("#filter-verdict", Select)
        chosen = self.listing.query.verdict
        select.set_options((Text(self._verdict_label(verdict)), verdict) for verdict in available)
        if chosen in available:
            select.value = chosen

    def _verdict_label(self, verdict: str) -> str:
        key = f"history_verdict_{verdict}"
        label = t(key, self._locale)
        return verdict if label == key else label

    # --- The filters: each field sets one of the list's (REQ-HIS-007) ---

    def on_input_changed(self, event: Input.Changed) -> None:
        name = (event.input.id or "").removeprefix("filter-")
        if name in ("since", "until"):
            self._apply_period()
        elif name == "magnitude":
            self._apply_number(event.value, self.listing.set_min_magnitude)
        elif name == "distance":
            self._apply_number(event.value, self.listing.set_max_distance)
        elif name == "sources":
            self._apply_sources(event.value)

    def on_select_changed(self, event: Select.Changed) -> None:
        # Read from the control, not the message: the options are rebuilt
        # when the history gains a verdict, and a message from before that
        # would otherwise undo the choice it restored.
        value = event.select.value
        chosen = value if isinstance(value, str) else None
        if chosen != self.listing.query.verdict:
            self.listing.set_verdict(chosen)
            self._draw()

    def _apply_number(self, raw: str, setter: Callable[[float | None], None]) -> None:
        value = number_in(raw)
        if value is NOT_YET:
            return  # half-typed: not a filter yet
        setter(value)
        self._draw()

    def _apply_period(self) -> None:
        first = day_in(self.query_one("#filter-since", Input).value)
        last = day_in(self.query_one("#filter-until", Input).value)
        if first is NOT_YET or last is NOT_YET:
            return
        try:
            self.listing.set_period(first, last)
        except ValueError:
            # The list refused and kept its query: the table still shows the
            # entries of the last period that made sense.
            self._period_refused = True
        else:
            self._period_refused = False
        self._draw()

    def _apply_sources(self, raw: str) -> None:
        """Keeps the networks named, separated by commas; none named is all."""
        known = {source.upper(): source for source in self.listing.available_sources}
        names = [name.strip().upper() for name in raw.split(",") if name.strip()]
        if any(name not in known for name in names):
            return  # a name still being typed: not a filter yet
        self.listing.set_sources([known[name] for name in names])
        self._draw()

    # --- Keys ---

    def action_next_page(self) -> None:
        self.listing.next_page()
        self._draw()

    def action_previous_page(self) -> None:
        self.listing.previous_page()
        self._draw()

    def action_toggle_reading(self) -> None:
        reading = "arrival" if self.listing.reading == "earthquake" else "earthquake"
        self.listing.set_reading(reading)
        self._draw()

    def action_clear_filters(self) -> None:
        self._period_refused = False
        self.listing.clear_filters()
        for name, _label_key in self._FIELDS:
            self.query_one(f"#filter-{name}", Input).value = ""
        self.query_one("#filter-verdict", Select).clear()
        self._draw()

    def action_back(self) -> None:
        self.dismiss()


class HistoryUnavailableScreen(Screen[None]):
    """What the terminal shows when the history cannot be read (CA-121.3).

    It says so and gives the reason as the store reported it, and it is a
    screen like any other: the dashboard under it keeps running.
    """

    BINDINGS = [Binding("escape", "back", "Back")]

    def __init__(self, reason: str, *, locale_code: str = DEFAULT_LOCALE) -> None:
        super().__init__()
        self._reason = reason
        self._locale = locale_code

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            f"{t('history_unavailable', self._locale)}\n\n{self._reason}",
            id="history-unavailable",
            markup=False,
        )
        yield Footer()

    def action_back(self) -> None:
        self.dismiss()


class VigiaTuiApp(App[None]):
    """Live status dashboard: WS status, alerts log, non-dismissable modal."""

    BINDINGS = [
        Binding("p", "toggle_pause", "Pause/Resume"),
        Binding("h", "history", "History"),
        Binding("q", "quit_agent", "Quit"),
    ]

    def __init__(
        self,
        *,
        state: AgentState,
        locale_code: str = DEFAULT_LOCALE,
        on_start: Callable[[], None] | None = None,
        open_history: OpenHistory | None = None,
        close_history: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._state = state
        self._locale = locale_code
        self._on_start = on_start
        self._open_history = open_history
        self._close_history = close_history
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

    @property
    def _dashboard(self) -> Any:
        """The dashboard's own screen, whatever is on top of it.

        `App.query_one` looks in the screen on top. With the history or an
        alert there, the status bar and the log are underneath -- and they
        still have to be kept up to date.
        """
        return self.screen_stack[0]

    def _refresh_status(self) -> None:
        status = self._dashboard.query_one("#status-bar", Static)
        key = "tray_ws_connected" if self._state.ws_connected else "tray_ws_reconnecting"
        status.update(t(key, self._locale))

    def action_toggle_pause(self) -> None:
        if self._controller is None:
            return
        if self._controller.paused:
            self._controller.resume()
        else:
            self._controller.pause()

    def action_history(self) -> None:
        """Opens the history list over the dashboard (REQ-HIS-015).

        Only from the dashboard itself: not twice, and never over an alert,
        which keeps the terminal until it is acknowledged.
        """
        if self._open_history is None or len(self.screen_stack) > 1:
            return
        try:
            listing = self._open_history()
        except Exception as exc:  # noqa: BLE001 - the history may never cost the dashboard
            self.push_screen(
                HistoryUnavailableScreen(str(exc), locale_code=self._locale), self._history_closed
            )
            return
        self.push_screen(HistoryScreen(listing, locale_code=self._locale), self._history_closed)

    def _history_closed(self, _result: None) -> None:
        if self._close_history is not None:
            self._close_history()

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
        log = self._dashboard.query_one("#alerts-log", RichLog)
        log.write(f"{data.magnitude} · {data.place} · {data.local_time}")
        return _AlertHandle(screen)
