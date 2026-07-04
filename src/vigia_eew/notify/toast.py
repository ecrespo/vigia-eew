"""Toast nativo del SO (RF-14, ADR-009 para asincronía).

`Toaster` envía una notificación nativa con `desktop-notifier` (Linux/Win/macOS) como
canal **informativo y complementario** a la ventana superpuesta (la ventana es la que
garantiza el "no descartable"; el toast puede silenciarse por "No molestar").

La urgencia escala con la severidad. El `notifier` se inyecta para pruebas; un fallo del
toast (p. ej. DBus caído) **nunca** interrumpe la alerta: se registra y se continúa (RNF-03).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, cast

from desktop_notifier import Urgency

from ..models import SeismicEvent, Severidad
from .presentacion import ZONA_VENEZUELA, texto_toast

_URGENCIA_POR_SEVERIDAD: dict[Severidad, Urgency] = {
    "info": Urgency.Low,
    "atencion": Urgency.Normal,
    "critico": Urgency.Critical,
}


class _Notifier(Protocol):
    """Interfaz mínima de `desktop_notifier.DesktopNotifier` que usamos."""

    async def send(self, *, title: str, message: str, urgency: Urgency, **kwargs: Any) -> Any: ...


def _urgencia(severidad: Severidad) -> Urgency:
    return _URGENCIA_POR_SEVERIDAD[severidad]


class Toaster:
    """Emite toasts nativos a partir de eventos sísmicos (RF-14)."""

    def __init__(
        self,
        *,
        notifier: _Notifier | None = None,
        app_name: str = "Vigía-eew",
        zona: str = ZONA_VENEZUELA,
        nombre_referencia: str = "referencia",
        logger: logging.Logger | None = None,
    ) -> None:
        self._notifier = notifier
        self._app_name = app_name
        self._zona = zona
        self._nombre_referencia = nombre_referencia
        self._log = logger or logging.getLogger("vigia_eew.notify.toast")

    def _obtener_notifier(self) -> _Notifier:
        notifier = self._notifier
        if notifier is None:
            from desktop_notifier import DesktopNotifier

            # `cast`: la clase real usa args posicionales; estructuralmente equivalente.
            notifier = cast(_Notifier, DesktopNotifier(app_name=self._app_name))
            self._notifier = notifier
        return notifier

    async def notificar(self, ev: SeismicEvent) -> None:
        """Envía el toast del evento; aísla cualquier fallo del backend (RNF-03)."""
        try:
            titulo, mensaje = texto_toast(
                ev, zona=self._zona, nombre_referencia=self._nombre_referencia
            )
            await self._obtener_notifier().send(
                title=titulo, message=mensaje, urgency=_urgencia(ev.severidad)
            )
        except Exception as exc:  # noqa: BLE001 - el toast nunca rompe la alerta
            self._log.warning("toast_fallo detalle=%s", exc)
