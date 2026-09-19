"""In-memory state shared across threads (RF-34, REQ-OPS-002).

`AgentState` is a small, lock-protected snapshot: `WSIngestor` updates it on
connect/reconnect (asyncio thread) and `AlertController` on showing an alert
(Tk thread); `tray.py` reads it from its own thread (pystray) for the menu text.
Not persisted — it only lives while the process is running.

`AgentRuntime` protects the other thing that crosses those threads: the event
loop and supervisor the worker publishes and the Tk thread reads at shutdown.
Same lock pattern, for the same reason (ADR-002).

`PresentationEnvironment` is not thread-shared -- it is decided once at
startup and never changes -- but it lives here because it is part of what the
tray reports about the agent, which is what this module is for.
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Mapping

#: Whether the "above everything, cannot be dismissed" promise holds here.
Guarantee = Literal["guaranteed", "degraded", "unknown"]


@dataclass(frozen=True, slots=True)
class PresentationEnvironment:
    """Where this session sits with respect to the alert guarantee (REQ-ALE-003).

    Attributes:
        guarantee: "guaranteed", "degraded", or "unknown" when the session
            cannot be classified. Unknown is a fail-safe outcome, never fatal.
        session: what was detected -- "wayland", "x11", "windows", "macos"
            or "unknown".
        reason: one sentence, shown to the user and written to the log.
    """

    guarantee: Guarantee
    session: str
    reason: str


#: Measured on this project's own hardware, GNOME/Wayland via XWayland:
#: `wm_attributes("-topmost", True)` is accepted without error and reading it
#: back gives 0. The same call under a plain X server on the same machine
#: gives 1. Nothing in the code can tell the difference at the call site,
#: which is why the session has to be reasoned about instead.
_WAYLAND_REASON = (
    "Wayland compositors own window stacking: Tk accepts -topmost and silently "
    "drops it, so the alert can be covered by another window"
)
_X11_REASON = "X11 honours -topmost and focus requests from the alert window"
_NATIVE_REASON = "the platform honours always-on-top for an application window"
_UNKNOWN_REASON = (
    "the desktop session could not be identified; the alert is shown, but being "
    "above every other window is not confirmed here"
)


def detect_presentation_environment(
    *,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> PresentationEnvironment:
    """Classifies the current session against the alert guarantee.

    Never raises and never refuses: this runs at startup, and an agent that
    will not start because it cannot classify a desktop is strictly worse
    than one that starts and says it is not sure (RNF-03, Art. 3).
    """
    env = os.environ if environ is None else environ
    system = sys.platform if platform is None else platform

    if system.startswith("win"):
        return PresentationEnvironment("guaranteed", "windows", _NATIVE_REASON)
    if system == "darwin":
        return PresentationEnvironment("guaranteed", "macos", _NATIVE_REASON)

    session = (env.get("XDG_SESSION_TYPE") or "").strip().lower()
    if session == "wayland" or (not session and env.get("WAYLAND_DISPLAY")):
        return PresentationEnvironment("degraded", "wayland", _WAYLAND_REASON)
    if session == "x11":
        return PresentationEnvironment("guaranteed", "x11", _X11_REASON)
    # DISPLAY alone is not evidence of X11: XWayland sets it too, which is
    # exactly how an agent would conclude it was safe when it is not.
    return PresentationEnvironment("unknown", "unknown", _UNKNOWN_REASON)


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

    def __init__(self, *, presentation: PresentationEnvironment | None = None) -> None:
        self._lock = threading.Lock()
        self._ws_connected = False
        self._last_alert: str | None = None
        #: Decided once at startup and never mutated, so it needs no lock.
        #: Injectable so the classification can be tested without the session.
        self.presentation = presentation or detect_presentation_environment()

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
