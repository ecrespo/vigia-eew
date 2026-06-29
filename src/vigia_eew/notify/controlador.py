"""Controlador de alertas — orquesta cola + ventana + sonido + toast.

`ControladorAlertas` es el punto donde la cola lógica (`AlertQueue`) se conecta con los
efectos de presentación: al mostrar un evento crea la ventana, reproduce el sonido y
lanza el toast; al recibir un `update` refresca la ventana en curso (RF-11). Mantiene
los efectos como **callbacks inyectables** (`crear_ventana`, `reproducir_sonido`,
`enviar_toast`) para que la orquestación se pruebe sin Tkinter ni audio reales.

`encolar(ev)` es la entrada que el puente asyncio↔Tk invoca en el hilo de la GUI.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ..models import SeismicEvent, Severidad
from .presentacion import ZONA_VENEZUELA, DatosAlerta, formatear_evento
from .queue import AlertQueue

# crear_ventana(datos, severidad, al_reconocer) -> objeto ventana (con `actualizar`)
_VentanaFactory = Callable[[DatosAlerta, Severidad, Callable[[], None]], Any]
_SonidoFn = Callable[[Severidad], None]
_ToastFn = Callable[[SeismicEvent], None]
_ReconocerFn = Callable[[SeismicEvent], None]


class ControladorAlertas:
    """Conecta `AlertQueue` con la ventana, el sonido y el toast (CU-1, CU-5, CU-6)."""

    def __init__(
        self,
        *,
        crear_ventana: _VentanaFactory,
        reproducir_sonido: _SonidoFn | None = None,
        enviar_toast: _ToastFn | None = None,
        al_reconocer: _ReconocerFn | None = None,
        zona: str = ZONA_VENEZUELA,
        nombre_referencia: str = "referencia",
        logger: logging.Logger | None = None,
    ) -> None:
        self._crear_ventana = crear_ventana
        self._reproducir = reproducir_sonido
        self._toast = enviar_toast
        self._al_reconocer_extra = al_reconocer
        self._zona = zona
        self._nombre_ref = nombre_referencia
        self._log = logger or logging.getLogger("vigia_eew.notify.controlador")
        self._ventana: Any = None
        self._cola = AlertQueue(
            mostrar=self._mostrar,
            actualizar=self._actualizar,
            al_reconocer=self._reconocido,
        )

    @property
    def cola(self) -> AlertQueue:
        return self._cola

    def encolar(self, ev: SeismicEvent) -> None:
        """Encola un evento para mostrarlo (entrada desde el puente asyncio↔Tk)."""
        self._cola.encolar(ev)

    def _datos(self, ev: SeismicEvent) -> DatosAlerta:
        return formatear_evento(ev, zona=self._zona, nombre_referencia=self._nombre_ref)

    def _mostrar(self, ev: SeismicEvent) -> None:
        self._ventana = self._crear_ventana(self._datos(ev), ev.severidad, self._cola.reconocer)
        if self._reproducir is not None:
            self._reproducir(ev.severidad)
        if self._toast is not None:
            self._toast(ev)

    def _actualizar(self, ev: SeismicEvent) -> None:
        if self._ventana is not None:
            self._ventana.actualizar(self._datos(ev))

    def _reconocido(self, ev: SeismicEvent) -> None:
        self._ventana = None
        if self._al_reconocer_extra is not None:
            self._al_reconocer_extra(ev)
