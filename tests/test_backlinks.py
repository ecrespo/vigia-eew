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
import subprocess
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


#: Two shapes reach the intent layer from the code, and both have to resolve.
#:
#: The long one is written inside a docstring, where the surrounding prose
#: needs the reader to know which file is meant. It is anchored on `lat.md/`
#: so that a nested type annotation -- `list[list[str]]` closes with the same
#: two brackets -- is not mistaken for a wiki link.
#:
#: The short one is the `@lat` comment above a definition: the tool's own
#: syntax, which takes the document name bare. Both shapes were already in this
#: codebase and only the first was checked here, which is how eight of the
#: eleven comments came to point at sections renamed out from under them.
#: (Spelled without the marker on purpose -- `lat check` scans this file too,
#: and an example in a comment is indistinguishable from a real link.)
_BACKLINK = re.compile(r"\[\[(lat\.md/[^\]]+)\]\]")
_AT_LAT = re.compile(r"#\s*@lat:\s*\[\[([^\]]+)\]\]")


def _backlinks() -> list[tuple[Path, str]]:
    """Every link from the code into the intent layer, in either shape."""
    found = []
    for module in SRC.rglob("*.py"):
        text = module.read_text()
        for link in _BACKLINK.findall(text):
            found.append((module, link))
        for link in _AT_LAT.findall(text):
            # The short form names the document without the folder, so the
            # folder is put back before the link is resolved.
            found.append((module, f"lat.md/{link}"))
    return found


def _headings(document: Path) -> set[str]:
    return {
        line.lstrip("#").strip()
        for line in document.read_text().splitlines()
        if line.startswith("#")
    }


def test_the_intent_layer_ships_with_the_repository() -> None:
    """The layer the backlinks point at has to travel with them.

    `lat.md/` was gitignored, so every check built on it -- these
    assertions and `lat check` in CI -- passed on the machine that had the
    files and had nothing to read anywhere else. Verified by cloning: the
    resolution test below fails in a fresh clone of the ignored tree.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "lat.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert "lat.md/lat.md" in tracked, "the intent layer is not versioned"
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "lat.md/lat.md"], cwd=REPO_ROOT, capture_output=True
    )
    assert ignored.returncode != 0, ".gitignore still excludes the intent layer"


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
