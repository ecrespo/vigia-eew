"""Alert queue and asyncio<->UI bridge (RF-20, RF-11, ADR-006).

`AlertQueue` shows **one alert at a time** and in arrival order (RF-20): acknowledging
the current one shows the next. An `update` of the event on screen **refreshes it in
place** without generating a new alert (RF-11). The queue is pure logic (injected
callbacks): it knows nothing about the UI toolkit, so it can be tested without a screen.

A **drill** -- a simulated alert -- never delays or displaces a real one
(REQ-UX-009): it is taken only when the queue is idle, and a real alert that
arrives while one is on screen closes it unacknowledged and takes its place.

`AsyncioUiBridge` crosses the thread boundary from ADR-006: the asyncio loop publishes
events to a thread-safe `queue.Queue` and the UI thread drains them periodically with
`widget.after` -- which `FletShell` provides, thread-safe.
"""

from __future__ import annotations

import logging
import queue as _stdqueue
from collections import deque
from collections.abc import Callable

from vigia_eew.models import SeismicEvent

_Sink = Callable[[SeismicEvent], None]


class AlertQueue:
    """Serializes alert presentation: one at a time, in order (RF-20)."""

    def __init__(
        self,
        *,
        show: _Sink,
        update: _Sink | None = None,
        on_acknowledge: _Sink | None = None,
        dismiss: _Sink | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._show = show
        self._update = update
        self._on_acknowledge = on_acknowledge
        #: Takes the alert on screen off it **without** an acknowledgement.
        #: Only ever called for a drill a real alert is replacing.
        self._dismiss = dismiss
        self._pending: deque[SeismicEvent] = deque()
        self._current: SeismicEvent | None = None
        self._paused = False
        self._log = logger or logging.getLogger("vigia_eew.notify.queue")

    @property
    def current(self) -> SeismicEvent | None:
        """Event currently being shown, or None if there isn't one."""
        return self._current

    @property
    def pending(self) -> int:
        """Number of events waiting (not counting the one being shown)."""
        return len(self._pending)

    @property
    def paused(self) -> bool:
        """True if presentation of new alerts is paused (RF-34)."""
        return self._paused

    @property
    def idle(self) -> bool:
        """Nothing on screen and nothing waiting."""
        return self._current is None and not self._pending

    # @lat: [[notification#A drill never costs a real alert]]
    def offer_drill(self, ev: SeismicEvent) -> bool:
        """Shows a drill if nothing real could be delayed by it; says whether it did.

        Refused -- not queued -- while an alert is on screen or waiting, and
        while notifications are paused: a drill that queued up would be shown
        the moment the user resumed, or right behind a real earthquake, and
        neither is a moment anybody chose. The caller offers it again later.
        """
        if self._paused or not self.idle:
            return False
        self.enqueue(ev)
        return True

    # @lat: [[notification#Pausing delays presentation, it never drops events]]
    def pause(self) -> None:
        """Stops showing new alerts; they keep queuing up without being lost (RF-34)."""
        self._paused = True

    def resume(self) -> None:
        """Resumes presentation and shows what accumulated while paused."""
        self._paused = False
        self._show_next_if_free()

    def enqueue(self, ev: SeismicEvent) -> None:
        """Enqueues an event; if it's an `update` of the one on screen, refreshes it.

        A *supersede* is the same gesture from a different direction: a
        network the user ranked higher reported the earthquake on screen
        (REQ-PIP-010). Its id is its own -- the catalogues do not share one --
        so it names the alert it overrules instead of matching on identity.

        An arrival that names an alert no longer on screen is **dropped**,
        never queued. Better data about an earthquake the user already
        acknowledged is not a second earthquake.
        """
        if ev.supersedes is not None:
            if self._current is not None and ev.supersedes == self._current.id:
                self._refresh(ev)
            else:
                self._log.info("alert_supersede_ignored id=%s supersedes=%s", ev.id, ev.supersedes)
            return
        if ev.action == "update" and self._current is not None and ev.id == self._current.id:
            self._refresh(ev)
            return
        if self._current is not None and self._current.is_drill and not ev.is_drill:
            self._displace_drill(ev)
            return
        self._pending.append(ev)
        self._show_next_if_free()

    def _displace_drill(self, ev: SeismicEvent) -> None:
        """A real alert arrived while a drill was on screen: the drill goes.

        Closed without acknowledgement -- nobody saw it out, so
        `on_acknowledge` is not called for it -- and the real alert goes to
        the front of whatever is waiting, which can only be other drills.
        """
        drill = self._current
        self._current = None
        if drill is not None and self._dismiss is not None:
            self._dismiss(drill)
        self._log.info("drill_displaced id=%s by=%s", drill.id if drill else None, ev.id)
        self._pending.appendleft(ev)
        self._show_next_if_free()

    def _refresh(self, ev: SeismicEvent) -> None:
        """Replaces what the alert on screen is showing, without alerting again."""
        self._current = ev
        if self._update is not None:
            self._update(ev)
        self._log.info("alert_updated id=%s supersedes=%s", ev.id, ev.supersedes)

    def acknowledge(self) -> None:
        """Acknowledges the current alert and shows the next one (CU-5)."""
        if self._current is None:
            return
        acknowledged = self._current
        self._current = None
        if self._on_acknowledge is not None:
            self._on_acknowledge(acknowledged)
        self._log.info("alert_acknowledged id=%s", acknowledged.id)
        self._show_next_if_free()

    def _show_next_if_free(self) -> None:
        if self._paused or self._current is not None or not self._pending:
            return
        self._current = self._pending.popleft()
        self._show(self._current)
        self._log.info("alert_shown id=%s", self._current.id)


# @lat: [[architecture#Asyncio and Flet split across two threads]]
class AsyncioUiBridge:
    """Thread-safe bridge from the asyncio loop to the UI (Flet) thread (ADR-006)."""

    def __init__(self, *, sink: _Sink, logger: logging.Logger | None = None) -> None:
        self._queue: _stdqueue.Queue[SeismicEvent] = _stdqueue.Queue()
        self._sink = sink
        self._log = logger or logging.getLogger("vigia_eew.notify.bridge")

    def publish(self, ev: SeismicEvent) -> None:
        """Publishes an event from the asyncio thread (thread-safe)."""
        self._queue.put_nowait(ev)

    def drain(self) -> None:
        """Empties the queue delivering each event to the sink (on the UI thread)."""
        while True:
            try:
                ev = self._queue.get_nowait()
            except _stdqueue.Empty:
                return
            self._sink(ev)

    def start_polling(self, widget: object, interval_ms: int = 100) -> None:
        """Schedules periodic draining of the queue on the UI loop."""

        def tick() -> None:
            self.drain()
            widget.after(interval_ms, tick)  # type: ignore[attr-defined]

        widget.after(interval_ms, tick)  # type: ignore[attr-defined]
