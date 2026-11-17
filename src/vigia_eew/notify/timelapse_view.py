"""The playback's controls: play, pause, seek, speed, trail (REQ-TLP-002/003/007).

The half that paints. What a step shows was decided by `timelapse.Timeline`,
which needs no screen; this module asks it for a frame and hands the frame to
a painter, and holds the controls around that
([[lat.md/history#The playback steps by earthquake, and a frame depends only on its step]]).

It advances by asking the shell's timer for the next step, one at a time,
each after as long as the timeline says that step should stay. There is no
loop and no clock of its own. Pausing does not cancel the step already asked
for -- the timer cannot take one back -- it makes it stale: every play, pause,
seek and reload starts a new generation, and a step that comes due under an
old one does nothing.

It holds a painter, not the map. So it has no way to pan or zoom anything,
which is the point: a playback that wandered the map on its own would fetch
tiles nobody decided to fetch (REQ-TLP-008).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import flet as ft

from vigia_eew.history import EventRecord
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify.presentation import VENEZUELA_ZONE, format_moment
from vigia_eew.notify.timelapse import SPEEDS, Frame, Timeline

#: The speed a playback opens at: a day of history per second of viewing.
DEFAULT_SPEED = "day"

Painter = Callable[[Frame], None]
#: `FletShell.after`: run that on the UI loop in so many milliseconds.
Timer = Callable[[int, Callable[[], Any]], Any]


class TimelapseView:
    """A row of controls under the map, and the stepping behind them.

    `paint` draws a frame; `after` is the shell's timer; `on_stop` is told
    when the user lets go of the playback, so that whoever owns the map can
    draw the whole set on it again.

    `step` is None until the playback has painted something: until then the
    map is not its to draw on.
    """

    def __init__(
        self,
        *,
        paint: Painter,
        after: Timer,
        on_stop: Callable[[], None] | None = None,
        locale_code: str = DEFAULT_LOCALE,
        zone: str = VENEZUELA_ZONE,
    ) -> None:
        self._paint = paint
        self._after = after
        self._on_stop = on_stop
        self._locale = locale_code
        self._zone = zone
        self._generation = 0
        self._trail = False
        self._speed = DEFAULT_SPEED
        self.timeline = Timeline([])
        self._records: Sequence[EventRecord] = ()
        self.step: int | None = None
        self.playing = False

        loc = locale_code
        self.play_button = ft.IconButton(
            icon=ft.Icons.PLAY_ARROW,
            tooltip=t("timelapse_play", loc),
            on_click=lambda _e: self.toggle(),
        )
        self.stop_button = ft.IconButton(
            icon=ft.Icons.STOP,
            tooltip=t("timelapse_stop", loc),
            on_click=lambda _e: self.stop(),
        )
        self.slider = ft.Slider(
            min=0, max=1, value=0, expand=True, on_change=lambda _e: self._slid()
        )
        self.speed_control = ft.Dropdown(
            label=t("timelapse_speed", loc),
            value=DEFAULT_SPEED,
            dense=True,
            width=150,
            options=[
                ft.DropdownOption(key=key, text=t(f"timelapse_speed_{key}", loc)) for key in SPEEDS
            ],
            on_select=lambda _e: self._speed_chosen(),
        )
        self.trail_switch = ft.Switch(
            label=t("timelapse_trail", loc), value=False, on_change=lambda _e: self._trail_set()
        )
        #: The instant of the frame on screen, in the configured zone.
        self.instant = ft.Text("", size=13, weight=ft.FontWeight.BOLD)
        #: The period the playback spans -- or that there is nothing to play.
        self.period = ft.Text("", size=12)
        #: Says so when the set is larger than what is played (CA-116.11).
        self.notice = ft.Text("", size=11, italic=True, visible=False)
        self.view = ft.Column(
            spacing=2,
            controls=[
                ft.Row(
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[self.play_button, self.stop_button, self.slider],
                ),
                ft.Row(
                    spacing=12,
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[self.speed_control, self.trail_switch, self.instant, self.period],
                ),
                self.notice,
            ],
        )
        self._sync()

    # --- The set ---

    def load(self, records: Sequence[EventRecord], *, total: int | None = None) -> None:
        """Replaces the set being played, and lets go of the map.

        Called when the filter changes: what was playing is no longer what the
        filter selects (REQ-TLP-004). `total` is how many the filter matches;
        when it is more than `records`, the notice says how many are played.
        """
        self._halt()
        self._records = records
        self.timeline = Timeline(records, trail=self._trail)
        self.step = None
        cut_short = total is not None and total > len(records)
        self.notice.visible = cut_short
        self.notice.value = (
            t("timelapse_truncated", self._locale, shown=len(records), total=total)
            if cut_short
            else ""
        )
        self._sync()

    # --- What the user does ---

    @property
    def engaged(self) -> bool:
        """Whether the map is showing a frame of the playback rather than the set."""
        return self.step is not None

    def toggle(self) -> None:
        if self.playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        """Plays from the step it is on, or from the start when it is at the end."""
        steps = len(self.timeline)
        if steps == 0 or self.playing:
            return
        at_the_end = self.step is not None and self.step >= steps - 1
        start = 0 if self.step is None or at_the_end else self.step
        self._halt()
        self.playing = True
        self._show(start)
        self._schedule()

    def pause(self) -> None:
        """Stops advancing. What is on the map stays as it is (CA-116.3)."""
        self._halt()
        self._sync()

    def seek(self, step: int) -> None:
        """Shows that step. If it was playing, it carries on from there."""
        if not 0 <= step < len(self.timeline):
            return
        was_playing = self.playing
        self._halt()
        self.playing = was_playing
        self._show(step)
        if was_playing:
            self._schedule()

    def stop(self) -> None:
        """Lets go of the map: the whole set is drawn on it again."""
        self._halt()
        self.step = None
        self._sync()
        if self._on_stop is not None:
            self._on_stop()

    # --- Stepping ---

    def _halt(self) -> None:
        """Makes whatever step is pending stale, and stops."""
        self._generation += 1
        self.playing = False

    def _schedule(self) -> None:
        assert self.step is not None
        generation = self._generation
        seconds = self.timeline.dwell(self.step, SPEEDS[self._speed])
        self._after(round(seconds * 1000), lambda: self._advance(generation))

    def _advance(self, generation: int) -> None:
        """The step asked for has come due -- unless something happened since."""
        if generation != self._generation or not self.playing or self.step is None:
            return
        if self.step >= len(self.timeline) - 1:
            self.playing = False  # the last frame has had its time
            self._sync()
            return
        self._show(self.step + 1)
        self._schedule()

    def _show(self, step: int) -> None:
        """Paints one frame. The only place a frame reaches the painter."""
        self.step = step
        frame = self.timeline.frame(step)
        self._paint(frame)
        self.instant.value = format_moment(frame.instant, self._zone)
        self._sync()

    # --- The controls ---

    def _slid(self) -> None:
        self.seek(round(self.slider.value or 0))

    def _speed_chosen(self) -> None:
        """Changes how long the next steps stay; what they show is untouched."""
        if self.speed_control.value in SPEEDS:
            self._speed = self.speed_control.value

    def _trail_set(self) -> None:
        """Old earthquakes stay at their weakest, or go. Same set, same step."""
        self._trail = bool(self.trail_switch.value)
        self.timeline = Timeline(self._records, trail=self._trail)
        if self.step is not None:
            self.seek(self.step)

    def _sync(self) -> None:
        """Brings the controls in line with where the playback is."""
        steps = len(self.timeline)
        loc = self._locale
        self.play_button.disabled = steps == 0
        self.play_button.icon = ft.Icons.PAUSE if self.playing else ft.Icons.PLAY_ARROW
        self.play_button.tooltip = t("timelapse_pause" if self.playing else "timelapse_play", loc)
        self.stop_button.disabled = self.step is None
        self.slider.disabled = steps < 2
        self.slider.max = max(1, steps - 1)
        self.slider.divisions = steps - 1 if steps > 1 else None
        self.slider.value = self.step or 0
        if self.step is None:
            self.instant.value = ""
        period = self.timeline.period
        self.period.value = (
            t("timelapse_empty", loc)
            if period is None
            else f"{format_moment(period[0], self._zone)} – {format_moment(period[1], self._zone)}"
        )
