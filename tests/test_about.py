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
