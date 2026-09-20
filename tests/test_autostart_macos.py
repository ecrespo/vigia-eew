"""Tests for autostart via LaunchAgent on macOS (RF-22, RF-23)."""

from __future__ import annotations

import plistlib

from vigia_eew.autostart.macos_launchagent import (
    LABEL,
    LaunchAgentInstaller,
    launchagent_plist,
)


class _Runner:
    def __init__(self):
        self.cmds: list[list[str]] = []

    def __call__(self, cmd):
        self.cmds.append(cmd)
        return 0


def _installer(tmp_path, runner):
    return LaunchAgentInstaller(
        program_args=["/usr/bin/python", "-m", "vigia_eew.cli"],
        agents_dir=tmp_path,
        runner=runner,
    )


def test_plist_contains_label_args_and_runatload():
    data = plistlib.loads(launchagent_plist(["/usr/bin/python", "-m", "vigia_eew.cli"]).encode())
    assert data["Label"] == LABEL
    assert data["ProgramArguments"] == ["/usr/bin/python", "-m", "vigia_eew.cli"]
    assert data["RunAtLoad"] is True
    assert data["KeepAlive"] is True


def test_install_writes_plist_and_loads(tmp_path):
    runner = _Runner()
    inst = _installer(tmp_path, runner)
    inst.install()

    path = tmp_path / f"{LABEL}.plist"
    assert path.exists()
    assert any("load" in c and "-w" in c for c in runner.cmds)


def test_is_installed(tmp_path):
    inst = _installer(tmp_path, _Runner())
    assert inst.is_installed() is False
    inst.install()
    assert inst.is_installed() is True


def test_uninstall_unloads_and_removes(tmp_path):
    runner = _Runner()
    inst = _installer(tmp_path, runner)
    inst.install()
    runner.cmds.clear()

    inst.uninstall()
    assert (tmp_path / f"{LABEL}.plist").exists() is False
    assert any("unload" in c for c in runner.cmds)


def test_uninstall_without_install_is_a_no_op(tmp_path):
    """Uninstalling what was never installed leaves nothing behind and asks launchd nothing.

    "Does not raise" was the old assertion, and an empty `uninstall()` passed
    it just as well.
    """
    runner = _Runner()
    installer = _installer(tmp_path, runner)

    installer.uninstall()

    assert not installer.path.exists()
    # launchctl is still asked to unload -- unloading something absent is
    # harmless and is what makes the uninstall idempotent.
    assert runner.cmds == [["launchctl", "unload", "-w", str(installer.path)]]
