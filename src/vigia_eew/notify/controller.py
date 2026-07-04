"""Alert controller — orchestrates queue + window + sound + toast.

`AlertController` is where the logical queue (`AlertQueue`) connects with the
presentation effects: when showing an event it creates the window, plays the sound,
and fires the toast; when receiving an `update` it refreshes the current window
(RF-11). It keeps the effects as **injectable callbacks** (`create_window`,
`play_sound`, `send_toast`) so orchestration can be tested without real Tkinter or
audio.

`enqueue(ev)` is the entry point the asyncio<->Tk bridge invokes on the GUI thread.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ..agent_state import AgentState
from ..i18n import DEFAULT_LOCALE
from ..models import SeismicEvent, SeverityLevel
from .presentation import VENEZUELA_ZONE, AlertData, format_event
from .queue import AlertQueue

# create_window(data, severity, on_acknowledge) -> window object (with `refresh`)
_WindowFactory = Callable[[AlertData, SeverityLevel, Callable[[], None]], Any]
_SoundFn = Callable[[SeverityLevel], None]
_ToastFn = Callable[[SeismicEvent], None]
_AcknowledgeFn = Callable[[SeismicEvent], None]


class AlertController:
    """Connects `AlertQueue` with the window, the sound, and the toast (CU-1, CU-5, CU-6)."""

    def __init__(
        self,
        *,
        create_window: _WindowFactory,
        play_sound: _SoundFn | None = None,
        send_toast: _ToastFn | None = None,
        on_acknowledge: _AcknowledgeFn | None = None,
        zone: str = VENEZUELA_ZONE,
        reference_name: str = "reference",
        state: AgentState | None = None,
        locale_code: str = DEFAULT_LOCALE,
        logger: logging.Logger | None = None,
    ) -> None:
        self._create_window = create_window
        self._play_sound = play_sound
        self._toast = send_toast
        self._extra_on_acknowledge = on_acknowledge
        self._zone = zone
        self._reference_name = reference_name
        self._state = state
        self._locale = locale_code
        self._log = logger or logging.getLogger("vigia_eew.notify.controller")
        self._window: Any = None
        self._alert_queue = AlertQueue(
            show=self._show,
            update=self._update,
            on_acknowledge=self._acknowledged,
        )

    @property
    def alert_queue(self) -> AlertQueue:
        return self._alert_queue

    @property
    def paused(self) -> bool:
        """True if presentation of new alerts is paused (RF-34)."""
        return self._alert_queue.paused

    def pause(self) -> None:
        """Stops showing new alerts; they keep queuing up without being lost (RF-34)."""
        self._alert_queue.pause()

    def resume(self) -> None:
        """Resumes alert presentation (RF-34)."""
        self._alert_queue.resume()

    def enqueue(self, ev: SeismicEvent) -> None:
        """Enqueues an event to show it (entry point from the asyncio<->Tk bridge)."""
        self._alert_queue.enqueue(ev)

    def _data(self, ev: SeismicEvent) -> AlertData:
        return format_event(
            ev, zone=self._zone, reference_name=self._reference_name, locale_code=self._locale
        )

    def _show(self, ev: SeismicEvent) -> None:
        data = self._data(ev)
        self._window = self._create_window(data, ev.severity, self._alert_queue.acknowledge)
        if self._play_sound is not None:
            self._play_sound(ev.severity)
        if self._toast is not None:
            self._toast(ev)
        if self._state is not None:
            self._state.mark_last_alert(
                f"{data.magnitude} · {data.place} · {data.local_time}"
            )

    def _update(self, ev: SeismicEvent) -> None:
        if self._window is not None:
            self._window.refresh(self._data(ev))

    def _acknowledged(self, ev: SeismicEvent) -> None:
        self._window = None
        if self._extra_on_acknowledge is not None:
            self._extra_on_acknowledge(ev)
