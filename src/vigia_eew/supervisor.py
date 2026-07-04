"""Orquestador asyncio — patrón "supervisor que reinicia hijos" (RNF-03, RNF-04).

`Supervisor` mantiene vivas un conjunto de tareas de larga vida (ingestión WS, polling
USGS y, en fases posteriores, el pipeline). Cada tarea se ejecuta dentro de un *guard*
que captura sus excepciones, las registra y la **reinicia con backoff** sin tumbar el
proceso ni afectar a las demás (aislamiento de fallos, TECHNICAL-DESIGN §3).

El cierre es **limpio**: `solicitar_parada()` (o SIGINT/SIGTERM) cancela las tareas vivas
y espera su finalización. El `sleep` del backoff se inyecta para pruebas deterministas.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from typing import Any

from .backoff import exponential_backoff

# Una tarea registrada es una factoría que produce la corrutina a supervisar.
Factoria = Callable[[], Awaitable[Any]]
_SleepFn = Callable[[float], Any]


class Supervisor:
    """Supervisa tareas asyncio reiniciándolas ante fallos; cierre coordinado."""

    def __init__(
        self,
        *,
        sleep: _SleepFn = asyncio.sleep,
        backoff_tope: float = 60.0,
        jitter: bool = True,
        rng: Callable[[], float] | None = None,
        manejar_senales: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self._tareas: list[tuple[str, Factoria]] = []
        self._sleep = sleep
        self._backoff_tope = backoff_tope
        self._jitter = jitter
        self._rng = rng
        self._manejar_senales = manejar_senales
        self._log = logger or logging.getLogger("vigia_eew.supervisor")
        self._parar = asyncio.Event()

    def add(self, nombre: str, factoria: Factoria) -> None:
        """Registra una tarea de larga vida bajo un nombre legible."""
        self._tareas.append((nombre, factoria))

    @property
    def nombres(self) -> list[str]:
        """Nombres de las tareas registradas (en orden de registro)."""
        return [nombre for nombre, _ in self._tareas]

    def solicitar_parada(self) -> None:
        """Pide el cierre ordenado del supervisor y sus tareas."""
        self._parar.set()

    async def run(self) -> None:
        """Arranca y supervisa todas las tareas hasta que se solicite la parada."""
        self._parar.clear()
        guards = [
            asyncio.create_task(self._guard(nombre, factoria), name=nombre)
            for nombre, factoria in self._tareas
        ]
        self._instalar_senales()
        try:
            await self._parar.wait()
        finally:
            for g in guards:
                g.cancel()
            await asyncio.gather(*guards, return_exceptions=True)
            self._remover_senales()
            self._log.info("supervisor_detenido")

    async def _guard(self, nombre: str, factoria: Factoria) -> None:
        """Mantiene viva una tarea: la reinicia con backoff ante fallo o término."""
        intento = 0
        while not self._parar.is_set():
            try:
                await factoria()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - aislamiento deliberado (RNF-03)
                self._log.warning(
                    "tarea_fallo nombre=%s tipo=%s detalle=%s", nombre, type(exc).__name__, exc
                )
            else:
                self._log.warning("tarea_termino nombre=%s (se reinicia)", nombre)
            if self._parar.is_set():
                break
            intento += 1
            espera = self._backoff(intento)
            self._log.info(
                "tarea_reinicia nombre=%s intento=%d espera_s=%.1f", nombre, intento, espera
            )
            await self._sleep(espera)

    def _backoff(self, intento: int) -> float:
        kwargs: dict[str, Any] = {"tope": self._backoff_tope, "jitter": self._jitter}
        if self._rng is not None:
            kwargs["rng"] = self._rng
        return exponential_backoff(intento, **kwargs)

    def _instalar_senales(self) -> None:
        """Instala manejadores SIGINT/SIGTERM para un cierre limpio (best-effort)."""
        if not self._manejar_senales:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.solicitar_parada)
            except (NotImplementedError, RuntimeError, ValueError):
                # add_signal_handler no está soportado en algunos SO (p. ej. Windows).
                self._log.debug("senal_no_soportada sig=%s", sig)

    def _remover_senales(self) -> None:
        if not self._manejar_senales:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.remove_signal_handler(sig)
            except (NotImplementedError, RuntimeError, ValueError):
                pass
