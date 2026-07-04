"""Ícono de bandeja del sistema (RF-34, ADR-012) — mejor esfuerzo, no bloqueante.

`construir_icono` arma un `pystray.Icon` con un menú (estado, pausar/reanudar, editar
configuración, salir); `IconoBandeja` lo corre en un hilo de trabajo aparte, dejando
Tkinter dueño exclusivo del hilo principal (ADR-006). Cualquier fallo al construir o
arrancar el ícono (backend gráfico ausente, GNOME/Wayland sin extensión de bandeja,
etc.) se aísla: se loguea un *warning* y el agente sigue funcionando sin ícono, igual
que `notify/toast.py` y `geoloc.py`.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from PIL import Image
from pystray import Icon, Menu, MenuItem

from .estado_agente import EstadoAgente

_NOMBRE_ARCHIVO_ICONO = "tray_icon.png"


def ruta_icono_predeterminada() -> Path:
    """Ruta al PNG del ícono empaquetado junto al paquete."""
    return Path(__file__).parent / "assets" / _NOMBRE_ARCHIVO_ICONO


def _comando_abrir(ruta: Path) -> list[str] | None:
    """Comando de SO para abrir `ruta` con la app asociada; `None` = usar `os.startfile`."""
    if sys.platform == "darwin":
        return ["open", str(ruta)]
    if sys.platform == "win32":
        return None
    return ["xdg-open", str(ruta)]


def abrir_config(ruta: Path, *, logger: logging.Logger | None = None) -> None:
    """Abre `config.toml` con la app asociada del SO; lo crea si no existe (RF-34)."""
    log = logger or logging.getLogger("vigia_eew.tray")
    try:
        if not ruta.exists():
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(
                "# Generado por Vigía-eew — ver config.toml.example en el repo para\n"
                "# todas las opciones disponibles.\n",
                encoding="utf-8",
            )
        comando = _comando_abrir(ruta)
        if comando is None:
            os.startfile(ruta)  # type: ignore[attr-defined]  # solo existe en Windows
        else:
            subprocess.Popen(comando)
    except OSError as exc:
        log.warning("tray_no_pudo_abrir_config detalle=%s", exc)


def construir_icono(
    *,
    estado: EstadoAgente,
    pausado: Callable[[], bool],
    alternar_pausa: Callable[[], None],
    editar_config: Callable[[], None],
    salir: Callable[[], None],
    ruta_icono: Path | None = None,
) -> Icon:
    """Arma el `pystray.Icon` con su menú; no lo arranca (ver `IconoBandeja`)."""
    imagen = Image.open(ruta_icono or ruta_icono_predeterminada())

    def _texto_estado(_item: MenuItem) -> str:
        return f"WS: {'conectado' if estado.ws_conectado else 'reconectando…'}"

    def _texto_ultima_alerta(_item: MenuItem) -> str:
        return estado.ultima_alerta or "Sin alertas todavía"

    def _texto_pausa(_item: MenuItem) -> str:
        return "Reanudar notificaciones" if pausado() else "Pausar notificaciones"

    menu = Menu(
        MenuItem(_texto_estado, action=None, enabled=False),
        MenuItem(_texto_ultima_alerta, action=None, enabled=False),
        Menu.SEPARATOR,
        MenuItem(_texto_pausa, action=lambda icon, item: alternar_pausa()),
        MenuItem("Editar configuración...", action=lambda icon, item: editar_config()),
        Menu.SEPARATOR,
        MenuItem("Salir", action=lambda icon, item: salir()),
    )
    return Icon("vigia-eew", icon=imagen, title="Vigía-eew", menu=menu)


class IconoBandeja:
    """Corre el `pystray.Icon` en un hilo de trabajo aparte (mejor esfuerzo)."""

    def __init__(self, icono: Icon, *, logger: logging.Logger | None = None) -> None:
        self._icono = icono
        self._hilo: threading.Thread | None = None
        self._log = logger or logging.getLogger("vigia_eew.tray")

    def iniciar(self) -> None:
        """Arranca el ícono en un hilo aparte."""
        self._hilo = threading.Thread(target=self._ejecutar, daemon=True)
        self._hilo.start()

    def _ejecutar(self) -> None:
        # Corre en el hilo del ícono: cualquier fallo del backend gráfico (sin
        # display, GNOME/Wayland sin extensión, etc.) se loguea aquí y no se
        # propaga — el agente sigue funcionando sin ícono (RF-34).
        try:
            self._icono.run()
        except Exception as exc:  # noqa: BLE001 - mejor esfuerzo deliberado
            self._log.warning("tray_error_en_ejecucion tipo=%s detalle=%s", type(exc).__name__, exc)

    def detener(self) -> None:
        """Detiene el ícono y espera a que su hilo termine."""
        try:
            self._icono.stop()
        except Exception as exc:  # noqa: BLE001 - no debe impedir el cierre del agente
            self._log.warning("tray_error_al_detener tipo=%s detalle=%s", type(exc).__name__, exc)
        if self._hilo is not None:
            self._hilo.join(timeout=2.0)
