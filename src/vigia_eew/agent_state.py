"""In-memory state shared across threads (RF-34, REQ-OPS-002).

`AgentState` is a small, lock-protected snapshot: `WSIngestor` updates it on
connect/reconnect (asyncio thread) and `AlertController` on showing an alert
(Tk thread); `tray.py` reads it from its own thread (pystray) for the menu text.
Not persisted — it only lives while the process is running.

`AgentRuntime` protects the other thing that crosses those threads: the event
loop and supervisor the worker publishes and the Tk thread reads at shutdown.
Same lock pattern, for the same reason (ADR-002).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import asyncio


class Stoppable(Protocol):
    """Anything shutdown can ask to wind down — in practice, the supervisor.

    Structural rather than imported: this module is the shared kernel and
    sits below `supervisor`, so naming the concrete type here would be an
    upward import and the boundary contracts would (rightly) reject it.
    """

    def request_stop(self) -> None: ...


class AgentRuntime:
    """The loop and supervisor the worker thread publishes, read by the Tk thread.

    The two used to be plain attributes on `Application`, assigned several
    statements apart: the loop as soon as it existed, the supervisor once the
    pipeline had been assembled. A quit landing between those two assignments
    found the `is not None` guard false, skipped `request_stop` entirely and
    let `join` expire. The process still exited -- the thread is a daemon --
    but no ingest task was ever cancelled and the loop never closed cleanly.

    Two changes close it. They are **published together**, so there is no
    longer an interval in which one is visible and the other is not; and a
    reader that arrives early can *wait*, instead of concluding from a None
    that there is nothing to stop.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stoppable: Stoppable | None = None

    def publish(self, loop: asyncio.AbstractEventLoop, stoppable: Stoppable) -> None:
        """Makes both visible at once, from the worker thread."""
        with self._lock:
            self._loop = loop
            self._stoppable = stoppable
        self._ready.set()

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        """The loop, or None if the worker has not published yet.

        For callers with something better to do than wait -- publishing a
        toast falls back to its own loop rather than blocking the UI thread.
        """
        with self._lock:
            return self._loop

    def await_ready(self, timeout: float) -> tuple[asyncio.AbstractEventLoop, Stoppable] | None:
        """Waits up to `timeout` for the pair, or None if it never arrives.

        None is a real outcome, not an error: the worker can die before it
        publishes. The caller reports it and carries on -- a shutdown that
        blocks forever waiting to shut down cleanly is worse than one that
        says it could not.
        """
        if not self._ready.wait(timeout):
            return None
        with self._lock:
            loop, stoppable = self._loop, self._stoppable
        if loop is None or stoppable is None:  # pragma: no cover - publish sets both
            return None
        return loop, stoppable


class AgentState:
    """Thread-safe snapshot of connection status and last alert, for the tray menu."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ws_connected = False
        self._last_alert: str | None = None

    @property
    def ws_connected(self) -> bool:
        with self._lock:
            return self._ws_connected

    @property
    def last_alert(self) -> str | None:
        with self._lock:
            return self._last_alert

    def mark_connected(self) -> None:
        with self._lock:
            self._ws_connected = True

    def mark_reconnecting(self) -> None:
        with self._lock:
            self._ws_connected = False

    def mark_last_alert(self, summary: str) -> None:
        with self._lock:
            self._last_alert = summary
