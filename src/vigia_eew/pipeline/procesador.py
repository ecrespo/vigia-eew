"""Procesador del pipeline — la tarea que une ingestión y notificación (RF-07..RF-13).

`Procesador` consume los `RawMessage` de la cola de ingestión y, por cada uno, aplica
la secuencia normalizar → filtrar → deduplicar (TECHNICAL-DESIGN §2):

  - inválido o filtrado → se descarta;
  - `nuevo` → se registra como alertado y se entrega a `al_alertar`;
  - `actualizar` (revisión del que está en pantalla) → se entrega a `al_actualizar`
    sin volver a alertar (RF-11);
  - `duplicado` → se descarta.

`al_alertar`/`al_actualizar` son callbacks (en el agente, publican en el puente
asyncio↔Tk). Esto mantiene el procesador desacoplado de la GUI y testeable sin pantalla.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from ..ingest import RawMessage
from ..models import SeismicEvent
from .dedup import Deduplicator
from .filtro import GeoFilter
from .normalize import Normalizer

_Callback = Callable[[SeismicEvent], None]


class Procesador:
    """Orquesta normalize→filtro→dedup sobre la cola de crudos (pipeline_task)."""

    def __init__(
        self,
        entrada: asyncio.Queue[RawMessage],
        normalizer: Normalizer,
        geofilter: GeoFilter,
        deduplicator: Deduplicator,
        *,
        al_alertar: _Callback,
        al_actualizar: _Callback | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._entrada = entrada
        self._normalizer = normalizer
        self._filtro = geofilter
        self._dedup = deduplicator
        self._al_alertar = al_alertar
        self._al_actualizar = al_actualizar
        self._log = logger or logging.getLogger("vigia_eew.pipeline.procesador")

    async def procesar_uno(self, msg: RawMessage) -> None:
        """Procesa un único crudo aplicando normalize→filtro→dedup."""
        ev = self._normalizer.normalizar(msg)
        if ev is None:
            return
        if not self._filtro.acepta(ev):
            self._log.debug("evento_filtrado id=%s distancia=%.0f", ev.id, ev.distancia_km)
            return
        resultado = self._dedup.clasificar(ev)
        if resultado == "nuevo":
            self._dedup.registrar(ev)
            self._al_alertar(ev)
        elif resultado == "actualizar":
            if self._al_actualizar is not None:
                self._al_actualizar(ev)
        # "duplicado": se descarta silenciosamente

    async def run(self) -> None:
        """Bucle del pipeline: consume la cola hasta ser cancelado."""
        while True:
            msg = await self._entrada.get()
            try:
                await self.procesar_uno(msg)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - un crudo no debe tumbar el pipeline
                self._log.warning("procesador_error tipo=%s detalle=%s", type(exc).__name__, exc)
