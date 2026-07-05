"""Native OS toast (RF-14, ADR-009 for asynchrony).

`Toaster` sends a native notification with `desktop-notifier` (Linux/Win/macOS) as an
**informative, complementary** channel to the overlay window (the window is what
guarantees "undismissable"; the toast can be silenced by "Do Not Disturb").

Urgency scales with severity. The `notifier` is injected for testing; a toast failure
(e.g. DBus down) **never** interrupts the alert: it is logged and execution continues
(RNF-03).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, cast

from desktop_notifier import Urgency

from vigia_eew.i18n import DEFAULT_LOCALE
from vigia_eew.models import SeismicEvent, SeverityLevel
from vigia_eew.notify.presentation import VENEZUELA_ZONE, toast_text

_URGENCY_BY_SEVERITY: dict[SeverityLevel, Urgency] = {
    "info": Urgency.Low,
    "warning": Urgency.Normal,
    "critical": Urgency.Critical,
}


class _Notifier(Protocol):
    """Minimal interface of `desktop_notifier.DesktopNotifier` that we use."""

    async def send(self, *, title: str, message: str, urgency: Urgency, **kwargs: Any) -> Any: ...


def _urgency(severity: SeverityLevel) -> Urgency:
    return _URGENCY_BY_SEVERITY[severity]


class Toaster:
    """Emits native toasts from seismic events (RF-14)."""

    def __init__(
        self,
        *,
        notifier: _Notifier | None = None,
        app_name: str = "Vigía-eew",
        zone: str = VENEZUELA_ZONE,
        reference_name: str = "reference",
        locale_code: str = DEFAULT_LOCALE,
        logger: logging.Logger | None = None,
    ) -> None:
        self._notifier = notifier
        self._app_name = app_name
        self._zone = zone
        self._reference_name = reference_name
        self._locale = locale_code
        self._log = logger or logging.getLogger("vigia_eew.notify.toast")

    def _get_notifier(self) -> _Notifier:
        notifier = self._notifier
        if notifier is None:
            from desktop_notifier import DesktopNotifier

            # `cast`: the real class uses positional args; structurally equivalent.
            notifier = cast(_Notifier, DesktopNotifier(app_name=self._app_name))
            self._notifier = notifier
        return notifier

    async def notify(self, ev: SeismicEvent) -> None:
        """Sends the event's toast; isolates any backend failure (RNF-03)."""
        try:
            title, message = toast_text(
                ev, zone=self._zone, reference_name=self._reference_name, locale_code=self._locale
            )
            await self._get_notifier().send(
                title=title, message=message, urgency=_urgency(ev.severity)
            )
        except Exception as exc:  # noqa: BLE001 - the toast never breaks the alert
            self._log.warning("toast_failed detail=%s", exc)
