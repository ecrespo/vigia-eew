"""Ventana de alerta superpuesta no descartable en Tkinter (RF-15..RF-19, ADR-003).

La ventana es el corazón del "imposible de ignorar":

  - **Siempre al frente y sin decoración** (RF-15): `-topmost` + `overrideredirect`,
    overlay grande centrado (o pantalla completa según config).
  - **Toma el foco y se re-eleva** si lo pierde (RF-16): `focus_force` + `lift`,
    re-elevación al evento `<FocusOut>`.
  - **No se cierra por accidente** (RF-19): la X (`WM_DELETE_WINDOW`), `Escape` y el
    clic fuera no la cierran; solo el botón **RECONOCIDO** (cierre explícito).

La *política* no descartable (`configurar_no_descartable`) y `tomar_foco` se aíslan como
funciones para poder probarlas con una raíz falsa, sin pantalla. La construcción del árbol
de widgets usa Tkinter real y se valida con un smoke opt-in (`VIGIA_GUI_TESTS=1`).
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from typing import Any

from .presentacion import DatosAlerta, color_severidad


def tomar_foco(raiz: Any) -> None:
    """Eleva la ventana y le fuerza el foco (RF-16)."""
    raiz.lift()
    raiz.focus_force()


def configurar_no_descartable(raiz: Any, *, al_cerrar_intento: Callable[[], None]) -> None:
    """Aplica la política de ventana no descartable (RF-15, RF-16, RF-19)."""
    raiz.overrideredirect(True)  # sin barra de título ni botones de ventana
    raiz.attributes("-topmost", True)  # siempre por encima del resto
    raiz.protocol("WM_DELETE_WINDOW", al_cerrar_intento)  # la X no cierra
    raiz.bind("<Escape>", lambda _e: "break")  # Escape no cierra
    raiz.bind("<FocusOut>", lambda _e: tomar_foco(raiz))  # re-elevar si pierde foco


class AlertWindow:
    """Ventana de alerta para un evento; solo se cierra con RECONOCIDO (RF-19)."""

    def __init__(
        self,
        datos: DatosAlerta,
        *,
        al_reconocer: Callable[[], None],
        raiz: Any = None,
        pantalla_completa: bool = False,
        construir: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self._datos = datos
        self._al_reconocer = al_reconocer
        self._raiz: Any = raiz if raiz is not None else tk.Tk()
        self._pantalla_completa = pantalla_completa
        self._reconocido = False
        self._log = logger or logging.getLogger("vigia_eew.notify.alert_window")
        if construir:
            self._construir()

    @property
    def raiz(self) -> Any:
        return self._raiz

    def _intento_cierre(self) -> None:
        """Intento de cierre por la X/Escape: se ignora deliberadamente (RF-19)."""
        self._log.info("alerta_cierre_ignorado")

    def reconocer(self) -> None:
        """Reconoce la alerta (único cierre válido) y destruye la ventana (CU-5)."""
        if self._reconocido:
            return
        self._reconocido = True
        self._al_reconocer()
        self._raiz.destroy()

    def actualizar(self, datos: DatosAlerta) -> None:
        """Refresca los datos mostrados sin recrear la ventana (RF-11)."""
        self._datos = datos
        if not self._reconocido:
            self._construir()

    # --- Construcción de la UI (Tkinter real) ---

    def _construir(self) -> None:
        raiz = self._raiz
        color = color_severidad(self._datos.severidad)
        raiz.title("Vigía-eew · ALERTA SÍSMICA")
        configurar_no_descartable(raiz, al_cerrar_intento=self._intento_cierre)
        if self._pantalla_completa:
            raiz.attributes("-fullscreen", True)
        else:
            self._centrar(900, 620)
        raiz.configure(bg=color)

        for hijo in list(raiz.winfo_children()):
            hijo.destroy()

        tk.Label(
            raiz, text="⚠ ALERTA SÍSMICA", font=("Helvetica", 28, "bold"), fg="white", bg=color
        ).pack(pady=(28, 6))
        tk.Label(
            raiz, text=self._datos.magnitud, font=("Helvetica", 110, "bold"), fg="white", bg=color
        ).pack(pady=4)

        detalle = (
            f"{self._datos.lugar}\n"
            f"{self._datos.distancia}\n"
            f"Profundidad: {self._datos.profundidad}\n"
            f"Hora local (Venezuela): {self._datos.hora_local}\n"
            f"Fuente: {self._datos.fuente}"
        )
        tk.Label(
            raiz, text=detalle, font=("Helvetica", 22), fg="white", bg=color, justify="center"
        ).pack(pady=18)

        tk.Button(
            raiz,
            text="RECONOCIDO",
            font=("Helvetica", 24, "bold"),
            fg=color,
            bg="white",
            activeforeground=color,
            padx=40,
            pady=16,
            command=self.reconocer,
        ).pack(pady=(20, 30))

        tomar_foco(raiz)

    def _centrar(self, ancho: int, alto: int) -> None:
        raiz = self._raiz
        pantalla_w = raiz.winfo_screenwidth()
        pantalla_h = raiz.winfo_screenheight()
        x = (pantalla_w - ancho) // 2
        y = (pantalla_h - alto) // 2
        raiz.geometry(f"{ancho}x{alto}+{x}+{y}")
