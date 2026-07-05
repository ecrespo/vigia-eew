"""Tests for the application assembly (RF-26, supervisor/notification wiring)."""

from __future__ import annotations

import asyncio

from vigia_eew.app import Application
from vigia_eew.config import EMSCSource, Notification, ReferencePoint, Settings, USGSSource
from vigia_eew.simulation import simulated_event
from vigia_eew.state import StateStore
from vigia_eew.tray import TrayIcon


class _FakeWindow:
    def refresh(self, data):
        pass


class _FakeRoot:
    def __init__(self):
        self.after_calls: list[tuple[int, object]] = []

    def after(self, ms, callback):
        self.after_calls.append((ms, callback))

    def quit(self):
        pass


def _app(**cfg_kw) -> Application:
    return Application(Settings(**cfg_kw))


# --- Supervisor wiring based on enabled sources ---


def test_supervisor_with_both_sources():
    app = _app()
    sup = app._build_supervisor(asyncio.Queue(), object())
    assert sup.names == ["ws", "rest", "pipeline"]


def test_supervisor_without_emsc():
    app = _app(sources_emsc=EMSCSource(enabled=False))
    sup = app._build_supervisor(asyncio.Queue(), object())
    assert sup.names == ["rest", "pipeline"]


def test_supervisor_without_usgs():
    app = _app(sources_usgs=USGSSource(enabled=False))
    sup = app._build_supervisor(asyncio.Queue(), object())
    assert sup.names == ["ws", "pipeline"]


# --- Notification controller built by the app ---


def test_controller_formats_and_shows():
    app = _app()
    seen: list = []
    ctrl = app._build_controller(
        lambda data, severity, on_acknowledge: seen.append((data, severity)) or _FakeWindow(),
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


def test_toggle_pause_schedules_on_tk_thread():
    app = _app()
    app._root = _FakeRoot()
    ctrl = app._build_controller(lambda data, severity, on_acknowledge: _FakeWindow())
    assert ctrl.paused is False

    app._toggle_pause()
    assert len(app._root.after_calls) == 1
    ms, callback = app._root.after_calls[0]
    assert ms == 0
    callback()  # runs the scheduled callback, like Tk's real mainloop would
    assert ctrl.paused is True


def test_exit_from_tray_schedules_quit():
    app = _app()
    app._root = _FakeRoot()
    app._exit_from_tray()
    assert len(app._root.after_calls) == 1
    ms, callback = app._root.after_calls[0]
    assert ms == 0
    assert callable(callback)


def test_edit_config_uses_explicit_path(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"
    calls = []
    import vigia_eew.app as app_mod

    monkeypatch.setattr(app_mod.tray, "open_config", lambda r: calls.append(r))
    app = Application(Settings(), config_path=path)
    app._edit_config()
    assert calls == [path]


def test_edit_config_uses_default_path_without_explicit_config(monkeypatch):
    calls = []
    import vigia_eew.app as app_mod

    monkeypatch.setattr(app_mod.tray, "open_config", lambda r: calls.append(r))
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
    assert tui_app.bound_supervisor.names == ["ws", "rest", "pipeline"]


def test_controller_for_tui_binds_controller_without_supervisor():
    app = _app()
    tui_app = _FakeTuiApp()
    ctrl = app._controller_for_tui(tui_app)
    assert tui_app.bound_controller is ctrl
    assert tui_app.bound_supervisor is None  # simulate mode: no ingestion


def test_inject_simulated_alert_pushes_event():
    app = _app()
    tui_app = _FakeTuiApp()
    app._controller_for_tui(tui_app)
    app._inject_simulated_alert()
    assert len(tui_app.pushed) == 1
    data, severity = tui_app.pushed[0]
    assert data.magnitude == "M 6.1"
    assert severity == "critical"
