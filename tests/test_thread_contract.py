"""Tests for the documented thread-ownership contract (REQ-OPS-003, CA-103.6).

The shutdown race of ADR-002 was not caused by a hard concurrency problem. It
was caused by nobody having written down which thread owned `_loop` and
`_sup`, so the question never got asked. `AgentState` two files away was
already doing it correctly with the same primitive.

This asserts the table exists and covers what it claims to. It cannot verify
that the table is *true* -- only review can -- but a table that silently
loses a row as the code grows is worse than none, and that part is checkable.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONVENTIONS = REPO_ROOT / "lat.md" / "conventions.md"

#: Every mutable thing more than one thread touches, as of v1.0.
SHARED_STATE = (
    "AgentRuntime",
    "AgentState",
    "AsyncioTkBridge",
    "raw_queue",
)


def test_the_thread_contract_is_written_down() -> None:
    """CA-103.6: there is a table of who owns what, and how it is synchronised."""
    text = CONVENTIONS.read_text()
    assert "Thread ownership" in text
    for primitive in ("threading.Lock", "threading.Event", "call_soon_threadsafe"):
        assert primitive in text


def test_every_piece_of_shared_state_has_a_row() -> None:
    """CA-103.6: including the application's, which is what ADR-002 was about."""
    table = CONVENTIONS.read_text().split("Thread ownership", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in table.splitlines() if line.startswith("|")]
    assert len(rows) >= len(SHARED_STATE) + 2  # header plus separator
    for item in SHARED_STATE:
        assert any(item in row for row in rows), f"{item} has no row in the table"


def test_the_code_declares_no_shared_state_the_table_omits() -> None:
    """A lock that appears in the code and not in the table is the drift to catch."""
    table = CONVENTIONS.read_text().split("Thread ownership", 1)[1].split("\n## ", 1)[0]
    src = REPO_ROOT / "src" / "vigia_eew"
    holders = set()
    for module in src.rglob("*.py"):
        # Per class, not per module: a frozen value object declared next to a
        # lock-holding one acquires nothing, and flagging it would train people
        # to add rows for things that need no row.
        for block in re.split(r"^class ", module.read_text(), flags=re.M)[1:]:
            name = re.match(r"(\w+)", block)
            if name and ("threading.Lock()" in block or "threading.Event()" in block):
                holders.add(name.group(1))
    undocumented = {name for name in holders if name not in table}
    assert undocumented == set(), f"synchronised state missing from the table: {undocumented}"
