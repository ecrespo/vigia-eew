"""Tests for the audio layer (RF-17, RNF-03)."""

from __future__ import annotations

from pathlib import Path

from vigia_eew.notify.sound import (
    PROFILES,
    SoundPlayer,
    player_command,
)


class _Player:
    """Fake player that records the paths played."""

    def __init__(self, *, fails=False):
        self.paths: list[Path] = []
        self._fails = fails

    def __call__(self, path: Path) -> None:
        self.paths.append(path)
        if self._fails:
            raise RuntimeError("audio unavailable")


def _sound_player(player, *, enabled=True, assets_dir=Path("/assets"), sleep=None):
    return SoundPlayer(
        player=player,
        sleep=sleep or (lambda _s: None),
        enabled=enabled,
        assets_dir=assets_dir,
    )


# --- Profile per severity (RF-17: more insistent the more severe) ---


def test_insistence_grows_with_severity():
    assert PROFILES["info"].repetitions < PROFILES["warning"].repetitions
    assert PROFILES["warning"].repetitions < PROFILES["critical"].repetitions


def test_plays_according_to_critical_repetitions():
    player = _Player()
    _sound_player(player).play("critical")
    assert len(player.paths) == PROFILES["critical"].repetitions


def test_info_plays_once():
    player = _Player()
    _sound_player(player).play("info")
    assert len(player.paths) == 1


def test_path_points_to_the_severity_asset():
    player = _Player()
    _sound_player(player, assets_dir=Path("/x/assets")).play("critical")
    assert player.paths[0] == Path("/x/assets") / PROFILES["critical"].asset


def test_disabled_does_not_play():
    player = _Player()
    _sound_player(player, enabled=False).play("critical")
    assert player.paths == []


def test_waits_between_repetitions():
    player = _Player()
    waits: list[float] = []
    _sound_player(player, sleep=lambda s: waits.append(s)).play("warning")
    # One fewer wait than repetitions (no wait after the last playback).
    assert len(waits) == PROFILES["warning"].repetitions - 1


def test_player_failure_does_not_propagate():
    player = _Player(fails=True)
    _sound_player(player).play("critical")  # must not raise (RNF-03)
    assert len(player.paths) == PROFILES["critical"].repetitions  # tried all of them


# --- Player selection per OS (pure) ---


def test_linux_command_prefers_paplay():
    assert player_command("/a.wav", "linux", {"paplay", "aplay"}) == ["paplay", "/a.wav"]


def test_linux_command_falls_back_to_aplay():
    assert player_command("/a.wav", "linux", {"aplay"}) == ["aplay", "/a.wav"]


def test_macos_command_uses_afplay():
    assert player_command("/a.wav", "darwin", set()) == ["afplay", "/a.wav"]


def test_command_without_player_is_none():
    assert player_command("/a.wav", "linux", set()) is None
