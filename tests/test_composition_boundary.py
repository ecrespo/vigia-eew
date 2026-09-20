"""Tests for the split between composition and orchestration (REQ-ING-009, HU-104).

`app.py` was the composition root and a god-module at once: it imported 22 of
the project's modules while the next highest fan-out in the tree was 5. Every
feature since v0.1.0 had to pass through it, which made it the one seam the
whole system was forced through -- architecture evaluation P1-1.

The problem was never its size. It was that assembling dependencies and
running the agent were the same file, so neither could be read or changed
without the other.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "vigia_eew"

#: The evaluation's target. Not a round number: the second-highest fan-out in
#: the tree was 5, so 8 leaves the composition root room to be a composition
#: root without letting it go back to being everything else as well.
MAX_APP_FAN_OUT = 8


def _internal_imports(module: Path) -> set[str]:
    """Project modules `module` imports, however the import is spelled."""
    text = module.read_text()
    found = set(re.findall(r"^from vigia_eew\.([a-z_0-9.]+) import", text, re.M))
    for line in re.findall(r"^from vigia_eew import (.+)$", text, re.M):
        found.update(name.strip() for name in line.split(","))
    return found


def test_the_application_module_is_no_longer_a_god_module() -> None:
    """CA-104.4: outgoing coupling of the application module is at most 8."""
    imports = _internal_imports(SRC / "app.py")
    assert len(imports) <= MAX_APP_FAN_OUT, sorted(imports)


def test_dependency_construction_lives_in_its_own_module() -> None:
    """CA-104.4: there is a wiring module, and it is the one doing the building."""
    wiring = SRC / "wiring.py"
    assert wiring.is_file()
    assert len(_internal_imports(wiring)) > MAX_APP_FAN_OUT, (
        "if wiring imports less than app used to, the assembly did not move"
    )


def test_the_application_module_is_readable_in_one_sitting() -> None:
    """Under 300 lines: orchestration only, with the assembly elsewhere."""
    lines = len((SRC / "app.py").read_text().splitlines())
    assert lines < 300, f"app.py is {lines} lines"


def test_the_application_no_longer_builds_the_pipeline_itself() -> None:
    """The two run modes used to assemble an identical Processor each.

    Duplicated assembly is how the TUI and Tk paths drift apart: a filter
    added to one and forgotten in the other is invisible until somebody is
    not warned.
    """
    app = (SRC / "app.py").read_text()
    for built in ("Normalizer(", "Deduplicator(", "Processor(", "GeoFilter("):
        assert built not in app, f"{built} is still constructed in app.py"
