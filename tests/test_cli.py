"""Tests for the CLI (RF-26, RF-21)."""

from __future__ import annotations

import pytest

from vigia_eew.cli import main


class _FakeApp:
    created: list[_FakeApp] = []

    def __init__(self, cfg, *, manual_reference=True, config_path=None):
        self.cfg = cfg
        self.manual_reference = manual_reference
        self.config_path = config_path
        self.simulated = False
        self.executed = False
        self.tui_simulate: bool | None = None
        _FakeApp.created.append(self)

    def simulate(self):
        self.simulated = True

    def execute(self):
        self.executed = True

    def run_tui(self, *, simulate=False):
        self.tui_simulate = simulate


def _create(cfg, **kwargs):
    return _FakeApp(cfg, **kwargs)


def setup_function():
    _FakeApp.created.clear()


@pytest.fixture(autouse=True)
def _no_real_seed(monkeypatch):
    """Record seeding calls and keep them off the real user config dir."""
    calls: list = []

    def fake_seed(path=None, **kwargs):
        calls.append(path)
        return None

    monkeypatch.setattr("vigia_eew.config.seed_config_if_missing", fake_seed)
    return calls


def test_simulate_invokes_simulate():
    rc = main(["--simulate"], create_app=_create)
    assert rc == 0
    assert _FakeApp.created[-1].simulated is True


def test_run_by_default_invokes_execute():
    rc = main([], create_app=_create)
    assert rc == 0
    assert _FakeApp.created[-1].executed is True


def test_tui_invokes_run_tui():
    rc = main(["--tui"], create_app=_create)
    assert rc == 0
    app = _FakeApp.created[-1]
    assert app.tui_simulate is False
    assert app.executed is False


def test_tui_with_simulate_invokes_run_tui_simulate():
    rc = main(["--tui", "--simulate"], create_app=_create)
    assert rc == 0
    app = _FakeApp.created[-1]
    assert app.tui_simulate is True
    assert app.simulated is False  # goes to run_tui, not the Tk simulate()


def test_check_config_does_not_create_app(capsys):
    rc = main(["--check-config"], create_app=_create)
    assert rc == 0
    assert _FakeApp.created == []  # check-config does not start the agent
    assert "Config OK" in capsys.readouterr().out


def test_nonexistent_config_fails():
    with pytest.raises(FileNotFoundError):
        main(["--config", "/path/that/does/not/exist.toml"], create_app=_create)


def test_without_config_reference_is_not_manual():
    # No --config and no user config.toml in this test environment -> not manual.
    rc = main([], create_app=_create)
    assert rc == 0
    assert _FakeApp.created[-1].manual_reference is False


def test_config_with_reference_is_manual(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[reference]\nname = "Test"\nlat = 1.0\nlon = 2.0\n', encoding="utf-8")
    rc = main(["--config", str(path)], create_app=_create)
    assert rc == 0
    assert _FakeApp.created[-1].manual_reference is True


def test_config_path_propagates_to_app(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[reference]\nname = "Test"\nlat = 1.0\nlon = 2.0\n', encoding="utf-8")
    rc = main(["--config", str(path)], create_app=_create)
    assert rc == 0
    assert _FakeApp.created[-1].config_path == str(path)


def test_seeds_default_config_when_no_config_flag(_no_real_seed):
    rc = main([], create_app=_create)
    assert rc == 0
    assert _no_real_seed == [None]  # seeded once, at the default path


def test_does_not_seed_with_explicit_config(tmp_path, _no_real_seed):
    path = tmp_path / "config.toml"
    path.write_text("[filter]\nmin_magnitude = 4.0\n", encoding="utf-8")
    rc = main(["--config", str(path)], create_app=_create)
    assert rc == 0
    assert _no_real_seed == []  # explicit --config is never auto-created


def test_check_config_does_not_seed(_no_real_seed):
    rc = main(["--check-config"], create_app=_create)
    assert rc == 0
    assert _no_real_seed == []  # read-only validation seeds nothing


def test_version_exits_cleanly():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


class _FakeInstaller:
    def __init__(self):
        self.installed = False
        self.uninstalled = False

    def install(self):
        self.installed = True

    def uninstall(self):
        self.uninstalled = True


def test_install_autostart_invokes_install(capsys):
    inst = _FakeInstaller()
    rc = main(["--install-autostart"], create_app=_create, create_installer=lambda: inst)
    assert rc == 0
    assert inst.installed is True
    assert _FakeApp.created == []  # does not start the agent


def test_uninstall_autostart_invokes_uninstall():
    inst = _FakeInstaller()
    rc = main(["--uninstall-autostart"], create_app=_create, create_installer=lambda: inst)
    assert rc == 0
    assert inst.uninstalled is True
    assert _FakeApp.created == []
