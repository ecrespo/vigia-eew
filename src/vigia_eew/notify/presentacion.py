"""Presentación del evento para la alerta (RF-18, RF-13, RNF-12).

Funciones **puras** que transforman un `SeismicEvent` (siempre en UTC) en cadenas
legibles para la ventana y el toast, convirtiendo la hora a la zona de Venezuela
(`America/Caracas`) solo aquí (RNF-12). También define el color por severidad (RF-13).
Sin dependencias de GUI: así la presentación se prueba sin pantalla.
"""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from ..models import SeismicEvent, Severidad

ZONA_VENEZUELA = "America/Caracas"

# Color por severidad (RF-13): azul (info), ámbar (atención), rojo (crítico).
_COLOR_POR_SEVERIDAD: dict[Severidad, str] = {
    "info": "#1565C0",
    "atencion": "#F9A825",
    "critico": "#C62828",
}


@dataclass(frozen=True, slots=True)
class DatosAlerta:
    """Campos ya formateados para mostrar en la ventana de alerta (RF-18)."""

    magnitud: str
    lugar: str
    distancia: str
    profundidad: str
    hora_local: str
    fuente: str
    severidad: Severidad


def color_severidad(severidad: Severidad) -> str:
    """Devuelve el color hex asociado a una severidad (RF-13)."""
    return _COLOR_POR_SEVERIDAD[severidad]


def _hora_local(ev: SeismicEvent, zona: str) -> str:
    """Convierte `hora_utc` a la zona indicada y la formatea (RNF-12)."""
    local = ev.hora_utc.astimezone(ZoneInfo(zona))
    return local.strftime("%Y-%m-%d %H:%M:%S")


def _lugar(ev: SeismicEvent) -> str:
    return ev.lugar or ev.region or "Ubicación desconocida"


def formatear_evento(
    ev: SeismicEvent,
    *,
    zona: str = ZONA_VENEZUELA,
    nombre_referencia: str = "referencia",
) -> DatosAlerta:
    """Construye los campos legibles de la alerta a partir del evento (RF-18)."""
    return DatosAlerta(
        magnitud=f"M {ev.magnitud:.1f}",
        lugar=_lugar(ev),
        distancia=f"{ev.distancia_km:.0f} km de {nombre_referencia}",
        profundidad=f"{ev.profundidad_km:.0f} km",
        hora_local=_hora_local(ev, zona),
        fuente=ev.fuente,
        severidad=ev.severidad,
    )


def texto_toast(
    ev: SeismicEvent,
    *,
    zona: str = ZONA_VENEZUELA,
    nombre_referencia: str = "referencia",
) -> tuple[str, str]:
    """Devuelve (título, mensaje) para el toast nativo (RF-14)."""
    datos = formatear_evento(ev, zona=zona, nombre_referencia=nombre_referencia)
    titulo = f"Alerta sísmica {datos.magnitud}"
    mensaje = f"{datos.lugar} · {datos.distancia} · {datos.hora_local}"
    return titulo, mensaje
