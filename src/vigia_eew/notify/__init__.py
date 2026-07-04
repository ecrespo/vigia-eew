"""Notification layer (RF-14..RF-21).

Components:
  - `presentation`: readable event formatting and severity-to-color mapping (RF-18).
  - `sound`: audio per severity, more insistent the more severe (RF-17).
  - `toast`: native OS toast via `desktop-notifier` (RF-14).
  - `alert_window`: undismissable overlay window in Tkinter (RF-15..RF-19).
  - `queue`: alert queue (one at a time) + asyncio<->Tk bridge (RF-20, ADR-006).
"""

from __future__ import annotations
