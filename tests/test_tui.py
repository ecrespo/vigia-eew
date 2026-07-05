"""Tests for the headless TUI dashboard (RF-36, ADR-013)."""

from __future__ import annotations

import asyncio

from textual.widgets import RichLog, Static

from vigia_eew.agent_state import AgentState
from vigia_eew.notify.presentation import AlertData
from vigia_eew.tui import AlertScreen, VigiaTuiApp


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
    app = VigiaTuiApp(state=AgentState())
    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
    # no supervisor bound (simulate mode); q must still exit without raising


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
    application._controller_for_tui(app)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, AlertScreen)
        log = app.query_one("#alerts-log", RichLog)
        assert log.virtual_size.height >= 1
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, AlertScreen)