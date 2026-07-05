"""Tests for the tray icon (RF-34). Pure logic; does not start the real pystray backend."""

from __future__ import annotations

import os
import subprocess
import sys

from vigia_eew.agent_state import AgentState
from vigia_eew.tray import (
    TrayIcon,
    _open_command,
    build_icon,
    default_icon_path,
    open_config,
)

# --- OS command to open a file (pure) ---


def test_open_command_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    assert _open_command(tmp_path / "config.toml") == ["xdg-open", str(tmp_path / "config.toml")]


def test_open_command_macos(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert _open_command(tmp_path / "config.toml") == ["open", str(tmp_path / "config.toml")]


def test_open_command_windows_uses_startfile(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    assert _open_command(tmp_path / "config.toml") is None


# --- open_config: creates the file if missing and opens it (isolated effect) ---


def test_open_config_creates_file_if_missing(monkeypatch, tmp_path):
    path = tmp_path / "sub" / "config.toml"
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: calls.append((cmd, kw)))
    monkeypatch.setattr(sys, "platform", "linux")

    open_config(path)

    assert path.exists()
    assert calls == [(["xdg-open", str(path)], {"env": None})]  # None = inherit (unfrozen)


def test_open_config_does_not_overwrite_existing_file(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[filter]\nmin_magnitude = 4.0\n", encoding="utf-8")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: None)
    monkeypatch.setattr(sys, "platform", "linux")

    open_config(path)

    assert "min_magnitude" in path.read_text(encoding="utf-8")


def test_open_config_failure_does_not_raise(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"

    def _fail(cmd, **kw):
        raise OSError("no xdg-open available")

    monkeypatch.setattr(subprocess, "Popen", _fail)
    monkeypatch.setattr(sys, "platform", "linux")

    open_config(path)  # must not raise


# --- Icon construction (without starting the real backend) ---


def test_default_icon_path_exists():
    assert default_icon_path().exists()


def test_build_icon_assembles_menu_with_actions():
    state = AgentState()
    calls = {"pause": 0, "config": 0, "exit": 0}
    icon = build_icon(
        state=state,
        paused=lambda: False,
        toggle_pause=lambda: calls.__setitem__("pause", calls["pause"] + 1),
        edit_config=lambda: calls.__setitem__("config", calls["config"] + 1),
        exit=lambda: calls.__setitem__("exit", calls["exit"] + 1),
    )
    items = list(icon.menu)
    texts = [str(i.text) for i in items if i.text is not None]
    assert any("connected" in t.lower() or "reconnecting" in t.lower() for t in texts)
    assert any("pause" in t.lower() for t in texts)
    assert any("edit configuration" in t.lower() for t in texts)
    assert any("quit" in t.lower() for t in texts)

    # Triggering each action invokes the injected callback (without touching real pystray).
    for item in items:
        if item.text and "quit" in str(item.text).lower():
            item(icon)
    assert calls["exit"] == 1


# --- TrayIcon: failure isolation (RF-34) ---


class _FakeIcon:
    def __init__(self, *, run_fails=None):
        self._run_fails = run_fails
        self.stopped = False

    def run(self):
        if self._run_fails is not None:
            raise self._run_fails

    def stop(self):
        self.stopped = True


def test_start_does_not_propagate_backend_failure():
    icon = TrayIcon(_FakeIcon(run_fails=RuntimeError("no display")))
    icon.start()  # must not raise
    icon._thread.join(timeout=2.0)
    assert icon._thread.is_alive() is False


def test_stop_calls_stop_and_waits_for_the_thread():
    fake = _FakeIcon()
    icon = TrayIcon(fake)
    icon.start()
    icon.stop()
    assert fake.stopped is True


# --- Headless import safety (RF-36): the agent must import with no X display ---


def test_app_imports_without_display():
    # pystray connects to its GUI backend at import; importing it lazily keeps
    # `vigia_eew.app` (and `--tui` on a headless server) import-safe without a display.
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    result = subprocess.run(
        [sys.executable, "-c", "import vigia_eew.app"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
