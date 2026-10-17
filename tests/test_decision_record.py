"""Tests for the published decision record (T-110, Art. 9).

These assertions are not about behaviour -- they are the machine-checkable
precondition of two later phases. The configuration panel (F5) contradicts
ADR-007 as originally written, and the history store (F6) contradicts the
constitution's "no database" restriction. Neither may be built until the
amendment that permits it is published, and "published" has to mean
something a gate can read.

T-128 turns intent-layer drift into a lint of its own. Until then, this is
the check that the record and the plan have not diverged in silence.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONSTITUTION = REPO_ROOT / "docs" / "sdd" / "specs" / "00-CONSTITUTION.md"
TECHNICAL_DESIGN = REPO_ROOT / "docs" / "TECHNICAL-DESIGN.md"

#: The six rows of docs/v1/00-ENMIENDAS-CONSTITUCION.md, by the article each
#: one amends. E-01 is the one D-3 had to resolve first.
AMENDED_ARTICLES = (
    "Stack · Lenguaje",
    "Stack · Config",
    "Stack · Contenedores",
    "Regla de versiones",
    "Stack · Persistencia",
    "Stack · Destinos de red",
)


def test_the_six_amendments_are_recorded() -> None:
    """Each amendment the v1 kit proposes is in the constitution's register."""
    register = CONSTITUTION.read_text()
    for article in AMENDED_ARTICLES:
        assert article in register, f"amendment to {article!r} not published"


def test_no_amendment_is_left_pending_approval() -> None:
    """An amendment with nobody's name on it has not been decided, only drafted."""
    register = CONSTITUTION.read_text().split("## Enmiendas", 1)[1]
    register = register.split("\n---", 1)[0]
    assert "pendiente" not in register


def test_the_language_floor_matches_its_amendment() -> None:
    """E-01: the article itself says 3.13, not only the register.

    A register that records a change the article contradicts is worse than
    no register: it makes the contradiction look decided.
    """
    stack = CONSTITUTION.read_text()
    assert "≥ 3.13" in stack
    assert "≥ 3.12**" not in stack


def test_the_enabling_adrs_are_published() -> None:
    """ADR-019 unblocks F5, ADR-025 unblocks F6."""
    design = TECHNICAL_DESIGN.read_text()
    assert "ADR-019" in design
    assert "ADR-025" in design


def test_the_superseded_adrs_say_so() -> None:
    """ADR-007 and ADR-010 are marked amended where they are read.

    Whoever opens ADR-007 to learn how configuration works must not find the
    v0.1.0 answer presented as current.
    """
    design = TECHNICAL_DESIGN.read_text()
    adr_007 = design.split("### ADR-007", 1)[1].split("### ADR-008", 1)[0]
    adr_010 = design.split("### ADR-010", 1)[1].split("### ADR-011", 1)[0]
    assert "ADR-019" in adr_007
    assert "Amended" in adr_007
    assert "Amended" in adr_010
