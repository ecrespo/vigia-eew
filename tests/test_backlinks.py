"""Tests that the code's links to its decisions resolve (REQ-OBS-008, CA-103.7).

`lat check` validates the links that run from the intent layer *into* the
code. It scans Python files but does not validate the links written inside
them, so a backlink pointing at a section somebody renamed stays broken and
silent -- verified by breaking one and watching `lat check` pass.

These backlinks are the direction that matters most day to day. Somebody
reading `verdict()` and wondering why the country check rejects rather than
admits should find the answer from where they already are, not by knowing
that `lat.md/` exists.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"

#: The three highest-value places, per HU-103: the deduplication verdict, the
#: filter's acceptance, and the automatic reference resolution.
EXPECTED_BACKLINKS = {
    "src/vigia_eew/pipeline/dedup.py",
    "src/vigia_eew/pipeline/filter.py",
    "src/vigia_eew/geoloc.py",
}


#: Anchored on `lat.md/` so that a nested type annotation -- `list[list[str]]`
#: closes with the same two brackets -- is not mistaken for a wiki link.
_BACKLINK = re.compile(r"\[\[(lat\.md/[^\]]+)\]\]")


def _backlinks() -> list[tuple[Path, str]]:
    found = []
    for module in SRC.rglob("*.py"):
        for link in _BACKLINK.findall(module.read_text()):
            found.append((module, link))
    return found


def _headings(document: Path) -> set[str]:
    return {
        line.lstrip("#").strip()
        for line in document.read_text().splitlines()
        if line.startswith("#")
    }


def test_the_three_decisions_are_linked_from_the_code() -> None:
    """CA-103.7: each of the three points carries its backlink."""
    linked = {str(path.relative_to(REPO_ROOT)) for path, _ in _backlinks()}
    assert EXPECTED_BACKLINKS <= linked


def test_every_backlink_in_the_code_resolves() -> None:
    """CA-103.7: a link to a renamed section fails the gate, like a style error.

    Checked here rather than left to `lat check`, which validates links from
    the intent layer into the code but not the ones written inside it.
    """
    broken = []
    for module, link in _backlinks():
        document, _, anchor = link.partition("#")
        path = REPO_ROOT / f"{document}.md"
        if not path.is_file():
            broken.append(f"{module.name}: no document {document}")
            continue
        section = anchor.split("#")[-1] if anchor else None
        if section and section not in _headings(path):
            broken.append(f"{module.name}: no section {section!r} in {document}")
    assert broken == [], broken
