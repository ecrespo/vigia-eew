"""Tests for the shutdown race in `Application` (REQ-OPS-002, HU-103, ADR-002).

`_run_loop` used to publish the event loop as soon as it existed and the
supervisor several statements later, once the pipeline had been assembled;
`_stop` read both from the Tk thread behind a single `is not None` guard. A quit
landing inside that window found the guard false, never called `request_stop`,
and let `join(timeout=5.0)` expire: the process still exited because the thread
is a daemon, but no ingest task was ever cancelled and the loop never closed
cleanly.

The failing test comes first on purpose. Written after the fix it would prove
that the code works, not that the problem was ever there.

T-119 closed it, with the lock plus readiness event of ADR-002. The scenarios
below cover both branches the fix has to satisfy: publication that arrives late
(waited for) and publication that never arrives (reported, not hung).
"""

from __future__ import annotations

import asyncio
import threading

from vigia_eew.app import Application
from vigia_eew.config import Settings
from vigia_eew.supervisor import Supervisor

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
        app.publish_runtime(loop, sup)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


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


def test_stop_reports_a_runtime_that_never_arrives(caplog) -> None:
    """CA-103.2: an unpublished runtime is named, not waited on forever.

    The worker can die before it publishes -- a failure while building the
    pipeline, for instance. Shutdown has to end anyway, and has to say why
    it could not cancel anything.
    """
    app = Application(Settings())
    finished = threading.Thread(target=lambda: None, daemon=True)
    finished.start()

    with caplog.at_level("WARNING"):
        app._stop(finished, runtime_timeout=0.05)

    assert "stop_before_runtime_ready" in caplog.text


def test_stop_cancels_every_task_in_the_normal_case() -> None:
    """CA-103.3: with the agent running, a stop leaves no task alive.

    Driven through a real event loop and a real Supervisor rather than
    stubs: "no orphan tasks" is a property of the loop, and a fake loop
    would be asserting the stub's behaviour instead of the shutdown's.
    """
    app = Application(Settings())
    started = threading.Event()
    surviving: list[str] = []

    def worker() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sup = Supervisor(handle_signals=False)
        for name in ("ws", "rest", "funvisis", "geofon", "pipeline"):
            sup.add(name, lambda: asyncio.sleep(3600))
        app.publish_runtime(loop, sup)
        started.set()
        try:
            loop.run_until_complete(sup.run())
            surviving.extend(task.get_name() for task in asyncio.all_tasks(loop) if not task.done())
        finally:
            loop.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    assert started.wait(timeout=5.0)

    app._stop(thread)

    assert not thread.is_alive(), "the worker outlived the shutdown"
    assert surviving == [], f"tasks left alive: {surviving}"
