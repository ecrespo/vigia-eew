"""Tests for the About window's content (T-151).

The window is a widget tree and needs a display; what it *says* is neither.
Version, copyright, licence and the warranty notice are facts about the
build, and a build that states the wrong licence is a legal problem, not a
cosmetic one -- so they are decided here, where they can be checked.
"""

from __future__ import annotations

from vigia_eew import __version__
from vigia_eew.notify.about import LICENSE_SPDX, PROJECT_URL, about_info


def test_it_reports_the_version_the_package_declares():
    """Typed from memory into a label, this is wrong one release later."""
    assert about_info().version == __version__


def test_it_carries_the_licence_and_the_warranty_notice():
    """The GPL asks an interactive program to say both; saying neither is the bug."""
    info = about_info(locale_code="en")
    assert info.license == LICENSE_SPDX
    assert "no warranty" in info.warranty.lower()


def test_it_speaks_the_language_the_agent_was_told_to_speak():
    assert "garantía" in about_info(locale_code="es").warranty.lower()
    assert "sísmica" in about_info(locale_code="es").description.lower()


def test_the_copyright_names_a_holder_and_a_year():
    line = about_info().copyright
    assert "Ernesto Crespo" in line
    assert any(character.isdigit() for character in line)


def test_it_points_at_the_project():
    assert about_info().url == PROJECT_URL
    assert PROJECT_URL.startswith("https://")


def test_the_fields_are_ordered_for_display():
    """The window renders `rows()` in order; the name leads, the link closes."""
    rows = about_info(locale_code="en").rows()
    assert rows[0][1] == "Vigía-eew"
    assert rows[-1][1] == PROJECT_URL
    assert all(isinstance(label, str) and isinstance(value, str) for label, value in rows)


# --- T-180 · the last drill on the About screen (CA-120.3, CA-120.4) ---------------


def _drill_row(**kwargs) -> str:
    rows = dict(about_info(locale_code="en", zone="UTC", **kwargs).rows())
    return rows["Last drill"]


def test_with_no_drill_yet_it_says_so():
    assert _drill_row() == "none yet"


def test_a_drill_that_was_acknowledged_says_when_and_that_it_was():
    from datetime import UTC, datetime

    from vigia_eew.models import LastDrill

    drill = LastDrill(
        presented_at=datetime(2026, 12, 1, 14, 0, 3, tzinfo=UTC),
        acknowledged_at=datetime(2026, 12, 1, 14, 0, 41, tzinfo=UTC),
    )

    assert _drill_row(last_drill=drill) == "2026-12-01 14:00:03 · acknowledged"


def test_a_drill_nobody_acknowledged_says_so():
    from datetime import UTC, datetime

    from vigia_eew.models import LastDrill

    drill = LastDrill(presented_at=datetime(2026, 12, 1, 14, 0, 3, tzinfo=UTC))

    assert _drill_row(last_drill=drill) == "2026-12-01 14:00:03 · not acknowledged"


def test_the_drill_is_dated_in_the_users_zone_and_language():
    from datetime import UTC, datetime

    from vigia_eew.models import LastDrill

    drill = LastDrill(presented_at=datetime(2026, 12, 1, 14, 0, 3, tzinfo=UTC))
    rows = dict(about_info(locale_code="es", zone="America/Caracas", last_drill=drill).rows())

    assert rows["Último simulacro"] == "2026-12-01 10:00:03 · sin reconocer"
