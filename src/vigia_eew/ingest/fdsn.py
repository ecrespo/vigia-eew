"""Common shape of the FDSN catalogue pollers (RF-05, RF-39; API-SPEC §2, §4).

USGS and GEOFON are the same kind of adapter: an `fdsnws-event` catalogue
polled on an interval, from a persisted cursor, into the raw queue. They speak
different dialects -- GeoJSON against pipe-delimited text -- but they are
constructed identically and their polling loops were identical, twenty-one and
fifteen duplicated lines respectively (code-audit P3-1).

This base holds what FDSN itself dictates and leaves each poller its own
`poll_once`. It is not a shared base for "the pollers": FUNVISIS is not FDSN
and does not inherit from it, because sharing a base with something that
merely resembles you is how an adapter ends up with fields it does not use.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

import httpx

from vigia_eew.config import Filter, ReferencePoint
from vigia_eew.ingest import RawMessage
from vigia_eew.state import StateStore
from vigia_eew.timeutil import Clock, default_clock

_SleepFn = Callable[[float], Any]


class FDSNPoller[CfgT]:
    """An FDSN catalogue polled from a persisted cursor.

    `CfgT` is the source's own configuration section; each poller narrows it.
    """

    #: Log channel for this source. A class attribute rather than a constructor
    #: argument: it is a property of the poller, not of the call, and every
    #: caller passing the same string is how they drift apart.
    LOGGER_NAME = "vigia_eew.ingest.fdsn"

    def __init__(
        self,
        cfg: CfgT,
        reference: ReferencePoint,
        filter_cfg: Filter,
        state: StateStore,
        output: asyncio.Queue[RawMessage],
        *,
        client: httpx.AsyncClient | None = None,
        sleep: _SleepFn = asyncio.sleep,
        timezone: str = "UTC",
        now: Clock = default_clock,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._reference = reference
        self._filter = filter_cfg
        self._state = state
        self._output = output
        self._client = client
        self._sleep = sleep
        self._timezone = timezone
        self._now = now
        self._log = logger or logging.getLogger(self.LOGGER_NAME)

    async def poll_once(self) -> float:
        """One poll; returns how many seconds to wait before the next."""
        raise NotImplementedError

    async def run(self) -> None:
        """Perpetual polling loop. Only exits when cancelled.

        The client is created here rather than in `__init__` so that it is
        bound to the loop that will use it -- the supervisor builds these on
        the worker thread, and an httpx client made on another loop is a
        problem that only shows up under load.
        """
        if self._client is None:
            self._client = httpx.AsyncClient()
        while True:
            wait = await self.poll_once()
            await self._sleep(wait)
