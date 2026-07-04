"""Estado en memoria compartido entre hilos, para el ícono de bandeja (RF-34).

`EstadoAgente` es un snapshot pequeño y protegido por lock: `WSIngestor` lo actualiza
al conectar/reconectar (hilo asyncio) y `ControladorAlertas` al mostrar una alerta
(hilo de Tk); `tray.py` lo lee desde su propio hilo (pystray) para el texto del menú.
No se persiste — vive solo mientras el proceso corre.
"""

from __future__ import annotations

import threading


class EstadoAgente:
    """Snapshot thread-safe de conexión y última alerta, para el menú de bandeja."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ws_conectado = False
        self._ultima_alerta: str | None = None

    @property
    def ws_conectado(self) -> bool:
        with self._lock:
            return self._ws_conectado

    @property
    def ultima_alerta(self) -> str | None:
        with self._lock:
            return self._ultima_alerta

    def marcar_conectado(self) -> None:
        with self._lock:
            self._ws_conectado = True

    def marcar_reconectando(self) -> None:
        with self._lock:
            self._ws_conectado = False

    def marcar_ultima_alerta(self, resumen: str) -> None:
        with self._lock:
            self._ultima_alerta = resumen
