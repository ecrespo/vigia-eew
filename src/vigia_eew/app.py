"""Ensamblaje del agente (RF-26, RF-21; concurrencia ADR-006).

`Aplicacion` cablea todas las capas en un agente ejecutable:

  ingestión (WS + REST) → cola asyncio → procesador (normaliza/filtra/dedup)
  → puente asyncio↔Tk → controlador de alertas (ventana + sonido + toast).

Sigue el modelo de concurrencia del ADR-006: **Tkinter en el hilo principal** y el
bucle **asyncio en un hilo de trabajo**; los eventos cruzan por `PuenteAsyncioTk`.

  - `ejecutar()`: agente completo (ingestión real + notificación).
  - `simular()`: inyecta el evento simulado en la capa de notificación, sin red (RF-21).

Las partes con lógica (selección de tareas del supervisor, construcción del controlador)
se aíslan en métodos testeables; el arranque de hilos/GUI es glue de integración.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Any

from . import geoloc
from .config import Referencia, Settings
from .ingest import RawMessage
from .ingest.rest_usgs import RESTReconciler
from .ingest.ws_emsc import WSIngestor
from .logging_conf import configurar_logging
from .models import SeismicEvent, Severidad
from .notify.controlador import ControladorAlertas
from .notify.presentacion import DatosAlerta
from .notify.queue import PuenteAsyncioTk
from .notify.sound import SoundPlayer
from .notify.toast import Toaster
from .pipeline.dedup import Deduplicator
from .pipeline.filtro import GeoFilter
from .pipeline.normalize import Normalizer
from .pipeline.procesador import Procesador
from .simulacion import evento_simulado
from .state import StateStore
from .supervisor import Supervisor

_VentanaFactory = Callable[[DatosAlerta, Severidad, Callable[[], None]], Any]


class Aplicacion:
    """Construye y ejecuta el agente Vigía (modo completo o `--simulate`)."""

    def __init__(
        self,
        cfg: Settings,
        *,
        estado: StateStore | None = None,
        logger: logging.Logger | None = None,
        referencia_manual: bool = True,
        detectar_ubicacion: Callable[[], Referencia | None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.estado = estado or StateStore()
        self._log = logger or logging.getLogger("vigia_eew.app")
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sup: Supervisor | None = None
        self._root: Any = None
        self._ctrl: ControladorAlertas | None = None
        self._salir_al_vaciar = False
        self._referencia_manual = referencia_manual
        self._detectar_ubicacion = detectar_ubicacion or geoloc.detectar_ubicacion_ip

    # --- Wiring testeable ---

    def _construir_supervisor(
        self, raw_queue: asyncio.Queue[RawMessage], procesador: Any
    ) -> Supervisor:
        """Registra las tareas del agente según las fuentes habilitadas (RNF-04)."""
        sup = Supervisor(manejar_senales=False)  # las señales las maneja el hilo principal
        if self.cfg.fuentes_emsc.habilitado:
            sup.add("ws", lambda: WSIngestor(self.cfg.fuentes_emsc, raw_queue).run())
        if self.cfg.fuentes_usgs.habilitado:
            sup.add(
                "rest",
                lambda: RESTReconciler(
                    self.cfg.fuentes_usgs,
                    self.cfg.referencia,
                    self.cfg.filtro,
                    self.estado,
                    raw_queue,
                ).run(),
            )
        sup.add("pipeline", lambda: procesador.run())
        return sup

    def _construir_controlador(
        self,
        crear_ventana: _VentanaFactory,
        *,
        reproducir: Callable[[Severidad], None] | None = None,
        publicar_toast: Callable[[SeismicEvent], None] | None = None,
    ) -> ControladorAlertas:
        """Crea el controlador de alertas con los efectos inyectados."""
        ctrl = ControladorAlertas(
            crear_ventana=crear_ventana,
            reproducir_sonido=reproducir,
            enviar_toast=publicar_toast,
            al_reconocer=self._tras_reconocer,
            nombre_referencia=self.cfg.referencia.nombre,
        )
        self._ctrl = ctrl
        return ctrl

    def _tras_reconocer(self, _ev: SeismicEvent) -> None:
        """Tras reconocer: si la cola quedó vacía y procede, cierra la app (simulate)."""
        if (
            self._salir_al_vaciar
            and self._ctrl is not None
            and self._ctrl.cola.actual is None
            and self._ctrl.cola.pendientes == 0
            and self._root is not None
        ):
            self._root.after(150, self._root.quit)

    # --- Construcción de la GUI real ---

    def _preparar(self, *, resolver_ubicacion: bool = False) -> None:
        configurar_logging(self.cfg.logging)
        self.estado.cargar()
        if resolver_ubicacion and not self._referencia_manual:
            self._resolver_referencia_automatica()

    def _resolver_referencia_automatica(self) -> None:
        """Resuelve el punto de referencia por IP cuando no hay `[referencia]` manual (RF-33)."""
        cacheada = self.estado.ubicacion_cacheada()
        if cacheada is not None:
            self.cfg.referencia = cacheada
            self._log.info("ubicacion_ip_cache nombre=%s", cacheada.nombre)
            return
        detectada = self._detectar_ubicacion()
        if detectada is None:
            self._log.warning("ubicacion_ip_fallback_default")
            return
        self.cfg.referencia = detectada
        self.estado.cachear_ubicacion(detectada)
        self.estado.guardar()
        self._log.info("ubicacion_ip_detectada nombre=%s", detectada.nombre)

    def _nuevo_root(self) -> Any:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()  # root oculto; cada alerta es un Toplevel
        self._root = root
        return root

    def _controlador_para_gui(self, root: Any, *, modo_loop: bool) -> ControladorAlertas:
        import tkinter as tk

        from .notify.alert_window import AlertWindow

        sound = SoundPlayer(habilitado=self.cfg.notificacion.sonido)
        toaster = Toaster(nombre_referencia=self.cfg.referencia.nombre)

        def crear_ventana(
            datos: DatosAlerta, severidad: Severidad, al_reconocer: Callable[[], None]
        ) -> AlertWindow:
            return AlertWindow(
                datos,
                al_reconocer=al_reconocer,
                raiz=tk.Toplevel(root),
                pantalla_completa=self.cfg.notificacion.pantalla_completa,
            )

        def reproducir(severidad: Severidad) -> None:
            threading.Thread(target=sound.reproducir, args=(severidad,), daemon=True).start()

        def publicar_toast(ev: SeismicEvent) -> None:
            if modo_loop and self._loop is not None:
                asyncio.run_coroutine_threadsafe(toaster.notificar(ev), self._loop)
            else:
                threading.Thread(
                    target=lambda: asyncio.run(toaster.notificar(ev)), daemon=True
                ).start()

        reproducir_fn = reproducir if self.cfg.notificacion.sonido else None
        return self._construir_controlador(
            crear_ventana, reproducir=reproducir_fn, publicar_toast=publicar_toast
        )

    # --- Modos de ejecución ---

    def simular(self) -> None:
        """Inyecta el evento simulado y muestra la alerta hasta reconocerla (RF-21)."""
        self._preparar()
        self._salir_al_vaciar = True
        root = self._nuevo_root()
        ctrl = self._controlador_para_gui(root, modo_loop=False)
        ctrl.encolar(evento_simulado(self.cfg.referencia, self.cfg.severidad))
        self._log.info("simulacion_iniciada")
        root.mainloop()

    def ejecutar(self) -> None:
        """Arranca el agente completo: ingestión + pipeline + notificación (CU-1, CU-2)."""
        self._preparar(resolver_ubicacion=True)
        root = self._nuevo_root()
        ctrl = self._controlador_para_gui(root, modo_loop=True)
        puente = PuenteAsyncioTk(sink=ctrl.encolar)
        puente.iniciar_sondeo(root, intervalo_ms=100)
        hilo = threading.Thread(target=self._correr_loop, args=(puente,), daemon=True)
        hilo.start()
        self._log.info("agente_iniciado")
        try:
            root.mainloop()
        except KeyboardInterrupt:
            self._log.info("interrupcion_teclado")
        finally:
            self._detener(hilo)

    def _correr_loop(self, puente: PuenteAsyncioTk) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        raw_queue: asyncio.Queue[RawMessage] = asyncio.Queue()
        procesador = Procesador(
            raw_queue,
            Normalizer(self.cfg.referencia, self.cfg.severidad),
            GeoFilter(self.cfg.filtro),
            Deduplicator(self.cfg.dedup, self.estado),
            al_alertar=puente.publicar,
            al_actualizar=puente.publicar,
        )
        sup = self._construir_supervisor(raw_queue, procesador)
        self._sup = sup
        try:
            loop.run_until_complete(sup.run())
        except Exception as exc:  # noqa: BLE001 - registrar cualquier fallo del bucle
            self._log.warning("loop_error tipo=%s detalle=%s", type(exc).__name__, exc)
        finally:
            loop.close()

    def _detener(self, hilo: threading.Thread) -> None:
        """Cierre coordinado: para el supervisor y espera al hilo asyncio."""
        if self._loop is not None and self._sup is not None:
            self._loop.call_soon_threadsafe(self._sup.solicitar_parada)
        hilo.join(timeout=5.0)
        if self._root is not None:
            try:
                self._root.destroy()
            except Exception:  # noqa: BLE001 - el root puede estar ya destruido
                pass
