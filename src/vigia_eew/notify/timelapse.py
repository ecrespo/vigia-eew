"""The playback's timeline: what is visible at each step (REQ-TLP-001..007, ADR-035).

A static map of ninety days answers *where*. Playing it answers *in what
order* and *at what pace*, which no table conveys -- a swarm and an aftershock
sequence are the same dots until they are seen arriving.

**It advances by earthquake, not by a clock** (decision D-8). A step is the
next earthquake of the set; the map is redrawn when a step is taken and not in
between. Speed is only how long a step stays on screen.

This module is the half that decides, and it is pure: no toolkit, no clock, no
file ([[lat.md/history#The playback steps by earthquake, and a frame depends only on its step]]).
`frame(i)` is a function of *i* and nothing else, so seeking to an earthquake
and reaching it by playing cannot come to show different things -- they are
the same call. The control that paints a frame is `timelapse_view.py`.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from vigia_eew.history import EventRecord

#: The shortest and the longest a step stays on screen, in seconds, and how
#: many earthquakes a playback holds. **Measured**, not chosen: 400 markers
#: redraw in 86 ms (worst seen 110 ms), which leaves a third of the shortest
#: step for the controls to answer (docs/v1.1/10-SPIKE-TIMELAPSE.md §5).
#: `MAX_DWELL` is the one judgement among them: long enough for a quiet week
#: to read as quiet, short enough not to look stopped.
#:
#: Their product is the longest a full playback of clamped steps can take, and
#: it has to stay at or under a minute (REQ-TLP-007). If a slower machine
#: needs relief, lower the limit rather than raise the minimum.
MIN_DWELL = 0.15
MAX_DWELL = 2.0
PLAYBACK_SYMBOL_LIMIT = 400

#: How strongly a symbol is drawn as it ages, strongest first. A few discrete
#: levels rather than a curve: a curve would change between steps, and
#: changing between steps is a clock again (ADR-035).
LEVELS: tuple[float, ...] = (1.0, 0.7, 0.45, 0.25)

#: How long, in the history's own time, a symbol takes to fade out. A
#: judgement, not a measurement: over a month of a region's seismicity it
#: keeps a few days in view at once.
DEFAULT_FADE = timedelta(days=3)

#: The speeds on offer, as seconds of history per second of viewing: six
#: hours, a day, a week.
SPEEDS: dict[str, float] = {
    "six_hours": 6 * 3600.0,
    "day": 86_400.0,
    "week": 7 * 86_400.0,
}


@dataclass(frozen=True, slots=True)
class Frame:
    """What one step shows: its instant, and each visible earthquake's strength."""

    instant: datetime
    #: Earthquakes that happened at or before `instant` and have not faded
    #: out, oldest first, each with one of `LEVELS`.
    symbols: tuple[tuple[EventRecord, float], ...]


class Timeline:
    """The earthquakes of a set, as steps that can be played or sought.

    `fade` is how long a symbol takes to fade, in the history's time. With
    `trail` it stays at its weakest afterwards instead of disappearing.
    """

    def __init__(
        self,
        records: Sequence[EventRecord],
        *,
        fade: timedelta = DEFAULT_FADE,
        trail: bool = False,
    ) -> None:
        self._records = sorted(records, key=lambda record: (record.occurred_at, record.id or 0))
        self._occurred = [record.occurred_at for record in self._records]
        #: One step per distinct instant: earthquakes at the same instant
        #: appear together, since neither happened first.
        self._instants = sorted(set(self._occurred))
        self._fade = fade
        self._trail = trail

    def __len__(self) -> int:
        return len(self._instants)

    @property
    def period(self) -> tuple[datetime, datetime] | None:
        """The first and the last instant played, or None when there is nothing to play."""
        if not self._instants:
            return None
        return (self._instants[0], self._instants[-1])

    def frame(self, step: int) -> Frame:
        """What step `step` shows. Depends on the step and on nothing else."""
        instant = self._instant(step)
        happened = bisect_right(self._occurred, instant)
        symbols = []
        for record in self._records[:happened]:
            strength = self._strength(instant - record.occurred_at)
            if strength > 0.0:
                symbols.append((record, strength))
        return Frame(instant=instant, symbols=tuple(symbols))

    def dwell(self, step: int, speed: float) -> float:
        """Seconds step `step` stays on screen at that speed.

        The real gap to the next earthquake divided by the speed, held between
        `MIN_DWELL` and `MAX_DWELL`: a burst a second apart must still be seen,
        and a silent week must not look like a playback that stopped. The last
        step has no next one and stays the longest.
        """
        instant = self._instant(step)
        if step == len(self._instants) - 1:
            return MAX_DWELL
        gap = (self._instants[step + 1] - instant).total_seconds()
        return min(MAX_DWELL, max(MIN_DWELL, gap / speed))

    def step_at(self, instant: datetime) -> int:
        """The last step at or before an instant; the first one when it precedes them all."""
        return max(0, bisect_right(self._instants, instant) - 1)

    def _instant(self, step: int) -> datetime:
        if not 0 <= step < len(self._instants):
            raise IndexError(f"step {step} is not one of this timeline's {len(self._instants)}")
        return self._instants[step]

    def _strength(self, age: timedelta) -> float:
        """How strongly an earthquake of that age is drawn: 1 at age zero, never rising."""
        if age >= self._fade:
            return LEVELS[-1] if self._trail else 0.0
        return LEVELS[int(age / self._fade * len(LEVELS))]
