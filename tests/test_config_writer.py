"""Tests for the configuration writer (T-135, REQ-CFG-009..012, HU-108).

Every assertion here runs against a **real file on disk**, on purpose.
Atomicity is a filesystem operation: a fake that records "replace was called"
would pass while leaving an orphan temp file on the user's machine, which is
precisely the failure CA-108.6 exists to catch.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from vigia_eew.config import bundled_example, load_config
from vigia_eew.config_writer import (
    ConfigWriter,
    ExternalEdit,
    InvalidConfig,
    fingerprint_of,
)


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """A real `config.toml`, seeded from the template the product ships."""
    path = tmp_path / "config.toml"
    path.write_text(bundled_example(), encoding="utf-8")
    return path


#: The shipped template's comment lines. CA-108.5 cites 46, measured on
#: `c3a2c29`; documenting the fields v1.0 added -- network priority, and the
#: history retention of F6 -- moved the figure, which is the point of writing
#: them. What the criterion actually demands is that a save preserve them, and
#: that is asserted by comparing before with after. The literal stays so the
#: template losing its documentation is a failure rather than a smaller number.
TEMPLATE_COMMENT_LINES = 66


def _comment_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("#")]


# --- CA-108.5 · Saving preserves the documentation -----------------------------


def test_saving_one_field_keeps_every_comment(config_file: Path) -> None:
    """The 46 comment lines are the user's in-line help; a save must not cost them."""
    before = _comment_lines(config_file)
    assert len(before) == TEMPLATE_COMMENT_LINES, "the shipped template lost documentation"

    writer = ConfigWriter(config_file)
    writer.load()
    writer.save({"filter.radius_km": 150.0})

    assert _comment_lines(config_file) == before


def test_saving_one_field_changes_only_that_line(config_file: Path) -> None:
    """Everything else is identical line for line -- sections keep their order too."""
    before = config_file.read_text(encoding="utf-8").splitlines()

    writer = ConfigWriter(config_file)
    writer.load()
    writer.save({"filter.radius_km": 150.0})

    after = config_file.read_text(encoding="utf-8").splitlines()
    differing = [(b, a) for b, a in zip(before, after, strict=True) if b != a]
    assert differing == [("radius_km = 300.0", "radius_km = 150.0")]


def test_the_saved_file_loads_back_with_the_new_value(config_file: Path) -> None:
    """The point of the exercise: the agent reads what the panel wrote."""
    writer = ConfigWriter(config_file)
    writer.load()
    writer.save({"filter.radius_km": 150.0, "notification.language": "es"})

    reloaded = load_config(config_file)
    assert reloaded.filter.radius_km == 150.0
    assert reloaded.notification.language == "es"


def test_a_key_absent_from_the_file_is_added_to_its_section(config_file: Path) -> None:
    """A `config.toml` written before the key existed must still be writable.

    This is the shape of every file an older version wrote: the table is
    there, the key is not. Adding it may not disturb the comments above it.
    """
    without_key = "\n".join(
        line
        for line in config_file.read_text(encoding="utf-8").splitlines()
        if line != "today_only = true"
    )
    config_file.write_text(without_key + "\n", encoding="utf-8")
    before = _comment_lines(config_file)

    writer = ConfigWriter(config_file)
    writer.load()
    writer.save({"filter.today_only": False})

    assert load_config(config_file).filter.today_only is False
    assert _comment_lines(config_file) == before


def test_a_missing_section_is_created(config_file: Path) -> None:
    """`[reference]` ships commented out; setting it must create the real table."""
    writer = ConfigWriter(config_file)
    writer.load()
    writer.save({"reference.name": "Valencia", "reference.lat": 10.16, "reference.lon": -68.0})

    reloaded = load_config(config_file)
    assert reloaded.reference.name == "Valencia"
    assert reloaded.reference.lat == 10.16


def test_writing_with_no_file_yet_starts_from_the_template(tmp_path: Path) -> None:
    """On a fresh install the panel writes the documented file, not a stub."""
    path = tmp_path / "nested" / "config.toml"
    writer = ConfigWriter(path)
    writer.load()
    writer.save({"filter.min_magnitude": 3.5})

    assert len(_comment_lines(path)) == TEMPLATE_COMMENT_LINES
    assert load_config(path).filter.min_magnitude == 3.5


# --- CA-108.6 · Atomic write with a recoverable backup -------------------------


def test_the_previous_version_is_kept_as_a_backup(config_file: Path) -> None:
    original = config_file.read_text(encoding="utf-8")

    writer = ConfigWriter(config_file)
    writer.load()
    writer.save({"filter.radius_km": 150.0})

    backup = config_file.with_suffix(config_file.suffix + ".bak")
    assert backup.read_text(encoding="utf-8") == original


def test_an_interrupted_save_leaves_the_original_intact(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CA-108.6: the original survives, and no temp file is left behind."""
    original = config_file.read_text(encoding="utf-8")

    def boom(*_args: object, **_kw: object) -> None:
        raise OSError("interrupted")

    monkeypatch.setattr(os, "replace", boom)

    writer = ConfigWriter(config_file)
    writer.load()
    with pytest.raises(OSError):
        writer.save({"filter.radius_km": 150.0})

    assert config_file.read_text(encoding="utf-8") == original
    leftovers = [p.name for p in config_file.parent.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


# --- CA-108.7 · An external edit is not overwritten in silence -----------------


def test_an_external_edit_is_refused_instead_of_overwritten(config_file: Path) -> None:
    writer = ConfigWriter(config_file)
    writer.load()

    edited = config_file.read_text(encoding="utf-8").replace(
        "radius_km = 300.0", "radius_km = 42.0"
    )
    config_file.write_text(edited, encoding="utf-8")
    os.utime(config_file, ns=(0, 0))  # a different mtime, whatever the clock resolution

    with pytest.raises(ExternalEdit) as failure:
        writer.save({"filter.min_magnitude": 3.0})

    assert str(config_file) in str(failure.value)
    assert config_file.read_text(encoding="utf-8") == edited


def test_reloading_clears_the_conflict(config_file: Path) -> None:
    """The user's way out is to reload; refusing forever would be a dead end."""
    writer = ConfigWriter(config_file)
    writer.load()
    config_file.write_text(
        config_file.read_text(encoding="utf-8").replace("radius_km = 300.0", "radius_km = 42.0"),
        encoding="utf-8",
    )
    os.utime(config_file, ns=(0, 0))

    writer.load()
    writer.save({"filter.min_magnitude": 3.0})

    assert load_config(config_file).filter.min_magnitude == 3.0


def test_a_file_that_appears_after_loading_is_a_conflict(tmp_path: Path) -> None:
    """Loading "no file" and finding one at save time is the same conflict."""
    path = tmp_path / "config.toml"
    writer = ConfigWriter(path)
    writer.load()
    path.write_text(bundled_example(), encoding="utf-8")

    with pytest.raises(ExternalEdit):
        writer.save({"filter.radius_km": 150.0})


# --- CA-108.8 · An invalid configuration never reaches the disk ----------------


def test_a_cross_field_rule_rejects_the_whole_write(config_file: Path) -> None:
    """`info_max >= warning_max` is the rule that leaves the agent unable to start."""
    original = config_file.read_text(encoding="utf-8")

    writer = ConfigWriter(config_file)
    writer.load()
    with pytest.raises(InvalidConfig) as failure:
        writer.save({"severity.info_max": 6.0})

    assert "severity" in str(failure.value)
    assert config_file.read_text(encoding="utf-8") == original
    assert not config_file.with_suffix(".toml.bak").exists()


def test_a_field_constraint_rejects_the_whole_write(config_file: Path) -> None:
    original = config_file.read_text(encoding="utf-8")

    writer = ConfigWriter(config_file)
    writer.load()
    with pytest.raises(InvalidConfig):
        writer.save({"filter.radius_km": -1.0})

    assert config_file.read_text(encoding="utf-8") == original


def test_an_unknown_field_is_refused_rather_than_written(config_file: Path) -> None:
    """A typo would otherwise land in the file and be ignored by the loader.

    Pydantic drops unknown keys, so the agent would start, behave as if the
    setting were never made, and leave the user's line sitting in the file
    looking effective.
    """
    writer = ConfigWriter(config_file)
    writer.load()
    with pytest.raises(InvalidConfig) as failure:
        writer.save({"filter.radius_kms": 150.0})

    assert "radius_kms" in str(failure.value)


def test_no_change_at_all_still_validates_the_file(config_file: Path) -> None:
    """Saving a file that is already invalid on disk must not "repair" it silently."""
    config_file.write_text(
        config_file.read_text(encoding="utf-8").replace("info_max = 4.0", "info_max = 9.0"),
        encoding="utf-8",
    )
    writer = ConfigWriter(config_file)
    writer.load()
    with pytest.raises(InvalidConfig):
        writer.save({})


# --- The fingerprint itself ----------------------------------------------------


def test_fingerprint_of_a_missing_file_is_none(tmp_path: Path) -> None:
    assert fingerprint_of(tmp_path / "nope.toml") is None


def test_fingerprint_changes_with_the_content(config_file: Path) -> None:
    before = fingerprint_of(config_file)
    config_file.write_text("radius_km = 1.0\n", encoding="utf-8")
    os.utime(config_file, ns=(0, 0))
    assert fingerprint_of(config_file) != before
