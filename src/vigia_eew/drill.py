"""The scheduled drill: when one is due, and the task that asks (ADR-040).

It is testing the smoke detector. An agent that goes months without alerting
has no other way to show that it still can, on this machine, with this
desktop -- and the day it matters is the wrong day to find out.

`is_due` is the whole decision and is pure. `DrillScheduler` wakes, asks, and
**offers**: whether the drill is actually shown is not decided here. The
alert queue refuses it while notifications are paused or a real alert is on
screen or waiting (REQ-UX-009), and a refused drill simply stays due until
the next wake.

This module knows nothing about alerts, queues or screens -- it imports none
of the package -- which is what lets a month pass in a test.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

#: Seconds between two looks at whether a drill is due. Hourly: a drill is
#: presented within an hour of falling due, which is all "every thirty days"
#: needs, and the task costs nothing in between.
CHECK_EVERY_S = 3600.0

#: Seconds before the first look after the agent starts. Not zero: a drill
#: that is due should not be the first thing a session shows, in the same
#: second the desktop is still coming up.
FIRST_CHECK_S = 60.0


def is_due(last: datetime | None, now: datetime, interval_days: int) -> bool:
    """Whether a drill should be presented, given when the last one was.

    With no drill ever, the first is due: somebody switched this on, and the
    first drill is the proof they asked for. A last drill *later* than now is
    a clock that was set back, and is not due -- otherwise every wake would
    fire one until the clock caught up.
    """
    if last is None:
        return True
    return now - last >= timedelta(days=interval_days)


class DrillScheduler:
    """Wakes hourly and offers a drill when one is due.

    Supervised like every other task of the agent, which is why it is one:
    a timer on the UI thread would be neither restarted nor shut down.
    """

    def __init__(
        self,
        *,
        interval_days: int,
        last_drill: Callable[[], datetime | None],
        offer: Callable[[], object],
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        self._interval_days = interval_days
        self._last_drill = last_drill
        self._offer = offer
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep = sleep
        self._log = logger or logging.getLogger("vigia_eew.drill")

    def check(self) -> bool:
        """Offers a drill if one is due; says whether it did."""
        if not is_due(self._last_drill(), self._now(), self._interval_days):
            return False
        self._log.info("drill_due interval_days=%d", self._interval_days)
        try:
            self._offer()
        except Exception as exc:  # noqa: BLE001 - a drill that cannot be shown is not fatal
            self._log.warning("drill_offer_failed type=%s detail=%s", type(exc).__name__, exc)
        return True

    async def run(self) -> None:
        """Until cancelled: wait, look, and wait again."""
        await self._sleep(FIRST_CHECK_S)
        while True:
            self.check()
            await self._sleep(CHECK_EVERY_S)
