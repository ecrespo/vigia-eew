"""Alert queue and asyncio<->Tk bridge (RF-20, RF-11, ADR-006).

`AlertQueue` shows **one alert at a time** and in arrival order (RF-20): acknowledging
the current one shows the next. An `update` of the event on screen **refreshes it in
place** without generating a new alert (RF-11). The queue is pure logic (injected
callbacks): it knows nothing about Tkinter, so it can be tested without a screen.

`AsyncioTkBridge` crosses the thread boundary from ADR-006: the asyncio loop publishes
events to a thread-safe `queue.Queue` and the Tk thread drains them periodically with
`widget.after`.
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
        logger: logging.Logger | None = None,
    ) -> None:
        self._show = show
        self._update = update
        self._on_acknowledge = on_acknowledge
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

    def pause(self) -> None:
        """Stops showing new alerts; they keep queuing up without being lost (RF-34)."""
        self._paused = True

    def resume(self) -> None:
        """Resumes presentation and shows what accumulated while paused."""
        self._paused = False
        self._show_next_if_free()

    def enqueue(self, ev: SeismicEvent) -> None:
        """Enqueues an event; if it's an `update` of the one on screen, refreshes it."""
        if (
            ev.action == "update"
            and self._current is not None
            and ev.id == self._current.id
        ):
            self._current = ev
            if self._update is not None:
                self._update(ev)
            self._log.info("alert_updated id=%s", ev.id)
            return
        self._pending.append(ev)
        self._show_next_if_free()

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


class AsyncioTkBridge:
    """Thread-safe bridge from the asyncio loop to the Tkinter thread (ADR-006)."""

    def __init__(self, *, sink: _Sink, logger: logging.Logger | None = None) -> None:
        self._queue: _stdqueue.Queue[SeismicEvent] = _stdqueue.Queue()
        self._sink = sink
        self._log = logger or logging.getLogger("vigia_eew.notify.bridge")

    def publish(self, ev: SeismicEvent) -> None:
        """Publishes an event from the asyncio thread (thread-safe)."""
        self._queue.put_nowait(ev)

    def drain(self) -> None:
        """Empties the queue delivering each event to the sink (on the Tk thread)."""
        while True:
            try:
                ev = self._queue.get_nowait()
            except _stdqueue.Empty:
                return
            self._sink(ev)

    def start_polling(self, widget: object, interval_ms: int = 100) -> None:
        """Schedules periodic draining of the queue on the Tkinter loop."""

        def tick() -> None:
            self.drain()
            widget.after(interval_ms, tick)  # type: ignore[attr-defined]

        widget.after(interval_ms, tick)  # type: ignore[attr-defined]
