"""Deduplicación y manejo de `update` (RF-09, RF-10, RF-11; TECHNICAL-DESIGN §5).

`Deduplicator` clasifica cada `SeismicEvent` ya filtrado en uno de tres resultados:

  - `"nuevo"`: nunca alertado y sin coincidencia con eventos recientes → generar alerta.
  - `"actualizar"`: mismo `id` ya alertado con `accion="update"` → refrescar la alerta
    en pantalla sin volver a alertar (RF-11).
  - `"duplicado"`: mismo `id` ya alertado, o coincidencia inter-fuente por heurística
    (≤ distancia, ≤ ventana temporal, ≤ Δmagnitud, RF-09) → descartar.

El estado (`ids_alertados` + `firmas_recientes`) se persiste para no repetir alertas tras
reinicios (RF-10). Las decisiones de id usan igualdad exacta; las inter-fuente, la
heurística configurable (`Dedup`).
"""

from __future__ import annotations

import logging
from typing import Literal

from ..config import Dedup
from ..geo import haversine_km
from ..models import AlertedId, EventSignature, SeismicEvent
from ..state import StateStore

ResultadoDedup = Literal["nuevo", "actualizar", "duplicado"]


class Deduplicator:
    """Clasifica eventos como nuevo/actualizar/duplicado y persiste lo alertado."""

    def __init__(
        self,
        cfg: Dedup,
        estado: StateStore,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._estado = estado
        self._log = logger or logging.getLogger("vigia_eew.pipeline.dedup")

    def clasificar(self, ev: SeismicEvent) -> ResultadoDedup:
        """Determina el resultado de dedup para un evento ya filtrado."""
        if self._estado.ya_alertado(ev.id):
            # Mismo id: o es una revisión (update) de una alerta vigente, o un duplicado.
            return "actualizar" if ev.accion == "update" else "duplicado"
        for firma in self._estado.estado.firmas_recientes:
            if self._coincide(ev, firma):
                self._log.info("dedup_inter_fuente id=%s fuente=%s", ev.id, ev.fuente)
                return "duplicado"
        return "nuevo"

    def registrar(self, ev: SeismicEvent) -> None:
        """Marca un evento como alertado (id + firma) y persiste el estado (RF-10)."""
        self._estado.registrar_alertado(
            AlertedId(id=ev.id, fuente=ev.fuente, hora_utc=ev.hora_utc)
        )
        self._estado.agregar_firma(ev.firma())
        self._estado.guardar()

    def _coincide(self, ev: SeismicEvent, firma: EventSignature) -> bool:
        """True si `ev` y `firma` son el mismo sismo según la heurística (RF-09)."""
        distancia = haversine_km(ev.lat, ev.lon, firma.lat, firma.lon)
        delta_t = abs((ev.hora_utc - firma.hora_utc).total_seconds())
        delta_mag = abs(ev.magnitud - firma.magnitud)
        return (
            distancia <= self._cfg.distancia_km
            and delta_t <= self._cfg.ventana_s
            and delta_mag <= self._cfg.delta_magnitud
        )
