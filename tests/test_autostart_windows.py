"""Tests for autostart via scheduled task on Windows (RF-22, RF-23)."""

from __future__ import annotations

from vigia_eew.autostart.windows_task import (
    TASK_NAME,
    SchtasksInstaller,
    create_command,
    delete_command,
)


class _FakeSchtasks:
    """Fake runner that simulates the scheduled task's state."""

    def __init__(self):
        self.cmds: list[list[str]] = []
        self.exists = False

    def __call__(self, cmd):
        self.cmds.append(cmd)
        if "/create" in cmd:
            self.exists = True
            return 0
        if "/delete" in cmd:
            self.exists = False
            return 0
        if "/query" in cmd:
            return 0 if self.exists else 1
        return 0


def _installer(runner):
    return SchtasksInstaller(exec_cmd='"C:\\Py\\pythonw.exe" -m vigia_eew.cli', runner=runner)


# --- Command generation (pure) ---


def test_create_command_onlogon():
    cmd = create_command("VigiaEEW", "exe")
    assert cmd[:2] == ["schtasks", "/create"]
    assert "/tn" in cmd and "VigiaEEW" in cmd
    assert "/tr" in cmd and "exe" in cmd
    assert cmd[cmd.index("/sc") + 1] == "onlogon"


def test_delete_command():
    cmd = delete_command("VigiaEEW")
    assert cmd[:2] == ["schtasks", "/delete"]
    assert "VigiaEEW" in cmd and "/f" in cmd


# --- Install / uninstall ---


def test_install_creates_task():
    runner = _FakeSchtasks()
    inst = _installer(runner)
    inst.install()
    assert any("/create" in c for c in runner.cmds)
    assert inst.is_installed() is True


def test_uninstall_deletes_task():
    runner = _FakeSchtasks()
    inst = _installer(runner)
    inst.install()
    inst.uninstall()
    assert any("/delete" in c for c in runner.cmds)
    assert inst.is_installed() is False


def test_uses_default_task_name():
    runner = _FakeSchtasks()
    SchtasksInstaller(exec_cmd="x", runner=runner).install()
    assert TASK_NAME in runner.cmds[0]
