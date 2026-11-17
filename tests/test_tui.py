"""Tests for the headless TUI dashboard (RF-36, ADR-013)."""

from __future__ import annotations

import asyncio

import pytest
from textual.widgets import RichLog, Static

from vigia_eew.agent_state import AgentState
from vigia_eew.notify.presentation import AlertData
from vigia_eew.tui import AlertScreen, VigiaTuiApp

# Every test here mounts a real Textual app and drives it through its async
# driver. Headless, but a UI toolkit all the same -- and the slowest file.
pytestmark = pytest.mark.gui


def _data(severity: str = "critical", place: str = "La Guaira") -> AlertData:
    return AlertData(
        magnitude="M 6.1",
        place=place,
        distance="20 km from Caracas",
        depth="10 km",
        local_time="2026-07-04 10:00:00",
        source="SIMULATED",
        severity=severity,
    )


async def test_compose_shows_status_bar_and_alerts_log():
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test():
        assert app.query_one("#status-bar", Static) is not None
        assert app.query_one("#alerts-log", RichLog) is not None


async def test_status_bar_shows_reconnecting_by_default():
    state = AgentState()
    app = VigiaTuiApp(state=state)
    async with app.run_test():
        status = app.query_one("#status-bar", Static)
        assert "reconnecting" in str(status.render()).lower()


async def test_status_bar_shows_connected():
    state = AgentState()
    state.mark_connected()
    app = VigiaTuiApp(state=state)
    async with app.run_test():
        status = app.query_one("#status-bar", Static)
        assert "connected" in str(status.render()).lower()


async def test_push_alert_shows_modal_screen():
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test():
        app.push_alert(_data(), "critical", lambda: None)
        assert isinstance(app.screen, AlertScreen)


async def test_push_alert_writes_to_log():
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test():
        app.push_alert(_data(place="Maracaibo"), "critical", lambda: None)
        log = app.query_one("#alerts-log", RichLog)
        assert log.virtual_size.height >= 1


async def test_acknowledge_calls_callback_and_dismisses():
    app = VigiaTuiApp(state=AgentState())
    acknowledged: list[int] = []
    async with app.run_test() as pilot:
        app.push_alert(_data(), "critical", lambda: acknowledged.append(1))
        await pilot.pause()
        assert isinstance(app.screen, AlertScreen)
        await pilot.press("enter")
        await pilot.pause()
        assert acknowledged == [1]
        assert not isinstance(app.screen, AlertScreen)


async def test_escape_does_not_dismiss_alert():
    app = VigiaTuiApp(state=AgentState())
    acknowledged: list[int] = []
    async with app.run_test() as pilot:
        app.push_alert(_data(), "critical", lambda: acknowledged.append(1))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert acknowledged == []
        assert isinstance(app.screen, AlertScreen)


async def test_refresh_updates_visible_alert():
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test() as pilot:
        handle = app.push_alert(_data(place="Maracaibo"), "critical", lambda: None)
        await pilot.pause()
        handle.refresh(_data(place="Valencia"))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, AlertScreen)
        assert "Valencia" in str(screen.query_one("#alert-body", Static).render())


class _FakeController:
    def __init__(self) -> None:
        self.paused = False
        self.pause_calls = 0
        self.resume_calls = 0

    def pause(self) -> None:
        self.pause_calls += 1
        self.paused = True

    def resume(self) -> None:
        self.resume_calls += 1
        self.paused = False


async def test_toggle_pause_binding_pauses_then_resumes():
    app = VigiaTuiApp(state=AgentState())
    ctrl = _FakeController()
    app.bind_controller(ctrl)
    async with app.run_test() as pilot:
        await pilot.press("p")
        await pilot.pause()
        assert ctrl.pause_calls == 1
        await pilot.press("p")
        await pilot.pause()
        assert ctrl.resume_calls == 1


class _FakeSupervisor:
    def __init__(self) -> None:
        self.stop_calls = 0
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        await self._stop_event.wait()

    def request_stop(self) -> None:
        self.stop_calls += 1
        self._stop_event.set()


async def test_quit_binding_requests_stop_and_exits():
    app = VigiaTuiApp(state=AgentState())
    sup = _FakeSupervisor()
    app.bind_supervisor(sup)
    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
        assert sup.stop_calls == 1


async def test_quit_without_supervisor_exits_cleanly():
    """In simulate mode nothing is bound, and `q` must still exit.

    "Does not raise" was the old assertion, and a binding that did nothing at
    all passed it. What matters is that the app is actually gone afterwards.
    """
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running


async def test_on_start_runs_after_mount():
    calls: list[int] = []
    app = VigiaTuiApp(state=AgentState(), on_start=lambda: calls.append(1))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert calls == [1]


async def test_simulate_tui_end_to_end_shows_and_acknowledges():
    """Full `--simulate --tui` wiring, headless (mirrors Application.run_tui)."""
    from vigia_eew.app import Application
    from vigia_eew.config import Notification, Settings

    application = Application(Settings(notification=Notification(sound=False)))
    app = VigiaTuiApp(
        state=application._agent_state,
        on_start=application._inject_simulated_alert,
    )
    # Mirrors run_tui: the application keeps the controller, which is what
    # on_start reaches for when it injects the simulated event.
    application._ctrl = application.wiring.build_tui_controller(
        app, on_acknowledge=application._after_acknowledge
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, AlertScreen)
        log = app.query_one("#alerts-log", RichLog)
        assert log.virtual_size.height >= 1
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, AlertScreen)


# --- T-176 · the history in the terminal (REQ-HIS-015, HU-121, ADR-041) ------------
#
# Only the list: no map and no playback fit in a terminal. The screen draws
# what `HistoryList` decided, so what is checked here is that it shows the
# list's rows, sets the list's filters, and never costs the dashboard anything.

from datetime import UTC, datetime, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402

from textual.widgets import DataTable, Input, Select  # noqa: E402

from vigia_eew.history import EventRecord, HistoryStore  # noqa: E402
from vigia_eew.i18n import t  # noqa: E402
from vigia_eew.notify.history_list import COLUMNS, HistoryList  # noqa: E402
from vigia_eew.tui import HistoryScreen, HistoryUnavailableScreen  # noqa: E402

_WHEN = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _arrival(
    event_id: str,
    *,
    magnitude: float,
    source: str = "EMSC",
    verdict: str = "discarded",
    reason: str | None = "radius",
    minutes: int = 0,
    distance_km: float = 300.0,
    earthquake: str | None = None,
) -> EventRecord:
    moment = _WHEN + timedelta(minutes=minutes)
    return EventRecord(
        correlation_id=earthquake or f"tr-{event_id}",
        source=source,
        source_event_id=event_id,
        occurred_at=moment,
        recorded_at=moment,
        latitude=10.6,
        longitude=-66.9,
        depth_km=12.0,
        magnitude=magnitude,
        region=f"PLACE {event_id.upper()}",
        distance_km=distance_km,
        verdict=verdict,
        reason=reason if verdict == "discarded" else None,
    )


@pytest.fixture
def history(tmp_path: Path):
    """Five arrivals of four earthquakes, from three networks, over two days."""
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.open()
    store.record(_arrival("a", magnitude=6.1, verdict="alerted", distance_km=20.0, earthquake="q1"))
    store.record(
        _arrival("a2", magnitude=6.0, source="USGS", reason="duplicate", minutes=1, earthquake="q1")
    )
    store.record(_arrival("b", magnitude=4.4, minutes=10))
    store.record(_arrival("c", magnitude=2.7, source="FUNVISIS", reason="magnitude", minutes=20))
    store.record(_arrival("d", magnitude=5.0, minutes=60 * 30))
    yield store
    store.close()


def _history_app(store: HistoryStore, *, page_size: int = 150, closed: list | None = None):
    def opened() -> HistoryList:
        return HistoryList(store, locale_code="en", zone="UTC", page_size=page_size)

    return VigiaTuiApp(
        state=AgentState(),
        open_history=opened,
        close_history=(lambda: closed.append(1)) if closed is not None else None,
    )


def _as_shown(listing: HistoryList) -> list[tuple[str, ...]]:
    return [tuple(str(getattr(row, column.key)) for column in COLUMNS) for row in listing.rows]


async def _open(pilot) -> HistoryScreen:
    await pilot.press("h")
    await pilot.pause()
    screen = pilot.app.screen
    assert isinstance(screen, HistoryScreen)
    return screen


async def _type(pilot, screen: HistoryScreen, field: str, text: str) -> None:
    screen.query_one(f"#filter-{field}", Input).value = text
    await pilot.pause()


# CA-121.1 · The list is in the terminal


async def test_the_history_opens_from_the_dashboard_with_a_key(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        assert len(screen.shown) == 5
        assert screen.query_one("#history-table", DataTable).row_count == 5


async def test_the_table_has_the_columns_of_the_list(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        table = screen.query_one("#history-table", DataTable)
        labels = [str(column.label) for column in table.columns.values()]
        assert labels == [screen.listing.label(column) for column in COLUMNS]
        assert "Magnitude" in labels and "Verdict" in labels and "Reason" in labels


async def test_there_is_a_control_for_each_criterion_the_store_filters_by(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        for field in ("since", "until", "magnitude", "distance", "sources"):
            assert screen.query_one(f"#filter-{field}", Input) is not None
        assert screen.query_one("#filter-verdict", Select) is not None


async def test_the_status_line_says_which_stretch_is_on_screen(history) -> None:
    app = _history_app(history, page_size=2)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        assert "1–2 of 5" in screen.status_text


async def test_the_pager_reaches_the_rest_and_comes_back(history) -> None:
    app = _history_app(history, page_size=2)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)
        first_page = screen.shown

        await pilot.press("n")
        await pilot.pause()
        assert "3–4 of 5" in screen.status_text
        assert screen.shown != first_page

        await pilot.press("n")
        await pilot.press("n")  # past the end: stays on the last page
        await pilot.pause()
        assert "5–5 of 5" in screen.status_text

        await pilot.press("b")
        await pilot.press("b")
        await pilot.pause()
        assert screen.shown == first_page


async def test_an_empty_history_says_so(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "empty.sqlite3").open()
    app = _history_app(store)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        assert screen.shown == []
        assert "Nothing recorded yet." in screen.status_text
    store.close()


# CA-121.2 · The same filter gives the same entries


async def test_the_rows_are_the_lists_rows_in_the_lists_order(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        assert screen.shown == _as_shown(HistoryList(history, locale_code="en", zone="UTC"))


async def test_the_verdict_filter_gives_what_the_graphical_list_gives(history) -> None:
    graphical = HistoryList(history, locale_code="en", zone="UTC")
    graphical.set_verdict("discarded")
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        screen.query_one("#filter-verdict", Select).value = "discarded"
        await pilot.pause()

        assert screen.shown == _as_shown(graphical)
        assert len(screen.shown) == 4


async def test_the_verdicts_offered_are_the_ones_the_history_holds(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        assert screen.verdicts_offered == ["alerted", "discarded"]


async def test_the_magnitude_and_distance_fields_filter(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        await _type(pilot, screen, "magnitude", "5")
        assert {row[2] for row in screen.shown} == {"PLACE A", "PLACE A2", "PLACE D"}

        await _type(pilot, screen, "distance", "100")
        assert [row[2] for row in screen.shown] == ["PLACE A"]


async def test_a_half_typed_number_is_not_a_filter_yet(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        await _type(pilot, screen, "magnitude", "5.x")

        assert len(screen.shown) == 5


async def test_the_period_fields_keep_those_days(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        await _type(pilot, screen, "since", "2026-09-20")
        assert [row[2] for row in screen.shown] == ["PLACE D"]

        await _type(pilot, screen, "since", "")
        await _type(pilot, screen, "until", "2026-09-19")
        assert len(screen.shown) == 4


async def test_a_period_that_ends_before_it_starts_is_said_and_changes_nothing(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)
        await _type(pilot, screen, "since", "2026-09-20")

        await _type(pilot, screen, "until", "2026-09-01")

        assert [row[2] for row in screen.shown] == ["PLACE D"]
        assert "The period ends before it starts." in screen.status_text


async def test_the_networks_field_keeps_the_networks_named(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)

        await _type(pilot, screen, "sources", "usgs, funvisis")
        assert {row[4] for row in screen.shown} == {"USGS", "FUNVISIS"}

        await _type(pilot, screen, "sources", "usgs, nobod")  # not a network yet
        assert {row[4] for row in screen.shown} == {"USGS", "FUNVISIS"}

        await _type(pilot, screen, "sources", "")
        assert len(screen.shown) == 5


async def test_one_key_reads_per_earthquake_and_back(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)
        screen.query_one("#history-table", DataTable).focus()

        await pilot.press("e")
        await pilot.pause()
        assert len(screen.shown) == 4
        assert "PLACE A2" not in {row[2] for row in screen.shown}

        await pilot.press("e")
        await pilot.pause()
        assert len(screen.shown) == 5


async def test_one_key_clears_every_filter_and_its_field(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)
        await _type(pilot, screen, "magnitude", "6")
        screen.query_one("#history-table", DataTable).focus()

        await pilot.press("c")
        await pilot.pause()

        assert len(screen.shown) == 5
        assert screen.query_one("#filter-magnitude", Input).value == ""


async def test_leaving_goes_back_to_the_dashboard_and_closes_the_reader(history) -> None:
    closed: list[int] = []
    app = _history_app(history, closed=closed)
    async with app.run_test(size=(160, 40)) as pilot:
        await _open(pilot)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, HistoryScreen)
        assert app.query_one("#status-bar", Static) is not None
        assert closed == [1]


async def test_the_history_key_does_not_open_a_second_one(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)
        screen.query_one("#history-table", DataTable).focus()

        await pilot.press("h")
        await pilot.pause()

        assert len(app.screen_stack) == 2


async def test_without_a_history_to_open_the_key_does_nothing() -> None:
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test() as pilot:
        await pilot.press("h")
        await pilot.pause()

        assert len(app.screen_stack) == 1


# CA-121.3 · A history that cannot be opened does not stop the dashboard


async def test_a_history_that_cannot_be_opened_is_said_with_its_reason() -> None:
    def broken() -> HistoryList:
        raise RuntimeError("history.sqlite3 was written with schema version 9")

    state = AgentState()
    app = VigiaTuiApp(state=state, open_history=broken)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.press("h")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, HistoryUnavailableScreen)
        said = str(screen.query_one("#history-unavailable", Static).render())
        assert t("history_unavailable", "en") in said
        assert "schema version 9" in said

        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 1


async def test_the_dashboard_keeps_updating_under_the_history(history) -> None:
    state = AgentState()
    app = _history_app(history)
    app._state = state
    async with app.run_test(size=(160, 40)) as pilot:
        await _open(pilot)

        state.mark_connected()
        app._refresh_status()  # what the one-second timer calls
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        status = app.query_one("#status-bar", Static)
        assert "connected" in str(status.render()).lower()
        assert "reconnecting" not in str(status.render()).lower()


# CA-121.4 · An alert takes the terminal


async def test_an_alert_is_shown_over_the_list_and_the_list_is_back_after_it(history) -> None:
    app = _history_app(history)
    acknowledged: list[int] = []
    async with app.run_test(size=(160, 40)) as pilot:
        screen = await _open(pilot)
        await _type(pilot, screen, "magnitude", "5")
        before = screen.shown

        app.push_alert(_data(place="Maracaibo"), "critical", lambda: acknowledged.append(1))
        await pilot.pause()
        assert isinstance(app.screen, AlertScreen)

        await pilot.press("escape")  # neither closes the alert nor the list under it
        await pilot.pause()
        assert isinstance(app.screen, AlertScreen)

        await pilot.press("enter")
        await pilot.pause()
        assert acknowledged == [1]
        assert app.screen is screen
        assert screen.shown == before


async def test_an_alert_over_the_list_is_still_logged_on_the_dashboard(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        await _open(pilot)

        app.push_alert(_data(place="Maracaibo"), "critical", lambda: None)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.press("escape")
        await pilot.pause()

        log = app.query_one("#alerts-log", RichLog)
        assert log.virtual_size.height >= 1


async def test_the_history_cannot_be_opened_over_an_alert(history) -> None:
    app = _history_app(history)
    async with app.run_test(size=(160, 40)) as pilot:
        app.push_alert(_data(), "critical", lambda: None)
        await pilot.pause()

        await pilot.press("h")
        await pilot.pause()

        assert isinstance(app.screen, AlertScreen)
        assert len(app.screen_stack) == 2


# The terminal frontend loads no graphical toolkit


def test_the_terminal_frontend_does_not_load_the_graphical_toolkit() -> None:
    """In a fresh interpreter: importing the dashboard must not import Flet."""
    import subprocess
    import sys

    probe = (
        "import sys, vigia_eew.tui; "
        "print(sorted(m for m in sys.modules if m.split('.')[0] in ('flet', 'flet_map')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == "[]"


# --- Text from a network is text, never markup --------------------------------------
#
# The place is whatever a network sent. Textual reads square brackets in a
# string as markup: a tag would restyle the row, and an unbalanced one raises.

_HOSTILE = "[bold red]NEAR[/bold red] CARACAS [/nope] [link=http://example.invalid]x[/link]"


async def test_a_place_with_brackets_in_it_is_listed_as_it_was_sent(tmp_path: Path) -> None:
    from dataclasses import replace

    store = HistoryStore(tmp_path / "hostile.sqlite3").open()
    store.record(replace(_arrival("x", magnitude=5.0), region=_HOSTILE))
    app = _history_app(store)
    async with app.run_test(size=(200, 40)) as pilot:
        screen = await _open(pilot)
        await pilot.pause()

        assert screen.shown[0][2] == _HOSTILE
        cell = screen.query_one("#history-table", DataTable).get_row_at(0)[2]
        assert cell.plain == _HOSTILE and not cell.spans
    store.close()


async def test_an_alert_whose_place_has_brackets_in_it_is_still_shown() -> None:
    """The alert is the one thing that must not fail to draw."""
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test(size=(200, 40)) as pilot:
        app.push_alert(_data(place=_HOSTILE), "critical", lambda: None)
        await pilot.pause()

        assert isinstance(app.screen, AlertScreen)
        body = app.screen.query_one("#alert-body", Static)
        assert _HOSTILE in str(body.render())


async def test_a_reason_the_store_gives_for_being_unreadable_is_shown_as_text() -> None:
    def broken() -> HistoryList:
        raise RuntimeError("cannot open [/nope] history")

    app = VigiaTuiApp(state=AgentState(), open_history=broken)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.press("h")
        await pilot.pause()

        said = str(app.screen.query_one("#history-unavailable", Static).render())
        assert "cannot open [/nope] history" in said


# --- T-178, T-179 · the terminal alert: the shaking, and the drill label -----------

from dataclasses import replace as _replace  # noqa: E402

_ARRIVES = datetime(2026, 6, 28, 13, 40, tzinfo=UTC)


class _Clock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


def _body(app) -> str:
    return str(app.screen.query_one("#alert-body", Static).render())


async def test_the_terminal_alert_says_how_long_ago_the_shaking_should_have_arrived():
    clock = _Clock(_ARRIVES + timedelta(minutes=20))
    app = VigiaTuiApp(state=AgentState(), now=clock)
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_alert(_replace(_data(), shaking_arrival=_ARRIVES), "critical", lambda: None)
        await pilot.pause()

        assert "The shaking should already have arrived ≈ 20 min ago" in _body(app)


async def test_the_terminal_alert_recounts_while_it_is_on_screen():
    clock = _Clock(_ARRIVES - timedelta(seconds=30))
    app = VigiaTuiApp(state=AgentState(), now=clock)
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_alert(_replace(_data(), shaking_arrival=_ARRIVES), "critical", lambda: None)
        await pilot.pause()
        assert "Shaking expected in ≈ 30 s" in _body(app)

        clock.moment += timedelta(seconds=31)
        app.screen.recount()  # what the one-second interval calls
        await pilot.pause()

        assert "The shaking should already have arrived ≈ 1 s ago" in _body(app)


async def test_the_terminal_alert_counts_on_an_interval():
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_alert(_data(), "critical", lambda: None)
        await pilot.pause()

        assert app.screen.recount_timer is not None


async def test_without_an_estimate_the_terminal_alert_has_no_line():
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_alert(_data(), "critical", lambda: None)
        await pilot.pause()

        assert "haking" not in _body(app)
        assert "M 6.1" in _body(app)


async def test_a_revision_recomputes_the_line_in_the_terminal():
    clock = _Clock(_ARRIVES + timedelta(minutes=5))
    app = VigiaTuiApp(state=AgentState(), now=clock)
    async with app.run_test(size=(120, 40)) as pilot:
        handle = app.push_alert(
            _replace(_data(), shaking_arrival=_ARRIVES), "critical", lambda: None
        )
        await pilot.pause()

        handle.refresh(_replace(_data(), shaking_arrival=_ARRIVES + timedelta(minutes=3)))
        await pilot.pause()

        assert "≈ 2 min ago" in _body(app)


async def test_a_drill_is_labelled_first_in_the_terminal():
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_alert(_replace(_data(), drill=True), "critical", lambda: None)
        await pilot.pause()

        assert _body(app).lstrip().startswith("DRILL — this is not a real earthquake")


async def test_a_drill_is_labelled_in_spanish_in_the_terminal():
    app = VigiaTuiApp(state=AgentState(), locale_code="es")
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_alert(_replace(_data(), drill=True), "critical", lambda: None)
        await pilot.pause()

        assert "SIMULACRO — no es un sismo real" in _body(app)


async def test_a_real_alert_has_no_drill_label_in_the_terminal():
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_alert(_data(), "critical", lambda: None)
        await pilot.pause()

        assert "DRILL" not in _body(app)


async def test_the_terminal_alert_can_be_closed_without_acknowledging_it():
    """What a real alert does to a drill on screen (REQ-UX-009)."""
    acknowledged: list[int] = []
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test(size=(120, 40)) as pilot:
        handle = app.push_alert(_data(), "critical", lambda: acknowledged.append(1))
        await pilot.pause()

        handle.close()
        await pilot.pause()

        assert not isinstance(app.screen, AlertScreen)
        assert acknowledged == []


async def test_the_terminal_alert_names_the_zone_of_its_time():
    data = _replace(
        _data(),
        local_time="2026-06-28 15:39:00",
        zone_abbreviation="CEST",
        zone_name="Europe/Madrid",
    )
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_alert(data, "critical", lambda: None)
        await pilot.pause()

        assert "2026-06-28 15:39:00 CEST (Europe/Madrid)" in _body(app)
