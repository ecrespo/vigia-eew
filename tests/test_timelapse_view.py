"""Tests for the playback control (T-165, REQ-TLP-002/003/007, HU-116).

What is visible at a step is the timeline's business and is tested there. This
file is about the control around it: that playing takes one step per
earthquake, that pausing stops it, and that the instant is always in view.

The painter and the timer are injected, so a "playback" here is a list of the
frames that were painted and a queue of callbacks nobody has run yet.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vigia_eew.history import EventRecord
from vigia_eew.notify.timelapse import LEVELS, MAX_DWELL, MIN_DWELL, SPEEDS, Frame
from vigia_eew.notify.timelapse_view import TimelapseView

_START = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _quake(index: int, after: timedelta) -> EventRecord:
    return EventRecord(
        id=index,
        correlation_id=f"q{index}",
        source="EMSC",
        source_event_id=f"e{index}",
        occurred_at=_START + after,
        recorded_at=_START + after,
        latitude=10.0,
        longitude=-66.0,
        depth_km=10.0,
        magnitude=4.0,
        region=None,
        distance_km=50.0,
        verdict="discarded",
    )


def _forty() -> list[EventRecord]:
    """Forty earthquakes spread over ninety days."""
    return [_quake(i + 1, timedelta(days=90) * i / 39) for i in range(40)]


class _Timer:
    """Stands in for `FletShell.after`: queues, and runs on demand."""

    def __init__(self) -> None:
        self.pending: list[tuple[int, object]] = []
        self.delays: list[int] = []

    def __call__(self, ms: int, action) -> None:
        self.pending.append((ms, action))
        self.delays.append(ms)

    def tick(self) -> bool:
        """Runs the oldest pending callback; False when there is none."""
        if not self.pending:
            return False
        _ms, action = self.pending.pop(0)
        action()
        return True

    def run_out(self, limit: int = 1000) -> None:
        for _ in range(limit):
            if not self.tick():
                return
        raise AssertionError("the playback never stopped scheduling")


def _playback(records, **kwargs) -> tuple[TimelapseView, list[Frame], _Timer]:
    painted: list[Frame] = []
    timer = _Timer()
    view = TimelapseView(paint=painted.append, after=timer, locale_code="en", zone="UTC", **kwargs)
    view.load(records)
    return view, painted, timer


# --- Playing (CA-116.2) -------------------------------------------------------------


def test_playing_forty_earthquakes_paints_forty_frames() -> None:
    view, painted, timer = _playback(_forty())

    view.play()
    timer.run_out()

    assert len(painted) == 40
    assert [frame.instant for frame in painted] == sorted(frame.instant for frame in painted)
    assert view.playing is False
    assert view.step == 39


def test_nothing_is_painted_until_the_user_plays() -> None:
    view, painted, timer = _playback(_forty())

    assert painted == []
    assert timer.pending == []
    assert view.step is None


def test_each_step_waits_as_long_as_the_timeline_says() -> None:
    view, _painted, timer = _playback(_forty())

    view.play()
    timer.run_out()

    assert len(timer.delays) == 40
    assert all(MIN_DWELL * 1000 <= ms <= MAX_DWELL * 1000 for ms in timer.delays)
    assert timer.delays[-1] == MAX_DWELL * 1000  # the last frame stays before it ends


def test_playing_again_at_the_end_starts_over() -> None:
    view, painted, timer = _playback(_forty())
    view.play()
    timer.run_out()

    view.play()

    assert view.playing is True
    assert view.step == 0
    assert painted[-1] == painted[0]


# --- Pausing (CA-116.3) -------------------------------------------------------------


def test_after_pause_no_further_frame_is_painted() -> None:
    view, painted, timer = _playback(_forty())
    view.play()
    timer.tick()
    timer.tick()
    assert len(painted) == 3

    view.pause()
    timer.run_out()  # the step that was already scheduled comes due

    assert len(painted) == 3
    assert view.playing is False
    assert view.step == 2


def test_resuming_carries_on_from_the_step_it_was_on() -> None:
    view, painted, timer = _playback(_forty())
    view.play()
    timer.tick()
    view.pause()
    timer.run_out()

    view.play()
    timer.run_out()

    assert view.step == 39
    assert len(painted) == 2 + 1 + 38  # two, the step repainted on resume, the rest


def test_a_pause_and_play_in_quick_succession_leaves_one_playback_running() -> None:
    """The step scheduled before the pause must not run alongside the new one."""
    view, painted, timer = _playback(_forty())
    view.play()
    view.pause()
    view.play()

    timer.run_out()

    assert [frame.instant for frame in painted[1:]] == sorted(f.instant for f in painted[1:])
    assert len(painted) == 1 + 40


def test_the_button_plays_and_pauses() -> None:
    view, _painted, _timer = _playback(_forty())

    view.play_button.on_click(None)
    assert view.playing is True
    view.play_button.on_click(None)
    assert view.playing is False


# --- Seeking (CA-116.4) -------------------------------------------------------------


def test_seeking_paints_the_frame_playing_reaches() -> None:
    played, painted_by_playing, timer = _playback(_forty())
    played.play()
    timer.run_out()
    sought, painted_by_seeking, _ = _playback(_forty())

    sought.seek(17)

    assert painted_by_seeking == [painted_by_playing[17]]
    assert sought.step == 17
    assert sought.playing is False


def test_the_slider_seeks() -> None:
    view, painted, _timer = _playback(_forty())
    assert (view.slider.min, view.slider.max) == (0, 39)

    view.slider.value = 12.0
    view.slider.on_change(None)

    assert view.step == 12
    assert len(painted) == 1


def test_the_slider_follows_the_playback() -> None:
    view, _painted, timer = _playback(_forty())
    view.play()
    timer.tick()
    timer.tick()

    assert view.slider.value == 2


def test_seeking_while_playing_carries_on_from_there() -> None:
    view, _painted, timer = _playback(_forty())
    view.play()

    view.seek(30)
    timer.run_out()

    assert view.step == 39


# --- Speed and trail (CA-116.5, CA-116.9) -------------------------------------------


def test_speed_changes_when_not_what() -> None:
    slow, painted_slow, slow_timer = _playback(_forty())
    fast, painted_fast, fast_timer = _playback(_forty())
    fast.speed_control.value = "week"
    fast.speed_control.on_select(None)
    slow.speed_control.value = "six_hours"
    slow.speed_control.on_select(None)

    slow.play()
    slow_timer.run_out()
    fast.play()
    fast_timer.run_out()

    assert painted_slow == painted_fast
    assert sum(fast_timer.delays) < sum(slow_timer.delays)


def test_the_speeds_offered_are_the_declared_ones() -> None:
    view, _painted, _timer = _playback(_forty())

    assert [option.key for option in view.speed_control.options] == list(SPEEDS)
    assert view.speed_control.value in SPEEDS


def test_the_trail_switch_keeps_old_earthquakes_at_their_weakest() -> None:
    view, painted, _timer = _playback(_forty())
    view.seek(39)
    assert len(painted[-1].symbols) < 40

    view.trail_switch.value = True
    view.trail_switch.on_change(None)

    assert len(painted[-1].symbols) == 40  # repainted on the same step, with the trail
    assert painted[-1].symbols[0][1] == LEVELS[-1]
    assert view.step == 39


# --- The instant and the period (CA-116.7) -------------------------------------------


def test_the_instant_shown_is_that_of_the_frame_in_the_configured_zone() -> None:
    painted: list[Frame] = []
    view = TimelapseView(
        paint=painted.append, after=_Timer(), locale_code="en", zone="America/Caracas"
    )
    view.load(_forty())

    view.seek(0)

    assert painted[0].instant == _START
    assert view.instant.value == "2026-09-01 08:00:00"  # 12:00 UTC, in Caracas


def test_the_period_is_in_view_before_and_while_playing() -> None:
    view, _painted, _timer = _playback(_forty())
    before = view.period.value

    view.seek(5)

    assert "2026-09-01" in before and "2026-11-30" in before
    assert view.period.value == before


# --- Nothing to play, and too much (CA-116.14, CA-116.11) -----------------------------


def test_with_nothing_to_play_it_says_so_and_play_is_disabled() -> None:
    view, painted, timer = _playback([])

    assert view.play_button.disabled is True
    assert view.slider.disabled is True
    assert view.period.value == "Nothing to play"

    view.play()

    assert painted == [] and timer.pending == [] and view.playing is False


def test_a_set_cut_short_says_how_much_of_it_is_played() -> None:
    view, _painted, _timer = _playback([])

    view.load(_forty(), total=6017)

    assert view.notice.visible is True
    assert "40" in view.notice.value and "6017" in view.notice.value


def test_a_set_played_in_full_says_nothing() -> None:
    view, _painted, _timer = _playback([])

    view.load(_forty(), total=40)

    assert view.notice.visible is False


# --- Replacing the set, and letting go (REQ-TLP-004) ----------------------------------


def test_loading_another_set_stops_the_playback_of_the_old_one() -> None:
    view, painted, timer = _playback(_forty())
    view.play()

    view.load(_forty()[:5])
    timer.run_out()

    assert len(painted) == 1  # the frame painted before the set was replaced
    assert view.playing is False
    assert view.step is None
    assert view.slider.max == 4


def test_stopping_hands_the_map_back() -> None:
    handed_back: list[bool] = []
    view, _painted, timer = _playback(_forty(), on_stop=lambda: handed_back.append(True))
    view.play()

    view.stop_button.on_click(None)
    timer.run_out()

    assert handed_back == [True]
    assert view.playing is False
    assert view.step is None
    assert view.engaged is False


def test_stop_is_offered_only_once_the_playback_has_the_map() -> None:
    view, _painted, _timer = _playback(_forty())
    assert view.stop_button.disabled is True

    view.seek(3)

    assert view.stop_button.disabled is False


def test_the_control_never_moves_the_map() -> None:
    """REQ-TLP-008: it holds no map, so it cannot; this keeps it that way."""
    import vigia_eew.notify.timelapse_view as module

    with open(module.__file__, encoding="utf-8") as handle:
        source = handle.read()

    for mover in ("move_to", "center_on", "zoom_to", "zoom_in", "zoom_out", "flet_map"):
        assert mover not in source
