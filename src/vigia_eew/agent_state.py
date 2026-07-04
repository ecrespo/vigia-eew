"""In-memory state shared across threads, for the tray icon (RF-34).

`AgentState` is a small, lock-protected snapshot: `WSIngestor` updates it on
connect/reconnect (asyncio thread) and `AlertController` on showing an alert
(Tk thread); `tray.py` reads it from its own thread (pystray) for the menu text.
Not persisted — it only lives while the process is running.
"""

from __future__ import annotations

import threading


class AgentState:
    """Thread-safe snapshot of connection status and last alert, for the tray menu."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ws_connected = False
        self._last_alert: str | None = None

    @property
    def ws_connected(self) -> bool:
        with self._lock:
            return self._ws_connected

    @property
    def last_alert(self) -> str | None:
        with self._lock:
            return self._last_alert

    def mark_connected(self) -> None:
        with self._lock:
            self._ws_connected = True

    def mark_reconnecting(self) -> None:
        with self._lock:
            self._ws_connected = False

    def mark_last_alert(self, summary: str) -> None:
        with self._lock:
            self._last_alert = summary
