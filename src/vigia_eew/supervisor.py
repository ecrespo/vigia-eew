"""Asyncio orchestrator — "supervisor that restarts children" pattern (RNF-03, RNF-04).

`Supervisor` keeps a set of long-lived tasks alive (WS ingestion, USGS polling, and,
in later phases, the pipeline). Each task runs inside a *guard* that captures its
exceptions, logs them, and **restarts it with backoff** without bringing down the
process or affecting the others (fault isolation, TECHNICAL-DESIGN §3).

Shutdown is **clean**: `request_stop()` (or SIGINT/SIGTERM) cancels the live tasks
and waits for them to finish. The backoff `sleep` is injected for deterministic tests.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from typing import Any

from .backoff import exponential_backoff

# A registered task is a factory that produces the coroutine to supervise.
Factory = Callable[[], Awaitable[Any]]
_SleepFn = Callable[[float], Any]


class Supervisor:
    """Supervises asyncio tasks, restarting them on failure; coordinated shutdown."""

    def __init__(
        self,
        *,
        sleep: _SleepFn = asyncio.sleep,
        backoff_cap: float = 60.0,
        jitter: bool = True,
        rng: Callable[[], float] | None = None,
        handle_signals: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self._tasks: list[tuple[str, Factory]] = []
        self._sleep = sleep
        self._backoff_cap = backoff_cap
        self._jitter = jitter
        self._rng = rng
        self._handle_signals = handle_signals
        self._log = logger or logging.getLogger("vigia_eew.supervisor")
        self._stop = asyncio.Event()

    def add(self, name: str, factory: Factory) -> None:
        """Registers a long-lived task under a readable name."""
        self._tasks.append((name, factory))

    @property
    def names(self) -> list[str]:
        """Names of the registered tasks (in registration order)."""
        return [name for name, _ in self._tasks]

    def request_stop(self) -> None:
        """Requests an orderly shutdown of the supervisor and its tasks."""
        self._stop.set()

    async def run(self) -> None:
        """Starts and supervises all tasks until a stop is requested."""
        self._stop.clear()
        guards = [
            asyncio.create_task(self._guard(name, factory), name=name)
            for name, factory in self._tasks
        ]
        self._install_signal_handlers()
        try:
            await self._stop.wait()
        finally:
            for g in guards:
                g.cancel()
            await asyncio.gather(*guards, return_exceptions=True)
            self._remove_signal_handlers()
            self._log.info("supervisor_stopped")

    async def _guard(self, name: str, factory: Factory) -> None:
        """Keeps a task alive: restarts it with backoff on failure or completion."""
        attempt = 0
        while not self._stop.is_set():
            try:
                await factory()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - deliberate isolation (RNF-03)
                self._log.warning(
                    "task_failed name=%s type=%s detail=%s", name, type(exc).__name__, exc
                )
            else:
                self._log.warning("task_ended name=%s (restarting)", name)
            if self._stop.is_set():
                break
            attempt += 1
            wait = self._backoff(attempt)
            self._log.info(
                "task_restarting name=%s attempt=%d wait_s=%.1f", name, attempt, wait
            )
            await self._sleep(wait)

    def _backoff(self, attempt: int) -> float:
        kwargs: dict[str, Any] = {"cap": self._backoff_cap, "jitter": self._jitter}
        if self._rng is not None:
            kwargs["rng"] = self._rng
        return exponential_backoff(attempt, **kwargs)

    def _install_signal_handlers(self) -> None:
        """Installs SIGINT/SIGTERM handlers for a clean shutdown (best-effort)."""
        if not self._handle_signals:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.request_stop)
            except (NotImplementedError, RuntimeError, ValueError):
                # add_signal_handler is not supported on some OSes (e.g. Windows).
                self._log.debug("signal_not_supported sig=%s", sig)

    def _remove_signal_handlers(self) -> None:
        if not self._handle_signals:
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
