"""Tests for the autostart facade (RF-22, RF-23, RF-26)."""

from __future__ import annotations

import sys

import pytest

from vigia_eew.autostart import agent_command, create_installer
from vigia_eew.autostart.linux_systemd import SystemdInstaller
from vigia_eew.autostart.macos_launchagent import LaunchAgentInstaller
from vigia_eew.autostart.windows_task import SchtasksInstaller


def test_agent_command_points_to_cli():
    cmd = agent_command()
    assert cmd[-2:] == ["-m", "vigia_eew.cli"]
    assert "python" in cmd[0].lower()


def test_agent_command_frozen_uses_only_the_executable(monkeypatch):
    # Packaged with PyInstaller (RF-28..RF-30): the binary itself is already the
    # agent, not an interpreter that accepts `-m`.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    cmd = agent_command()
    assert cmd == [sys.executable]


def test_create_installer_linux():
    assert isinstance(create_installer("linux"), SystemdInstaller)


def test_create_installer_macos():
    assert isinstance(create_installer("darwin"), LaunchAgentInstaller)


def test_create_installer_windows():
    assert isinstance(create_installer("win32"), SchtasksInstaller)


def test_create_installer_default_uses_current_platform():
    # Must not raise on the platform running the tests (Linux/macOS/Windows).
    inst = create_installer()
    assert hasattr(inst, "install") and hasattr(inst, "uninstall")
    assert sys.platform in ("linux", "darwin", "win32")


def test_unsupported_os_fails_clearly():
    with pytest.raises(NotImplementedError):
        create_installer("sunos5")
