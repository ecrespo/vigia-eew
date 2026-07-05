"""Configuration tests (RF-24, RF-12)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vigia_eew.config import Settings, has_manual_reference, load_config

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


def test_example_file_is_valid():
    # The repo's config.toml.example must load without errors.
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    example = root / "config.toml.example"
    cfg = load_config(example)
    assert cfg.reference.name == "Caracas"
    assert cfg.notification.timezone == "America/Caracas"


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
