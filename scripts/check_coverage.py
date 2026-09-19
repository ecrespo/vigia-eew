#!/usr/bin/env python3
"""Enforce coverage per criticality group (REQ-OBS-003, CA-102.1, CA-102.2).

A single global `fail_under` lets a well-covered module pay for a bare one:
the total stays up while the code that decides whether to wake someone at
04:00 goes untested. Each group is asked for its own figure instead.

The thresholds are not a ranking of how much anyone cares about a module.
They follow what a gap in each one costs:

- **pipeline, state, config_writer, history** -- decide whether an earthquake
  is alerted at all, remember what was already alerted, write the file that
  says where the user lives, and keep the record of what was decided. A gap in
  the first two is a missed alert or a duplicate one; in the third, a
  `config.toml` the agent cannot start from; in the fourth, a migration that
  loses somebody's history. None of them is visible until it happens for real.
- **ingest, tiles** -- adapters over somebody else's service. A gap costs one
  source while three others still feed the pipeline (RNF-04), or it costs the
  map while the list it sits on keeps working (REQ-MAP-002).
- **notify, autostart, tray, tui** -- bind to a toolkit, an OS service
  manager or a display. Much of what is left uncovered cannot be exercised
  without the real thing; the opt-in GUI smokes cover that part.

Assembly (`app.py`, `cli.py`) carries no figure on purpose: holding it to
the pipeline's bar measures the wiring, not the decisions.

Usage: `check_coverage.py coverage.json`
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

#: (path prefixes, minimum percent covered -- lines and branches together).
THRESHOLDS: tuple[tuple[tuple[str, ...], float], ...] = (
    (
        (
            "vigia_eew/pipeline/",
            "vigia_eew/state.py",
            "vigia_eew/config_writer.py",
            "vigia_eew/history.py",
        ),
        85.0,
    ),
    (("vigia_eew/ingest/", "vigia_eew/tiles.py"), 70.0),
    (
        (
            "vigia_eew/notify/",
            "vigia_eew/autostart/",
            "vigia_eew/tray.py",
            "vigia_eew/tui.py",
        ),
        40.0,
    ),
)


@dataclass(frozen=True)
class Short:
    """A module below the figure its group owes."""

    path: str
    covered: float
    required: float

    def __str__(self) -> str:
        return f"{self.path}: {self.covered:.1f}% covered, {self.required:.0f}% required"


def threshold_for(path: str) -> float | None:
    """The figure `path` owes, or None when its group declares none."""
    normalised = path.replace("\\", "/")
    for prefixes, required in THRESHOLDS:
        if any(prefix in normalised for prefix in prefixes):
            return required
    return None


def violations(report: dict) -> list[Short]:
    """Every module in `report` that is below its group's figure."""
    short: list[Short] = []
    for path, data in sorted(report.get("files", {}).items()):
        required = threshold_for(path)
        if required is None:
            continue
        covered = float(data["summary"]["percent_covered"])
        if covered < required:
            short.append(Short(path=path, covered=covered, required=required))
    return short


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    report = json.loads(Path(argv[1]).read_text())
    short = violations(report)
    if not short:
        print("Coverage: every group meets the figure it owes.")
        return 0
    print("Coverage below the declared threshold:", file=sys.stderr)
    for item in short:
        print(f"  {item}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
