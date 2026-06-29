"""Backoff exponencial con jitter (RF-03, RNF-03).

Helper puro reutilizado por la reconexión del WebSocket (`ingest/ws_emsc.py`) y por
el reinicio de tareas del `Supervisor`. La estrategia es *equal jitter*: la espera
nominal duplica (base·2^(intento-1)) saturada en `tope`, y el jitter reparte el
resultado en `[nominal/2, nominal]` para evitar reconexiones sincronizadas.
"""

from __future__ import annotations

import random
from collections.abc import Callable

# Generador por defecto: número en [0, 1). Inyectable para pruebas deterministas.
_rng_por_defecto: Callable[[], float] = random.random


def exponential_backoff(
    intento: int,
    *,
    base: float = 1.0,
    tope: float = 60.0,
    jitter: bool = True,
    rng: Callable[[], float] = _rng_por_defecto,
) -> float:
    """Calcula la espera (segundos) antes del siguiente reintento.

    Args:
        intento: número de intento, empezando en 1.
        base: espera del primer intento (intento=1) sin jitter.
        tope: espera máxima; satura el crecimiento exponencial.
        jitter: si False, devuelve la espera nominal determinista.
        rng: fuente de aleatoriedad en [0, 1); inyectable en pruebas.

    Returns:
        Segundos a esperar (siempre <= `tope`).

    Raises:
        ValueError: si `intento` < 1.
    """
    if intento < 1:
        raise ValueError("intento debe ser >= 1")
    # 2.0 (no 2) para que mypy infiera float: `int ** int` puede ser float (exp. negativos).
    nominal = min(tope, base * 2.0 ** (intento - 1))
    if not jitter:
        return nominal
    # Equal jitter: mitad fija + mitad aleatoria, acotado por `nominal` (<= tope).
    mitad = nominal / 2
    return mitad + rng() * mitad
