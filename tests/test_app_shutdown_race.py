"""Tests for the shutdown race in `Application` (REQ-OPS-002, HU-103, ADR-002).

`_run_loop` publishes `self._loop` (app.py:420) and then, several statements
later, `self._sup` (app.py:431). `_stop` reads both from the Tk thread behind a
single `is not None` guard (app.py:443). A quit that lands inside that window
finds the guard false, never calls `request_stop`, and lets `join(timeout=5.0)`
expire: the process still exits because the thread is a daemon, but the ingest
tasks were never cancelled and the event loop never closed cleanly.

The failing test comes first on purpose. Written after the fix it would prove
that the code works, not that the problem was ever there.

It is expected to fail until **T-119** lands the lock plus readiness event, two
phases from here. `strict=True` is what keeps that honest: the day the fix works
the test stops being an expected failure and the suite says so, forcing the
marker off instead of letting a stale xfail hide a passing case.
"""

from __future__ import annotations

import threading

import pytest

from vigia_eew.app import Application
from vigia_eew.config import Settings

#: Long enough that `_stop` is provably past its guard before the worker
#: publishes, short enough that `join(timeout=5.0)` never expires. There is no
#: seam between the guard and the join to synchronise on, so the window is
#: opened by delay -- with four orders of magnitude of margin either way.
_PUBLISH_DELAY_S = 0.05


class _RecordingLoop:
    """Stand-in for the worker's event loop that runs callbacks inline."""

    def __init__(self) -> None:
        self.scheduled: list[object] = []

    def call_soon_threadsafe(self, callback, *args) -> None:
        self.scheduled.append(callback)
        callback(*args)


class _RecordingSupervisor:
    def __init__(self) -> None:
        self.stop_requested = False

    def request_stop(self) -> None:
        self.stop_requested = True


def _worker(app: Application, loop, sup, delay: float) -> threading.Thread:
    """A worker that publishes its loop and supervisor `delay` seconds in.

    Mirrors `_run_loop`: the loop is published first, the supervisor after the
    pipeline is assembled.
    """

    def run() -> None:
        threading.Event().wait(delay)
        app._loop = loop
        app._sup = sup

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


@pytest.mark.xfail(
    strict=True,
    reason="T-119 (F2) synchronises _loop/_sup; red by design until then -- REQ-OPS-002",
)
def test_stop_cancels_when_it_arrives_before_the_worker_publishes() -> None:
    """CA-103.1: a quit inside the publication window still cancels the tasks."""
    app = Application(Settings())
    loop, sup = _RecordingLoop(), _RecordingSupervisor()
    thread = _worker(app, loop, sup, _PUBLISH_DELAY_S)

    app._stop(thread)

    assert not thread.is_alive(), "the worker outlived the shutdown"
    assert sup.stop_requested, (
        "shutdown was requested while the worker had not yet published its loop "
        "and supervisor, so _stop found its guard false and skipped "
        "request_stop entirely: the ingest tasks were never cancelled"
    )


def test_stop_cancels_when_the_worker_published_first() -> None:
    """Control for CA-103.1: outside the window the same path works today.

    Without this, a red test above could mean the harness is wrong rather than
    the code. It also pins the behaviour the fix must not break.
    """
    app = Application(Settings())
    loop, sup = _RecordingLoop(), _RecordingSupervisor()
    thread = _worker(app, loop, sup, delay=0.0)
    thread.join(timeout=5.0)

    app._stop(thread)

    assert sup.stop_requested
