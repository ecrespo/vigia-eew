"""Capa de ingestión (RF-01..RF-06).

Las fuentes (WebSocket EMSC y REST USGS) publican **mensajes crudos** (`RawMessage`)
en una cola asyncio. El pipeline de la Fase 3 los normaliza al `SeismicEvent` común.
Mantener el crudo aquí desacopla el transporte de la normalización (API-SPEC §3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import Fuente


@dataclass(frozen=True, slots=True)
class RawMessage:
    """Mensaje sin normalizar emitido por una fuente.

    Attributes:
        fuente: origen del mensaje (`"EMSC"` o `"USGS"`).
        action: `"create"` o `"update"` (EMSC lo trae explícito; USGS es siempre
            `"create"`, el manejo de revisiones se hace por `updated`/cursor).
        feature: el objeto GeoJSON Feature crudo (con `properties` y `geometry`).
    """

    fuente: Fuente
    action: str
    feature: dict[str, Any]


__all__ = ["RawMessage"]
