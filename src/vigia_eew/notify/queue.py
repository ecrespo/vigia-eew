"""Cola de alertas y puente asyncio↔Tk (RF-20, RF-11, ADR-006).

`AlertQueue` muestra **una alerta a la vez** y en orden de llegada (RF-20): al reconocer
la actual, aparece la siguiente. Un `update` del evento en pantalla lo **refresca en sitio**
sin generar una alerta nueva (RF-11). La cola es lógica pura (callbacks inyectados): no
conoce Tkinter, así se prueba sin pantalla.

`PuenteAsyncioTk` cruza el límite de hilos del ADR-006: el bucle asyncio publica eventos
en una `queue.Queue` thread-safe y el hilo de Tk los drena periódicamente con `widget.after`.
"""

from __future__ import annotations

import logging
import queue as _stdqueue
from collections import deque
from collections.abc import Callable

from ..models import SeismicEvent

_Sink = Callable[[SeismicEvent], None]


class AlertQueue:
    """Serializa la presentación de alertas: una a la vez, en orden (RF-20)."""

    def __init__(
        self,
        *,
        mostrar: _Sink,
        actualizar: _Sink | None = None,
        al_reconocer: _Sink | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._mostrar = mostrar
        self._actualizar = actualizar
        self._al_reconocer = al_reconocer
        self._pendientes: deque[SeismicEvent] = deque()
        self._actual: SeismicEvent | None = None
        self._pausado = False
        self._log = logger or logging.getLogger("vigia_eew.notify.queue")

    @property
    def actual(self) -> SeismicEvent | None:
        """Evento que se está mostrando, o None si no hay ninguno."""
        return self._actual

    @property
    def pendientes(self) -> int:
        """Cantidad de eventos en espera (sin contar el que se muestra)."""
        return len(self._pendientes)

    @property
    def pausado(self) -> bool:
        """True si la presentación de nuevas alertas está pausada (RF-34)."""
        return self._pausado

    def pausar(self) -> None:
        """Deja de mostrar alertas nuevas; siguen encolándose sin perderse (RF-34)."""
        self._pausado = True

    def reanudar(self) -> None:
        """Reanuda la presentación y muestra lo acumulado mientras estaba pausada."""
        self._pausado = False
        self._mostrar_siguiente_si_libre()

    def encolar(self, ev: SeismicEvent) -> None:
        """Encola un evento; si es un `update` del que está en pantalla, lo refresca."""
        if (
            ev.accion == "update"
            and self._actual is not None
            and ev.id == self._actual.id
        ):
            self._actual = ev
            if self._actualizar is not None:
                self._actualizar(ev)
            self._log.info("alerta_actualizada id=%s", ev.id)
            return
        self._pendientes.append(ev)
        self._mostrar_siguiente_si_libre()

    def reconocer(self) -> None:
        """Reconoce la alerta actual y muestra la siguiente (CU-5)."""
        if self._actual is None:
            return
        reconocido = self._actual
        self._actual = None
        if self._al_reconocer is not None:
            self._al_reconocer(reconocido)
        self._log.info("alerta_reconocida id=%s", reconocido.id)
        self._mostrar_siguiente_si_libre()

    def _mostrar_siguiente_si_libre(self) -> None:
        if self._pausado or self._actual is not None or not self._pendientes:
            return
        self._actual = self._pendientes.popleft()
        self._mostrar(self._actual)
        self._log.info("alerta_mostrada id=%s", self._actual.id)


class PuenteAsyncioTk:
    """Puente thread-safe del bucle asyncio al hilo de Tkinter (ADR-006)."""

    def __init__(self, *, sink: _Sink, logger: logging.Logger | None = None) -> None:
        self._cola: _stdqueue.Queue[SeismicEvent] = _stdqueue.Queue()
        self._sink = sink
        self._log = logger or logging.getLogger("vigia_eew.notify.puente")

    def publicar(self, ev: SeismicEvent) -> None:
        """Publica un evento desde el hilo asyncio (thread-safe)."""
        self._cola.put_nowait(ev)

    def drenar(self) -> None:
        """Vacía la cola entregando cada evento al sink (en el hilo de Tk)."""
        while True:
            try:
                ev = self._cola.get_nowait()
            except _stdqueue.Empty:
                return
            self._sink(ev)

    def iniciar_sondeo(self, widget: object, intervalo_ms: int = 100) -> None:
        """Programa el drenado periódico de la cola en el bucle de Tkinter."""

        def tick() -> None:
            self.drenar()
            widget.after(intervalo_ms, tick)  # type: ignore[attr-defined]

        widget.after(intervalo_ms, tick)  # type: ignore[attr-defined]
