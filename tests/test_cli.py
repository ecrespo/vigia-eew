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
        self.settings_opened = False
        self.history_opened = False
        _FakeApp.created.append(self)

    def simulate(self):
        self.simulated = True

    def execute(self):
        self.executed = True

    def run_tui(self, *, simulate=False):
        self.tui_simulate = simulate

    def open_settings(self):
        self.settings_opened = True

    def open_history(self):
        self.history_opened = True


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
    assert app.simulated is False  # goes to run_tui, not the Flet simulate()


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


# --- Opening the configuration panel on its own (`--settings`) ---


def test_settings_opens_the_panel_without_starting_the_agent():
    """The panel is a mode of its own, not a side effect of a running agent.

    On a GNOME/Wayland session pystray falls back to its X11 tray, which draws
    the icon and never opens a menu: the tray entry that leads to the panel is
    then unreachable, and this flag is what the desktop entry runs instead.
    """
    rc = main(["--settings"], create_app=_create)
    assert rc == 0
    app = _FakeApp.created[-1]
    assert app.settings_opened is True
    assert app.executed is False
    assert app.simulated is False


def test_settings_seeds_the_config_before_opening_it(_no_real_seed):
    """An empty config dir must still open a panel over a real file (RF-24)."""
    main(["--settings"], create_app=_create)
    assert _no_real_seed == [None]


def test_settings_honours_an_explicit_config_path(tmp_path):
    path = tmp_path / "otro.toml"
    path.write_text('[reference]\nname = "X"\nlat = 1.0\nlon = 2.0\n')
    rc = main(["--settings", "--config", str(path)], create_app=_create)
    assert rc == 0
    assert _FakeApp.created[-1].config_path == str(path)


# --- Opening the history on its own (`--history`, REQ-GUI-011) ---


def test_history_opens_the_history_without_starting_the_agent():
    """CA-113.1: the history is a mode of its own, like the panel.

    The tray menu was the only way in, and on GNOME/Wayland it may not open.
    """
    rc = main(["--history"], create_app=_create)
    assert rc == 0
    app = _FakeApp.created[-1]
    assert app.history_opened is True
    assert app.executed is False
    assert app.simulated is False
    assert app.settings_opened is False


def test_history_wins_over_the_other_modes():
    """Dispatched first: with `--settings` too, the navigation leads to the panel."""
    main(["--history", "--settings", "--simulate"], create_app=_create)
    app = _FakeApp.created[-1]
    assert app.history_opened is True
    assert app.settings_opened is False
    assert app.simulated is False


def test_help_lists_the_history_option(capsys):
    with pytest.raises(SystemExit):
        main(["--help"], create_app=_create)
    assert "--history" in capsys.readouterr().out


# --- Recovering the history (`--backfill DAYS`, REQ-HIS-010, 03 §2) ---------------


def _outcomes(*statuses: str):
    from vigia_eew.backfill import Outcome

    names = ("EMSC", "USGS", "GEOFON")
    made = [
        Outcome(name, status, recovered=3 if status == "recovered" else 0, detail="HTTP 500")
        for name, status in zip(names, statuses, strict=False)
    ]
    return [
        *made,
        Outcome(
            "FUNVISIS",
            "not_recoverable",
            detail="the service offers no query by date",
            reason_key="backfill_no_query_by_date",
        ),
    ]


def test_backfill_recovers_and_prints_one_line_per_network(capsys):
    asked: list = []

    def recover(cfg, days):
        asked.append((cfg.history.recovered_retention_days, days))
        return _outcomes("recovered", "recovered", "failed")

    rc = main(["--backfill", "90"], create_app=_create, recover=recover)

    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert asked == [(365, 90)]
    assert _FakeApp.created == []  # the agent is not started
    assert [line.split()[0] for line in out] == ["EMSC", "USGS", "GEOFON", "FUNVISIS"]
    assert "no query by date" in out[3] or "consulta por fecha" in out[3]


def test_backfill_exits_one_when_every_recoverable_network_failed(capsys):
    rc = main(["--backfill", "30"], recover=lambda cfg, days: _outcomes("failed", "failed"))

    assert rc == 1
    assert len(capsys.readouterr().out.splitlines()) == 3


def test_backfill_refuses_a_period_beyond_the_retention_naming_the_limit(capsys):
    """CA-117.6: exit 2, on standard error, before any request."""
    from vigia_eew.backfill import run

    rc = main(["--backfill", "400"], recover=run)

    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    assert "400" in captured.err and "365" in captured.err
    assert "recovered_retention_days" in captured.err


def test_backfill_needs_a_number_of_days():
    with pytest.raises(SystemExit) as raised:
        main(["--backfill", "soon"])
    assert raised.value.code == 2


def test_backfill_honours_an_explicit_config(tmp_path, capsys):
    path = tmp_path / "config.toml"
    path.write_text("[history]\nrecovered_retention_days = 10\n", encoding="utf-8")

    rc = main(["--config", str(path), "--backfill", "11"], recover=lambda cfg, days: [])

    assert rc == 2
    assert "10" in capsys.readouterr().err


def test_backfill_says_when_the_history_cannot_be_opened(capsys):
    def recover(cfg, days):
        raise OSError("read-only file system")

    rc = main(["--backfill", "30"], recover=recover)

    assert rc == 1
    assert "read-only file system" in capsys.readouterr().err


def test_help_lists_the_backfill_option(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "--backfill" in capsys.readouterr().out


def test_backfill_fills_an_empty_history_that_survives_a_restart(capsys, monkeypatch):
    """T-171's exit: the real recovery, the real file, a fake network."""
    from datetime import UTC, datetime, timedelta

    import vigia_eew.backfill as backfill_module
    from vigia_eew.history import HistoryStore

    when = datetime.now(UTC) - timedelta(days=40)

    class _Resp:
        status_code = 200
        text = ""
        headers: dict = {}

        def __init__(self, features):
            self._features = features

        def json(self):
            return {"features": self._features}

    class _Network:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def get(self, url, *, params=None, timeout=None, headers=None):
            inside = params["starttime"] <= when.strftime("%Y-%m-%dT%H:%M:%S") < params["endtime"]
            if "seismicportal" not in url or not inside:
                resp = _Resp([])
                resp.status_code = 204
                return resp
            properties = {
                "unid": "20261007_0000001",
                "time": when.strftime("%Y-%m-%dT%H:%M:%S.0Z"),
                "lat": 10.6,
                "lon": -66.9,
                "depth": 10.0,
                "mag": 4.4,
                "magtype": "mb",
                "flynn_region": "NEAR COAST OF VENEZUELA",
            }
            return _Resp([{"id": "x", "properties": properties}])

    monkeypatch.setattr(backfill_module.httpx, "AsyncClient", _Network)

    rc = main(["--backfill", "90"])

    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert {line.split()[0] for line in out} == {"EMSC", "USGS", "GEOFON", "FUNVISIS"}
    restarted = HistoryStore().open()  # prunes, as the agent does when it starts
    assert [(row.source, row.verdict) for row in restarted.rows()] == [("EMSC", "recovered")]
    restarted.close()
