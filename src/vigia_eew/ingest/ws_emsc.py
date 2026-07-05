"""EMSC WebSocket ingestor — primary push channel (RF-01..RF-04, ADR-009).

`WSIngestor` keeps a connection to EMSC's *standing order* alive and publishes
each event as a `RawMessage` on the output queue. Responsibilities:

  - **Keepalive** (RF-02): `ping_interval`/`ping_timeout` native to `websockets`;
    without them the socket dies silently (API-SPEC §1.2).
  - **Perpetual reconnection** (RF-03): on close or error, exponential backoff +
    jitter (up to `backoff_max_s`) and retry; the backoff resets on reconnect.
  - **Reception** (RF-01/RF-04): parses the JSON and enqueues the raw Feature.

The transport (`connect`) and `sleep` are injected so the loop can be tested without
network. The loop exits via `asyncio.CancelledError` (clean shutdown from the
Supervisor).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import websockets

from vigia_eew.agent_state import AgentState
from vigia_eew.backoff import exponential_backoff
from vigia_eew.config import EMSCSource
from vigia_eew.ingest import RawMessage

# Default connection factory: the real `websockets` client.
_ConnectFactory = Callable[..., Any]
_SleepFn = Callable[[float], Any]


class WSIngestor:
    """Keeps the EMSC WS connection alive and publishes `RawMessage` onto `output`."""

    def __init__(
        self,
        cfg: EMSCSource,
        output: asyncio.Queue[RawMessage],
        *,
        connect: _ConnectFactory | None = None,
        sleep: _SleepFn = asyncio.sleep,
        jitter: bool = True,
        rng: Callable[[], float] | None = None,
        state: AgentState | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._output = output
        self._connect: _ConnectFactory = connect or websockets.connect
        self._sleep = sleep
        self._jitter = jitter
        self._rng = rng
        self._state = state
        self._log = logger or logging.getLogger("vigia_eew.ingest.ws")

    def _parse(self, raw: str | bytes) -> RawMessage | None:
        """Converts a raw message into a `RawMessage`; returns None if invalid."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            self._log.warning("ws_invalid_json")
            return None
        feature = data.get("data")
        if not isinstance(feature, dict):
            self._log.warning("ws_message_without_data")
            return None
        action = data.get("action", "create")
        return RawMessage(source="EMSC", action=str(action), feature=feature)

    async def run(self) -> None:
        """Perpetual connect/reconnect loop. Only exits when cancelled."""
        attempt = 0
        while True:
            try:
                connection = self._connect(
                    self._cfg.url,
                    ping_interval=self._cfg.ping_interval_s,
                    ping_timeout=self._cfg.ping_timeout_s,
                )
                async with connection as ws:
                    self._log.info("ws_connected url=%s", self._cfg.url)
                    if self._state is not None:
                        self._state.mark_connected()
                    async for raw in ws:
                        # Reset the backoff only on real progress (message
                        # received), not on open: this way a socket that accepts
                        # and closes in a loop doesn't cause aggressive
                        # reconnections (RNF-03).
                        attempt = 0
                        msg = self._parse(raw)
                        if msg is not None:
                            await self._output.put(msg)
            except asyncio.CancelledError:
                self._log.info("ws_cancelled")
                raise
            except Exception as exc:  # noqa: BLE001 - deliberate resilience (RNF-03)
                self._log.warning("ws_error type=%s detail=%s", type(exc).__name__, exc)

            if self._state is not None:
                self._state.mark_reconnecting()
            attempt += 1
            wait = self._backoff(attempt)
            self._log.info("ws_reconnecting attempt=%d wait_s=%.1f", attempt, wait)
            await self._sleep(wait)

    def _backoff(self, attempt: int) -> float:
        kwargs: dict[str, Any] = {
            "cap": float(self._cfg.backoff_max_s),
            "jitter": self._jitter,
        }
        if self._rng is not None:
            kwargs["rng"] = self._rng
        return exponential_backoff(attempt, **kwargs)
