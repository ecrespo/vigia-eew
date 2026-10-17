"""Tests for the application assembly (RF-26, supervisor/notification wiring)."""

from __future__ import annotations

import asyncio

from vigia_eew.app import Application
from vigia_eew.config import (
    EMSCSource,
    Filter,
    FUNVISISSource,
    GEOFONSource,
    Notification,
    ReferencePoint,
    Settings,
    USGSSource,
)
from vigia_eew.simulation import simulated_event
from vigia_eew.state import StateStore
from vigia_eew.tray import TrayIcon


class _FakeWindow:
    def refresh(self, data):
        pass


class _FakeShell:
    def __init__(self):
        self.after_calls: list[tuple[int, object]] = []

    def after(self, ms, callback):
        self.after_calls.append((ms, callback))

    def quit(self):
        pass


def _app(**cfg_kw) -> Application:
    return Application(Settings(**cfg_kw))


# --- Supervisor wiring based on enabled sources ---


def test_supervisor_with_all_sources():
    app = _app()
    sup = app.wiring.build_supervisor(asyncio.Queue(), object())
    assert sup.names == ["ws", "rest", "funvisis", "geofon", "pipeline", "history"]


def test_supervisor_without_emsc():
    app = _app(sources_emsc=EMSCSource(enabled=False))
    sup = app.wiring.build_supervisor(asyncio.Queue(), object())
    assert sup.names == ["rest", "funvisis", "geofon", "pipeline", "history"]


def test_supervisor_without_usgs():
    app = _app(sources_usgs=USGSSource(enabled=False))
    sup = app.wiring.build_supervisor(asyncio.Queue(), object())
    assert sup.names == ["ws", "funvisis", "geofon", "pipeline", "history"]


def test_supervisor_without_funvisis():
    app = _app(sources_funvisis=FUNVISISSource(enabled=False))
    sup = app.wiring.build_supervisor(asyncio.Queue(), object())
    assert sup.names == ["ws", "rest", "geofon", "pipeline", "history"]


def test_supervisor_without_geofon():
    app = _app(sources_geofon=GEOFONSource(enabled=False))
    sup = app.wiring.build_supervisor(asyncio.Queue(), object())
    assert sup.names == ["ws", "rest", "funvisis", "pipeline", "history"]


# --- Notification controller built by the app ---


def test_controller_formats_and_shows():
    app = _app()
    seen: list = []
    ctrl = app.wiring.build_controller(
        lambda data, severity, on_acknowledge: seen.append((data, severity)) or _FakeWindow(),
        on_acknowledge=app._after_acknowledge,
    )
    ctrl.enqueue(simulated_event(app.cfg.reference, app.cfg.severity))
    assert len(seen) == 1
    data, severity = seen[0]
    assert data.magnitude == "M 6.1"
    assert severity == "critical"
    assert "La Guaira" in data.place


# --- Automatic IP-based location detection (RF-33) ---


def test_prepare_without_resolve_does_not_call_geoloc(tmp_path):
    calls: list[int] = []
    app = Application(
        Settings(),
        state=StateStore(tmp_path / "state.json"),
        manual_reference=False,
        detect_location=lambda: calls.append(1) or None,
    )
    app._prepare()  # resolve_location=False by default (used by --simulate)
    assert calls == []


def test_prepare_resolves_automatic_location(tmp_path):
    detected = ReferencePoint(name="Maracaibo", lat=10.63, lon=-71.64)
    app = Application(
        Settings(),
        state=StateStore(tmp_path / "state.json"),
        manual_reference=False,
        detect_location=lambda: detected,
    )
    app._prepare(resolve_location=True)
    assert app.cfg.reference.name == "Maracaibo"
    cached = app.state.cached_location()
    assert cached is not None
    assert cached.name == "Maracaibo"


def test_prepare_respects_manual_reference(tmp_path):
    calls: list[int] = []
    app = Application(
        Settings(reference={"name": "Valencia", "lat": 10.16, "lon": -68.0}),
        state=StateStore(tmp_path / "state.json"),
        manual_reference=True,
        detect_location=lambda: calls.append(1) or ReferencePoint(name="x", lat=0, lon=0),
    )
    app._prepare(resolve_location=True)
    assert calls == []
    assert app.cfg.reference.name == "Valencia"


def test_prepare_uses_cache_without_calling_geoloc(tmp_path):
    state_path = tmp_path / "state.json"
    previous = StateStore(state_path)
    previous.load()
    previous.cache_location(ReferencePoint(name="Cache", lat=1.0, lon=2.0))
    previous.save()

    calls: list[int] = []
    app = Application(
        Settings(),
        state=StateStore(state_path),
        manual_reference=False,
        detect_location=lambda: calls.append(1) or None,
    )
    app._prepare(resolve_location=True)
    assert calls == []
    assert app.cfg.reference.name == "Cache"


def test_prepare_falls_back_to_default_if_geoloc_fails(tmp_path):
    app = Application(
        Settings(),
        state=StateStore(tmp_path / "state.json"),
        manual_reference=False,
        detect_location=lambda: None,
    )
    app._prepare(resolve_location=True)
    assert app.cfg.reference.name == "Caracas"  # default, not cached
    assert app.state.cached_location() is None


# --- Tray icon (RF-34) ---


def test_build_tray_disabled_returns_none():
    app = _app(notification=Notification(tray_icon=False))
    assert app._build_tray() is None


def test_build_tray_enabled_returns_icon():
    app = _app()
    icon = app._build_tray()
    assert isinstance(icon, TrayIcon)


def test_toggle_pause_schedules_on_ui_thread():
    app = _app()
    app._shell = _FakeShell()
    ctrl = app.wiring.build_controller(
        lambda data, severity, on_acknowledge: _FakeWindow(),
        on_acknowledge=app._after_acknowledge,
    )
    app._ctrl = ctrl
    assert ctrl.paused is False

    app._toggle_pause()
    assert len(app._shell.after_calls) == 1
    ms, callback = app._shell.after_calls[0]
    assert ms == 0
    callback()  # runs the scheduled callback, like the UI loop would
    assert ctrl.paused is True


def test_exit_from_tray_schedules_quit():
    app = _app()
    app._shell = _FakeShell()
    app._exit_from_tray()
    assert len(app._shell.after_calls) == 1
    ms, callback = app._shell.after_calls[0]
    assert ms == 0
    assert callable(callback)


def test_edit_config_uses_explicit_path(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"
    calls = []
    import vigia_eew.wiring as wiring_mod

    monkeypatch.setattr(wiring_mod.tray, "open_config", lambda r: calls.append(r))
    app = Application(Settings(), config_path=path)
    app._edit_config()
    assert calls == [path]


def test_edit_config_uses_default_path_without_explicit_config(monkeypatch):
    calls = []
    import vigia_eew.app as app_mod
    import vigia_eew.wiring as wiring_mod

    monkeypatch.setattr(wiring_mod.tray, "open_config", lambda r: calls.append(r))
    app = _app()
    app._edit_config()
    assert len(calls) == 1
    assert calls[0] == app_mod.default_config_path()


# --- Headless TUI dashboard wiring (RF-36) ---


class _FakeTuiApp:
    def __init__(self):
        self.pushed: list = []
        self.bound_controller = None
        self.bound_supervisor = None

    def push_alert(self, data, severity, on_acknowledge):
        self.pushed.append((data, severity))
        return object()

    def bind_controller(self, ctrl):
        self.bound_controller = ctrl

    def bind_supervisor(self, sup):
        self.bound_supervisor = sup


def test_wire_tui_builds_controller_using_push_alert():
    app = _app()
    tui_app = _FakeTuiApp()
    ctrl = app._wire_tui(tui_app)
    ctrl.enqueue(simulated_event(app.cfg.reference, app.cfg.severity))
    assert len(tui_app.pushed) == 1
    data, severity = tui_app.pushed[0]
    assert data.magnitude == "M 6.1"
    assert severity == "critical"


def test_wire_tui_binds_controller_and_supervisor():
    from vigia_eew.supervisor import Supervisor

    app = _app()
    tui_app = _FakeTuiApp()
    ctrl = app._wire_tui(tui_app)
    assert tui_app.bound_controller is ctrl
    assert isinstance(tui_app.bound_supervisor, Supervisor)
    assert tui_app.bound_supervisor.names == [
        "ws",
        "rest",
        "funvisis",
        "geofon",
        "pipeline",
        "history",
    ]


def test_controller_for_tui_binds_controller_without_supervisor():
    app = _app()
    tui_app = _FakeTuiApp()
    ctrl = app.wiring.build_tui_controller(tui_app, on_acknowledge=lambda _ev: None)
    assert tui_app.bound_controller is ctrl
    assert tui_app.bound_supervisor is None  # simulate mode: no ingestion


def test_inject_simulated_alert_pushes_event():
    app = _app()
    tui_app = _FakeTuiApp()
    app._ctrl = app.wiring.build_tui_controller(tui_app, on_acknowledge=lambda _ev: None)
    app._inject_simulated_alert()
    assert len(tui_app.pushed) == 1
    data, severity = tui_app.pushed[0]
    assert data.magnitude == "M 6.1"
    assert severity == "critical"


# --- Country notification filter wiring (RF-37) ---


def _country_event(lat, lon, distance_km=50.0):
    from datetime import UTC, datetime

    from vigia_eew.models import SeismicEvent

    return SeismicEvent(
        id="c",
        source="USGS",
        magnitude=6.0,
        mag_type="mb",
        lat=lat,
        lon=lon,
        depth_km=10.0,
        time_utc=datetime(2026, 6, 28, tzinfo=UTC),
        distance_km=distance_km,
        severity="critical",
    )


def test_resolve_user_country_uses_config_override():
    app = _app(filter=Filter(country_filter=True, country="ve"))
    assert app.wiring.resolve_user_country() == "VE"


def test_resolve_user_country_auto_from_reference_point():
    app = _app(
        reference=ReferencePoint(name="Caracas", lat=10.48, lon=-66.90),
        filter=Filter(country_filter=True, country="auto"),
    )
    assert app.wiring.resolve_user_country() == "VE"


def test_build_geo_filter_disabled_keeps_other_country():
    # today_only=False: these fixtures use a fixed 2026-06-28 date, unrelated to the
    # freshness filter (RF-40), which has its own dedicated tests in test_filter.py.
    app = _app(filter=Filter(country_filter=False, today_only=False))
    geo = app.wiring.build_geo_filter()
    assert geo.accepts(_country_event(4.71, -74.07)) is True  # Bogotá, kept (filter off)


def test_build_geo_filter_enabled_drops_other_country():
    app = _app(
        reference=ReferencePoint(name="Caracas", lat=10.48, lon=-66.90),
        filter=Filter(country_filter=True, country="auto", radius_km=2000, today_only=False),
    )
    geo = app.wiring.build_geo_filter()
    assert geo.accepts(_country_event(4.71, -74.07)) is False  # Bogotá (CO) dropped
    assert geo.accepts(_country_event(10.48, -66.90)) is True  # Caracas (VE) kept
    assert geo.accepts(_country_event(12.0, -64.0)) is True  # offshore VE -> kept


def test_build_geo_filter_inactive_when_country_unresolved():
    # country="auto" but reference is mid-ocean -> no country -> fail-safe (inert).
    app = _app(
        reference=ReferencePoint(name="Ocean", lat=0.0, lon=-30.0),
        filter=Filter(country_filter=True, country="auto", today_only=False),
    )
    geo = app.wiring.build_geo_filter()
    assert geo.accepts(_country_event(4.71, -74.07)) is True  # not suppressed


def test_build_geo_filter_wires_configured_timezone():
    # RF-40/RF-41: _build_geo_filter must pass the configured timezone through to
    # GeoFilter so the freshness check uses the user's local day, not UTC.
    app = _app(notification=Notification(timezone="America/Caracas"))
    geo = app.wiring.build_geo_filter()
    assert geo._timezone == "America/Caracas"


# --- T-137 · Opening the configuration panel (REQ-GUI-005) ---


def test_open_panel_schedules_on_the_ui_thread(monkeypatch, tmp_path):
    """Flet's controls belong to the UI loop, and the tray runs on its own thread (ADR-006).

    Building a window straight from the tray's callback is the same mistake
    `_toggle_pause` already avoids -- it works until it does not.
    """
    opened = []
    import vigia_eew.wiring as wiring_mod

    monkeypatch.setattr(
        wiring_mod.Wiring, "open_panel", lambda self, shell, path: opened.append(path)
    )
    app = Application(Settings(), config_path=tmp_path / "config.toml")
    app._shell = _FakeShell()

    app._open_panel()

    assert len(app._shell.after_calls) == 1
    ms, callback = app._shell.after_calls[0]
    assert ms == 0
    callback()
    assert opened == [tmp_path / "config.toml"]


def test_open_panel_does_nothing_without_a_window(tmp_path):
    """No shell means no GUI session; there is nowhere to put a panel."""
    app = Application(Settings(), config_path=tmp_path / "config.toml")

    app._open_panel()  # must not raise


def test_the_tray_is_built_with_both_ways_into_the_configuration(tmp_path):
    app = Application(Settings(), config_path=tmp_path / "config.toml")
    app._shell = _FakeShell()

    icon = app._build_tray()

    texts = [str(i.text) for i in icon._icon.menu if i.text is not None]
    assert any(t.lower().startswith("configuration") for t in texts)
    assert any("edit configuration" in t.lower() for t in texts)


# --- `--settings` · the panel with no agent behind it (REQ-GUI-009) ---


class _Page:
    """Just enough of a Flet page for `FletShell` to wrap."""

    def __init__(self):
        from types import SimpleNamespace

        async def nothing():
            return None

        self.window = SimpleNamespace(
            visible=False,
            prevent_close=False,
            on_event=None,
            to_front=nothing,
            center=nothing,
            destroy=nothing,
        )
        self.controls = []
        self.on_keyboard_event = None
        self.title = ""
        self.padding = None
        self.bgcolor = None
        self.tasks = []

    def update(self):
        pass

    def run_task(self, method):
        self.tasks.append(method)


def _run_with(page):
    """A `run_ui` that runs Flet's `main` against a fake page, on a real loop."""
    import asyncio

    ran = []

    def run_ui(main):
        ran.append(main)
        asyncio.run(main(page))

    return run_ui, ran


def test_open_settings_runs_the_panel_on_its_own_window(monkeypatch, tmp_path):
    """No ingestion, no tray, no bridge: one window showing the panel."""
    import vigia_eew.wiring as wiring_mod

    opened = []
    monkeypatch.setattr(
        wiring_mod.Wiring, "open_panel", lambda self, shell, path: opened.append(shell)
    )
    page = _Page()
    run_ui, ran = _run_with(page)
    app = Application(Settings(), config_path=tmp_path / "config.toml", run_ui=run_ui)

    app.open_settings()

    assert len(ran) == 1
    assert opened == [app._shell]
    assert app._shell.standalone is True  # closing the panel ends the run
    assert app._tray_icon is None


def test_closing_the_panel_ends_the_process(tmp_path):
    """Closing the only screen has to end the run, or the process outlives its UI."""
    page = _Page()
    run_ui, _ = _run_with(page)
    app = Application(Settings(), config_path=tmp_path / "config.toml", run_ui=run_ui)
    app.open_settings()
    assert app._shell.screen_key == "panel"

    page.window.on_event(type("E", (), {"type": "close"})())

    assert app._shell.screen_key is None
    assert page.window.prevent_close is False  # the window is being destroyed


def test_simulate_shows_the_alert_and_ends_once_acknowledged(tmp_path):
    page = _Page()
    run_ui, _ = _run_with(page)
    app = Application(Settings(), config_path=tmp_path / "config.toml", run_ui=run_ui)

    app.simulate()

    assert app._shell.alert_view is not None
    assert app._ctrl is not None and app._ctrl.alert_queue.current is not None
    page.on_keyboard_event(type("K", (), {"key": "Enter"})())  # ENTER, as a user would
    assert app._ctrl.alert_queue.current is None
    assert app._shell.alert_view is None
    assert page.window.prevent_close is False  # standalone: nothing left, so it ends


def test_the_suite_cannot_start_the_real_client(tmp_path):
    """The autouse guard: a mode run without `run_ui` fails loudly, not on screen."""
    import pytest

    app = Application(Settings(), config_path=tmp_path / "config.toml")
    with pytest.raises(RuntimeError, match="must not start the Flet client"):
        app.open_settings()


# --- T-151 · About, from the tray and from the panel (REQ-GUI-010) ---


def test_open_about_schedules_on_the_ui_thread(monkeypatch, tmp_path):
    """Same thread rule as the panel: the tray callback runs on its own thread."""
    opened = []
    import vigia_eew.wiring as wiring_mod

    monkeypatch.setattr(wiring_mod.Wiring, "open_about", lambda self, shell: opened.append(shell))
    app = Application(Settings(), config_path=tmp_path / "config.toml")
    app._shell = _FakeShell()

    app._open_about()

    ms, callback = app._shell.after_calls[0]
    assert ms == 0
    callback()
    assert opened == [app._shell]


def test_the_tray_is_built_with_the_about_entry(tmp_path):
    app = Application(Settings(), config_path=tmp_path / "config.toml")
    app._shell = _FakeShell()
    captured = {}

    def fake_build_tray(**kwargs):
        captured.update(kwargs)
        return None

    app.wiring.build_tray = fake_build_tray  # type: ignore[method-assign]
    app._build_tray()

    assert callable(captured["open_about"])
