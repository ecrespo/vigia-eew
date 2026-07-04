"""Tests for autostart via systemd --user (RF-22, RF-23)."""

from __future__ import annotations

from vigia_eew.autostart.linux_systemd import SystemdInstaller, systemd_unit


class _Runner:
    def __init__(self):
        self.cmds: list[list[str]] = []

    def __call__(self, cmd):
        self.cmds.append(cmd)
        return 0


def _installer(tmp_path, runner):
    return SystemdInstaller(
        exec_cmd="/usr/bin/python -m vigia_eew.cli",
        unit_dir=tmp_path,
        runner=runner,
    )


# --- Unit generation (pure) ---


def test_unit_contains_execstart_and_wantedby():
    text = systemd_unit("/usr/bin/python -m vigia_eew.cli", description="Vigía")
    assert "ExecStart=/usr/bin/python -m vigia_eew.cli" in text
    assert "WantedBy=default.target" in text
    assert "Restart=on-failure" in text
    assert "Description=Vigía" in text


# --- Install / uninstall ---


def test_install_writes_unit_and_enables(tmp_path):
    runner = _Runner()
    inst = _installer(tmp_path, runner)
    inst.install()

    path = tmp_path / "vigia-eew.service"
    assert path.exists()
    assert "ExecStart=" in path.read_text(encoding="utf-8")
    # daemon-reload + enable --now
    assert ["systemctl", "--user", "daemon-reload"] in runner.cmds
    assert any("enable" in c and "--now" in c for c in runner.cmds)


def test_is_installed(tmp_path):
    inst = _installer(tmp_path, _Runner())
    assert inst.is_installed() is False
    inst.install()
    assert inst.is_installed() is True


def test_uninstall_removes_unit_and_disables(tmp_path):
    runner = _Runner()
    inst = _installer(tmp_path, runner)
    inst.install()
    runner.cmds.clear()

    inst.uninstall()
    assert (tmp_path / "vigia-eew.service").exists() is False
    assert any("disable" in c and "--now" in c for c in runner.cmds)


def test_uninstall_without_install_does_not_fail(tmp_path):
    inst = _installer(tmp_path, _Runner())
    inst.uninstall()  # must not raise even if the unit doesn't exist
    assert inst.is_installed() is False
