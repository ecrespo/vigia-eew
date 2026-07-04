"""Filtro geográfico y de magnitud (RF-12).

`GeoFilter` decide si un `SeismicEvent` ya normalizado es relevante: dentro del radio
configurado respecto al punto de referencia y con magnitud suficiente. Se aplica antes
de la deduplicación (TECHNICAL-DESIGN §2): descarta barato lo irrelevante. Ambos límites
son **inclusivos** (un evento justo en el borde del radio o en la magnitud mínima pasa).
"""

from __future__ import annotations

from ..config import Filtro
from ..models import SeismicEvent


class GeoFilter:
    """Acepta o descarta eventos por distancia y magnitud (RF-12)."""

    def __init__(self, cfg: Filtro) -> None:
        self._cfg = cfg

    def acepta(self, ev: SeismicEvent) -> bool:
        """True si el evento está dentro del radio y alcanza la magnitud mínima."""
        return ev.distancia_km <= self._cfg.radio_km and ev.magnitud >= self._cfg.magnitud_minima
