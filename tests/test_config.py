"""Configuration tests (RF-24, RF-12)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vigia_eew import config as config_module
from vigia_eew.config import (
    Settings,
    bundled_example,
    has_manual_reference,
    load_config,
    seed_config_if_missing,
)

CONFIG_EXAMPLE = """
[reference]
name = "Valencia"
lat = 10.1620
lon = -68.0077

[filter]
radius_km = 150.0
min_magnitude = 3.0

[sources.emsc]
ping_interval_s = 10

[sources.usgs]
poll_interval_s = 30

[severity]
info_max = 3.5
warning_max = 5.0
"""


def test_defaults_without_file(tmp_path):
    # None path and no user file -> defaults (Caracas).
    cfg = Settings()
    assert cfg.reference.name == "Caracas"
    assert cfg.filter.radius_km == 300.0
    assert cfg.sources_emsc.ping_interval_s == 15
    assert cfg.notification.tray_icon is True
    # Country filter is opt-in, off by default (RF-37).
    assert cfg.filter.country_filter is False
    assert cfg.filter.country == "auto"
    # Freshness filter is on by default (RF-40).
    assert cfg.filter.today_only is True


def test_funvisis_source_defaults():
    cfg = Settings()
    assert cfg.sources_funvisis.enabled is True  # Venezuela-only, on by default
    assert "funvisis" in cfg.sources_funvisis.url
    assert cfg.sources_funvisis.url.startswith("http://")  # no valid HTTPS available
    assert cfg.sources_funvisis.poll_interval_s == 60


def test_funvisis_source_loaded_from_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        "[sources.funvisis]\nenabled = false\npoll_interval_s = 120\n", encoding="utf-8"
    )
    cfg = load_config(path)
    assert cfg.sources_funvisis.enabled is False
    assert cfg.sources_funvisis.poll_interval_s == 120


def test_geofon_source_defaults():
    cfg = Settings()
    assert cfg.sources_geofon.enabled is True  # independent global source, on by default
    assert "geofon" in cfg.sources_geofon.url
    assert cfg.sources_geofon.poll_interval_s == 60


def test_geofon_source_loaded_from_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[sources.geofon]\nenabled = false\npoll_interval_s = 90\n", encoding="utf-8")
    cfg = load_config(path)
    assert cfg.sources_geofon.enabled is False
    assert cfg.sources_geofon.poll_interval_s == 90


def test_country_filter_loaded_from_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[filter]\ncountry_filter = true\ncountry = "VE"\n', encoding="utf-8")
    cfg = load_config(path)
    assert cfg.filter.country_filter is True
    assert cfg.filter.country == "VE"


def test_today_only_loaded_from_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[filter]\ntoday_only = false\n", encoding="utf-8")
    cfg = load_config(path)
    assert cfg.filter.today_only is False


def test_load_from_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(CONFIG_EXAMPLE, encoding="utf-8")
    cfg = load_config(path)
    assert cfg.reference.name == "Valencia"
    assert cfg.filter.radius_km == 150.0
    # Mapping of nested sections [sources.emsc] / [sources.usgs].
    assert cfg.sources_emsc.ping_interval_s == 10
    assert cfg.sources_usgs.poll_interval_s == 30
    assert cfg.severity.info_max == 3.5


def test_nonexistent_explicit_path_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "does_not_exist.toml")


def test_invalid_severity():
    with pytest.raises(ValidationError):
        Settings(severity={"info_max": 6.0, "warning_max": 5.0})


def test_bundled_example_is_valid_toml(tmp_path):
    # The packaged template must load without errors.
    path = tmp_path / "config.toml"
    path.write_text(bundled_example(), encoding="utf-8")
    cfg = load_config(path)
    assert cfg.notification.timezone == "America/Caracas"


def test_bundled_example_has_reference_commented(tmp_path):
    # [reference] is commented in the template -> IP auto-detection stays on (RF-33).
    path = tmp_path / "config.toml"
    path.write_text(bundled_example(), encoding="utf-8")
    assert has_manual_reference(path) is False


def test_seed_creates_file_and_parent_dir(tmp_path):
    target = tmp_path / "nested" / "config.toml"
    result = seed_config_if_missing(target)
    assert result == target
    assert target.exists()
    # The seeded file is the loadable template with a commented [reference] (RF-33).
    assert has_manual_reference(target) is False


def test_seed_does_not_overwrite_existing(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text("[filter]\nmin_magnitude = 9.0\n", encoding="utf-8")
    result = seed_config_if_missing(target)
    assert result is None
    assert "9.0" in target.read_text(encoding="utf-8")  # user file untouched


def test_seed_uses_default_path_when_none(tmp_path, monkeypatch):
    target = tmp_path / "config.toml"
    monkeypatch.setattr(config_module, "default_config_path", lambda: target)
    result = seed_config_if_missing()
    assert result == target
    assert target.exists()


def test_seed_is_best_effort_on_oserror(tmp_path):
    # Parent is a regular file -> mkdir raises OSError; seeding must not propagate it.
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    result = seed_config_if_missing(blocker / "config.toml")
    assert result is None


def test_has_manual_reference_nonexistent_explicit_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        has_manual_reference(tmp_path / "does_not_exist.toml")


def test_has_manual_reference_with_section(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(CONFIG_EXAMPLE, encoding="utf-8")
    assert has_manual_reference(path) is True


def test_has_manual_reference_without_section(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[filter]\nmin_magnitude = 4.0\n", encoding="utf-8")
    assert has_manual_reference(path) is False


def test_has_manual_reference_no_path_and_no_user_file():
    # No --config and no user config.toml in this test environment -> not manual.
    assert has_manual_reference(None) is False


# --- T-167 · the four keys of the recovery (REQ-HIS-010, REQ-HIS-013, D-5, D-10) ---


def test_the_recovery_has_its_defaults() -> None:
    cfg = Settings()

    assert cfg.sources_emsc.catalog_url == "https://www.seismicportal.eu/fdsnws/event/1/query"
    assert cfg.history.recovered_retention_days == 365
    assert cfg.history.recovery_radius_km == 1000.0
    assert cfg.history.recovery_min_magnitude == 2.5


def test_a_config_written_before_the_recovery_loads_with_the_defaults(tmp_path) -> None:
    """A v1.0 file names none of the four keys and must mean what it meant."""
    path = tmp_path / "config.toml"
    path.write_text(
        '[sources.emsc]\nurl = "wss://example.org/ws"\n\n[history]\nretention_days = 30\n',
        encoding="utf-8",
    )

    cfg = load_config(path)

    assert cfg.sources_emsc.url == "wss://example.org/ws"
    assert cfg.sources_emsc.catalog_url == "https://www.seismicportal.eu/fdsnws/event/1/query"
    assert cfg.history.retention_days == 30
    assert cfg.history.recovered_retention_days == 365


def test_the_recovery_keys_are_read_from_the_file(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[sources.emsc]\ncatalog_url = "https://example.org/fdsnws/event/1/query"\n\n'
        "[history]\nrecovered_retention_days = 30\nrecovery_radius_km = 300\n"
        "recovery_min_magnitude = 4.0\n",
        encoding="utf-8",
    )

    cfg = load_config(path)

    assert cfg.sources_emsc.catalog_url == "https://example.org/fdsnws/event/1/query"
    assert cfg.history.recovered_retention_days == 30
    assert cfg.history.recovery_radius_km == 300.0
    assert cfg.history.recovery_min_magnitude == 4.0


def test_the_two_retentions_are_separate_keys(tmp_path) -> None:
    """CA-117.10: changing either does not change the other."""
    path = tmp_path / "config.toml"
    path.write_text("[history]\nretention_days = 10\n", encoding="utf-8")

    cfg = load_config(path)

    assert (cfg.history.retention_days, cfg.history.recovered_retention_days) == (10, 365)


def test_a_recovery_radius_of_nothing_is_refused(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[history]\nrecovery_radius_km = 0\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_config(path)


def test_the_example_file_declares_the_four_keys() -> None:
    """The example is the documentation most users read."""
    example = bundled_example()

    for key in (
        "catalog_url",
        "recovered_retention_days",
        "recovery_radius_km",
        "recovery_min_magnitude",
    ):
        assert f"\n{key} = " in example, key


# --- T-180 · [drill] (REQ-UX-007) --------------------------------------------------


def test_the_scheduled_drill_is_off_by_default() -> None:
    """CA-120.2: a window nobody asked for is not a good first contact."""
    cfg = load_config()

    assert cfg.drill.enabled is False
    assert cfg.drill.interval_days == 30


def test_the_drill_keys_are_read_from_the_file(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[drill]\nenabled = true\ninterval_days = 7\n", encoding="utf-8")

    cfg = load_config(path)

    assert cfg.drill.enabled is True
    assert cfg.drill.interval_days == 7


def test_an_interval_of_no_days_is_refused(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[drill]\ninterval_days = 0\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_config(path)


def test_the_example_file_documents_the_drill_and_leaves_it_off(tmp_path) -> None:
    text = bundled_example()
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")

    assert "[drill]" in text
    assert load_config(path).drill.enabled is False


def test_the_drill_reaches_the_panel_like_any_other_section() -> None:
    from vigia_eew.notify.config_panel import describe

    sections = {section.key: section for section in describe()}

    assert {field.path for field in sections["drill"].fields} == {
        "drill.enabled",
        "drill.interval_days",
    }
