"""Capa de notificación (RF-14..RF-21).

Componentes:
  - `presentacion`: formato legible del evento y mapeo de severidad a color (RF-18).
  - `sound`: audio por severidad, más insistente cuanto más grave (RF-17).
  - `toast`: toast nativo del SO vía `desktop-notifier` (RF-14).
  - `alert_window`: ventana superpuesta no descartable en Tkinter (RF-15..RF-19).
  - `queue`: cola de alertas (una a la vez) + puente asyncio↔Tk (RF-20, ADR-006).
"""

from __future__ import annotations
