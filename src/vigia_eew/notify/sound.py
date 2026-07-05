"""Alert audio layer (RF-17, ADR-005).

Plays a sound per severity, **more insistent the more severe** (more repetitions).
The actual player depends on the OS (paplay/aplay/ffplay on Linux, afplay on macOS,
`winsound` on Windows) with a *fallback* to the terminal bell; that choice is
isolated in `player_command` (pure) and in `_default_player`.

The player is injectable to test the repetition logic without playing audio. A
playback failure never interrupts the alert (RNF-03): it is logged and execution
continues.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from vigia_eew.models import SeverityLevel

_Player = Callable[[Path], None]
_SleepFn = Callable[[float], None]


@dataclass(frozen=True, slots=True)
class SoundProfile:
    """Playback profile for a severity: asset and repetition pattern."""

    asset: str
    repetitions: int
    interval_s: float


# Increasing insistence with severity (RF-17).
PROFILES: dict[SeverityLevel, SoundProfile] = {
    "info": SoundProfile("info.wav", 1, 0.0),
    "warning": SoundProfile("warning.wav", 2, 0.6),
    "critical": SoundProfile("critical.wav", 4, 0.4),
}


def assets_path() -> Path:
    """Directory of packaged audio assets (`vigia_eew/assets`)."""
    return Path(__file__).resolve().parent.parent / "assets"


def player_command(
    path: str | Path, platform: str, available: set[str]
) -> list[str] | None:
    """Chooses the playback command based on OS and available binaries.

    Returns the argument list for `subprocess`, or None if there is no suitable
    external player (the caller will use a *fallback*).
    """
    path = str(path)
    if platform == "darwin":
        return ["afplay", path]
    if platform == "win32":
        return None  # on Windows `winsound` is used, not an external command
    if "paplay" in available:
        return ["paplay", path]
    if "aplay" in available:
        return ["aplay", path]
    if "ffplay" in available:
        return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]
    return None


def _available() -> set[str]:
    return {c for c in ("paplay", "aplay", "ffplay") if shutil.which(c)}


def _default_player(path: Path) -> None:
    """Real player per OS; *fallback* to the terminal bell."""
    if sys.platform == "win32":
        import winsound  # only available on Windows

        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return
    command = player_command(path, sys.platform, _available())
    if command is None:
        print("\a", end="", flush=True)  # terminal bell as a last resort
        return
    subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class SoundPlayer:
    """Plays the alert sound according to severity (RF-17)."""

    def __init__(
        self,
        *,
        player: _Player | None = None,
        sleep: _SleepFn = time.sleep,
        enabled: bool = True,
        assets_dir: Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._player = player or _default_player
        self._sleep = sleep
        self._enabled = enabled
        self._assets_dir = assets_dir or assets_path()
        self._log = logger or logging.getLogger("vigia_eew.notify.sound")

    def play(self, severity: SeverityLevel) -> None:
        """Plays the severity's profile (multiple times if insistent)."""
        if not self._enabled:
            return
        profile = PROFILES[severity]
        path = self._assets_dir / profile.asset
        for i in range(profile.repetitions):
            try:
                self._player(path)
            except Exception as exc:  # noqa: BLE001 - audio never breaks the alert
                self._log.warning("sound_failed detail=%s", exc)
            if i < profile.repetitions - 1:
                self._sleep(profile.interval_s)
