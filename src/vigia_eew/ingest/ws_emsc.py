"""Ingestor WebSocket EMSC — vía primaria de push (RF-01..RF-04, ADR-009).

`WSIngestor` mantiene viva una conexión al *standing order* de EMSC y publica cada
evento como `RawMessage` en la cola de salida. Responsabilidades:

  - **Keepalive** (RF-02): `ping_interval`/`ping_timeout` nativos de `websockets`;
    sin ellos el socket muere en silencio (API-SPEC §1.2).
  - **Reconexión perpetua** (RF-03): ante cierre o error, backoff exponencial + jitter
    (hasta `backoff_max_s`) y reintento; el backoff se reinicia al reconectar.
  - **Recepción** (RF-01/RF-04): parsea el JSON y encola el Feature crudo.

El transporte (`connect`) y el `sleep` se inyectan para poder probar el bucle sin red.
La salida del bucle es por `asyncio.CancelledError` (cierre limpio desde el Supervisor).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import websockets

from ..backoff import exponential_backoff
from ..config import FuenteEMSC
from . import RawMessage

# Factoría de conexión por defecto: el cliente real de `websockets`.
_ConnectFactory = Callable[..., Any]
_SleepFn = Callable[[float], Any]


class WSIngestor:
    """Mantiene la conexión WS de EMSC y publica `RawMessage` en `salida`."""

    def __init__(
        self,
        cfg: FuenteEMSC,
        salida: asyncio.Queue[RawMessage],
        *,
        connect: _ConnectFactory | None = None,
        sleep: _SleepFn = asyncio.sleep,
        jitter: bool = True,
        rng: Callable[[], float] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._salida = salida
        self._connect: _ConnectFactory = connect or websockets.connect
        self._sleep = sleep
        self._jitter = jitter
        self._rng = rng
        self._log = logger or logging.getLogger("vigia_eew.ingest.ws")

    def _parsear(self, raw: str | bytes) -> RawMessage | None:
        """Convierte un mensaje crudo en `RawMessage`; devuelve None si es inválido."""
        try:
            datos = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            self._log.warning("ws_json_invalido")
            return None
        feature = datos.get("data")
        if not isinstance(feature, dict):
            self._log.warning("ws_mensaje_sin_data")
            return None
        action = datos.get("action", "create")
        return RawMessage(fuente="EMSC", action=str(action), feature=feature)

    async def run(self) -> None:
        """Bucle de conexión/reconexión perpetua. Termina solo al ser cancelado."""
        intento = 0
        while True:
            try:
                conexion = self._connect(
                    self._cfg.url,
                    ping_interval=self._cfg.ping_interval_s,
                    ping_timeout=self._cfg.ping_timeout_s,
                )
                async with conexion as ws:
                    self._log.info("ws_conectado url=%s", self._cfg.url)
                    async for raw in ws:
                        # Reiniciar el backoff solo ante progreso real (mensaje
                        # recibido), no al abrir: así un socket que acepta y cierra
                        # en bucle no provoca reconexiones agresivas (RNF-03).
                        intento = 0
                        msg = self._parsear(raw)
                        if msg is not None:
                            await self._salida.put(msg)
            except asyncio.CancelledError:
                self._log.info("ws_cancelado")
                raise
            except Exception as exc:  # noqa: BLE001 - resiliencia deliberada (RNF-03)
                self._log.warning("ws_error tipo=%s detalle=%s", type(exc).__name__, exc)

            intento += 1
            espera = self._backoff(intento)
            self._log.info("ws_reconectando intento=%d espera_s=%.1f", intento, espera)
            await self._sleep(espera)

    def _backoff(self, intento: int) -> float:
        kwargs: dict[str, Any] = {
            "tope": float(self._cfg.backoff_max_s),
            "jitter": self._jitter,
        }
        if self._rng is not None:
            kwargs["rng"] = self._rng
        return exponential_backoff(intento, **kwargs)
