"""The v1.0.0 cut, as something a gate can read (T-138).

The plan is explicit that the condition for cutting is **not** "every phase
done" but a list of ten statements. A list of ten statements that only a human
compares against reality is a list that drifts, and the drift shows up after
the tag rather than before it.

So the cut is checked here: the version the package declares, the version the
changelog announces, the ten conditions, and every task either done or
explicitly out of scope with a reason.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN = REPO_ROOT / "docs" / "v1" / "06-IMPLEMENTATION-PLAN.md"
TASKS = REPO_ROOT / "docs" / "v1" / "07-TASKS.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

#: The two tasks that are not `[x]`, and the words that have to appear in each
#: one's entry for the deferral to count as a decision rather than an omission.
#:
#: T-132 is out of the cut by decision D-1: GNOME under Wayland advertises no
#: protocol any client could use to keep the always-on-top promise, so
#: REQ-ALE-004 became a `[SHOULD]` and its implementation task went with it.
#:
#: T-138 is the publication itself. Everything the repository controls is done
#: -- version, changelog, the ten conditions, artifacts built and run -- and
#: what is left happens on a tag push, which is somebody's decision to make and
#: not a commit's.
DEFERRED: dict[str, tuple[str, ...]] = {
    "T-132": ("fuera del corte", "D-1"),
    "T-138": ("pendiente", "tag"),
}


def _declared_version() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _released_sections() -> list[str]:
    """The versions the changelog announces, newest first."""
    return re.findall(r"^## \[(\d+\.\d+\.\d+)\]", CHANGELOG.read_text(encoding="utf-8"), re.M)


def test_the_package_and_the_changelog_agree_on_the_version() -> None:
    """A release whose notes describe a different number is a release nobody can cite."""
    assert _released_sections()[0] == _declared_version()


def test_the_release_carries_a_date() -> None:
    version = _declared_version()
    text = CHANGELOG.read_text(encoding="utf-8")

    assert re.search(rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}", text, re.M)


def test_nothing_is_left_sitting_in_the_unreleased_section() -> None:
    """Whatever is in it at the cut ships without being announced.

    The heading stays -- the next change lands under it -- but it has to be
    empty when the tag is made.
    """
    text = CHANGELOG.read_text(encoding="utf-8")
    unreleased = text.split("## [Sin publicar]", 1)[1].split("## [", 1)[0]

    assert unreleased.strip() == "", f"unreleased entries at the cut: {unreleased.strip()[:200]}"


def test_the_ten_cut_conditions_are_met() -> None:
    """The list the plan says is *the* condition, not "every phase done"."""
    rows = [
        line
        for line in PLAN.read_text(encoding="utf-8").splitlines()
        if re.match(r"^\| \d+ \|", line)
    ]

    assert len(rows) == 10, f"the cut list has {len(rows)} conditions, not 10"
    unmet = [row for row in rows if "✅" not in row]
    assert unmet == [], f"{len(unmet)} cut conditions are not met"


def test_every_task_is_done_or_declared_out_of_the_cut() -> None:
    """A task nobody marked is indistinguishable from a task nobody did."""
    text = TASKS.read_text(encoding="utf-8")
    pending = re.findall(r"^### \[([ ~!])\] (T-\d+)", text, re.M)

    unfinished = {task for state, task in pending if state != "~"}
    assert unfinished == set(), f"tasks neither done nor deferred: {sorted(unfinished)}"

    deferred = {task for state, task in pending if state == "~"}
    expected = set(DEFERRED)
    assert deferred == expected, f"unexpected deferrals: {sorted(deferred ^ expected)}"


def test_each_deferral_says_why() -> None:
    """Deferring is a decision, and a decision with no reason is an omission."""
    text = TASKS.read_text(encoding="utf-8")
    for task, words in DEFERRED.items():
        section = text.split(f"### [~] {task}", 1)[1].split("### ", 1)[0]
        for word in words:
            assert word in section, f"{task} does not say {word!r}"


def test_the_task_count_still_matches_what_the_plan_promised() -> None:
    """49 tasks were planned; the register has to account for all of them."""
    text = TASKS.read_text(encoding="utf-8")
    declared = re.search(r"\*\*(\d+) tareas\*\*", text)
    assert declared is not None

    listed = re.findall(r"^### \[[x ~!]\]", text, re.M)
    assert len(listed) == int(declared.group(1))
