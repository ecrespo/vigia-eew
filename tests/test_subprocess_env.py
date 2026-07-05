"""Tests for the system-subprocess environment sanitization (PyInstaller onefile).

A PyInstaller onefile bundle injects its extraction dir (`sys._MEIPASS`) into
`LD_LIBRARY_PATH`/`DYLD_LIBRARY_PATH` so the frozen app finds its bundled shared
libraries. That value leaks into subprocesses: a system binary like `systemctl`
then loads the bundle's (older) `libcrypto.so.3` instead of the system's, failing
with a missing versioned symbol. `system_env()` strips that injected path so
spawned system binaries use the OS libraries.
"""

from __future__ import annotations

import sys

from vigia_eew.subprocess_env import system_env


def test_not_frozen_returns_none(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert system_env() is None


def test_frozen_without_orig_removes_ld_library_path(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEIabc123")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    env = system_env()
    assert env is not None
    assert "LD_LIBRARY_PATH" not in env


def test_frozen_with_orig_restores_original_value(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEIabc123")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/local/lib")
    env = system_env()
    assert env is not None
    assert env["LD_LIBRARY_PATH"] == "/usr/local/lib"
    assert "LD_LIBRARY_PATH_ORIG" not in env


def test_frozen_strips_dyld_library_path_on_macos(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/tmp/_MEIabc123")
    monkeypatch.delenv("DYLD_LIBRARY_PATH_ORIG", raising=False)
    env = system_env()
    assert env is not None
    assert "DYLD_LIBRARY_PATH" not in env


def test_frozen_without_lib_vars_returns_environ_copy(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    monkeypatch.delenv("DYLD_LIBRARY_PATH", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin")
    env = system_env()
    assert env is not None
    assert env["PATH"] == "/usr/bin"  # a real copy of the environment


def test_returned_env_is_a_copy_not_os_environ(monkeypatch):
    import os

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    env = system_env()
    assert env is not None
    assert env is not os.environ  # mutating it must not touch the process env


# --- Wiring: the systemd runner (the reported failure) passes the sanitized env ---


def test_systemd_runner_passes_sanitized_env(monkeypatch):
    import vigia_eew.autostart.linux_systemd as mod

    captured: dict = {}

    class _Completed:
        returncode = 0

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")
        return _Completed()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod, "system_env", lambda: {"CLEAN": "1"})

    rc = mod._subprocess_runner(["systemctl", "--user", "daemon-reload"])
    assert rc == 0
    assert captured["cmd"] == ["systemctl", "--user", "daemon-reload"]
    assert captured["env"] == {"CLEAN": "1"}
