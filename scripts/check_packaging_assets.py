#!/usr/bin/env python3
"""Validate the resources the packager bundles, before it runs (REQ-OPS-007).

Two consecutive releases shipped broken because of a packaging resource:
`7b1c71c`, an invalid placeholder icon, and `c38d9f6`, a *valid* PNG whose
resolution linuxdeploy rejects. The second is the instructive one -- "is it
a PNG" was never the question. The question is whether it is a PNG the
packager will accept, and the only way to answer it before the packager
runs is to ask here.

Stdlib only, deliberately: this has to run before anything is installed, and
`packaging/build_linux.sh` generates the AppImage icon the same way for the
same reason. Pillow is a runtime dependency of the product, not of its build.

Usage: `check_packaging_assets.py [repo-root]`
"""

from __future__ import annotations

import json
import struct
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

#: linuxdeploy accepts icons from 8x8 to 512x512. A 1x1 PNG parses fine and
#: is rejected anyway -- that is exactly what broke v0.1.2.
_MIN_ICON_SIDE = 8
_MAX_ICON_SIDE = 512


@dataclass(frozen=True)
class Asset:
    """A resource `packaging/vigia-eew.spec` bundles, and how to recognise a good one."""

    path: str
    kind: str


#: Everything under `src/vigia_eew/assets`, which the spec bundles wholesale
#: as `vigia_eew/assets` (packaging/vigia-eew.spec:41).
REQUIRED: tuple[Asset, ...] = (
    Asset("src/vigia_eew/assets/tray_icon.png", "icon"),
    Asset("src/vigia_eew/assets/critical.wav", "sound"),
    Asset("src/vigia_eew/assets/warning.wav", "sound"),
    Asset("src/vigia_eew/assets/info.wav", "sound"),
    Asset("src/vigia_eew/assets/countries.geojson", "geojson"),
)


def _icon_problem(path: Path) -> str | None:
    data = path.read_bytes()
    if not data.startswith(_PNG_MAGIC):
        return f"{path.name}: not a PNG (bad signature)"
    if len(data) < 24:
        return f"{path.name}: truncated before its header"
    width, height = struct.unpack(">II", data[16:24])
    if not (_MIN_ICON_SIDE <= width <= _MAX_ICON_SIDE):
        return f"{path.name}: {width}x{height}, outside {_MIN_ICON_SIDE}..{_MAX_ICON_SIDE}"
    if not (_MIN_ICON_SIDE <= height <= _MAX_ICON_SIDE):
        return f"{path.name}: {width}x{height}, outside {_MIN_ICON_SIDE}..{_MAX_ICON_SIDE}"
    return None


def _sound_problem(path: Path) -> str | None:
    try:
        with wave.open(str(path), "rb") as handle:
            if handle.getnframes() <= 0:
                return f"{path.name}: no audio frames"
    except (wave.Error, EOFError) as exc:
        return f"{path.name}: not readable as WAV ({exc})"
    return None


def _geojson_problem(path: Path) -> str | None:
    try:
        parsed = json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return f"{path.name}: not valid JSON ({exc})"
    if "features" not in parsed:
        return f"{path.name}: no 'features' key; not a FeatureCollection"
    return None


_CHECKS = {"icon": _icon_problem, "sound": _sound_problem, "geojson": _geojson_problem}


def problems(root: Path, required: tuple[Asset, ...] = REQUIRED) -> list[str]:
    """Everything wrong with the packaging resources under `root`."""
    found: list[str] = []
    for asset in required:
        path = root / asset.path
        if not path.is_file():
            found.append(f"{asset.path}: missing")
            continue
        problem = _CHECKS[asset.kind](path)
        if problem is not None:
            found.append(problem)
    return found


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    found = problems(root)
    if not found:
        print(f"Packaging assets: {len(REQUIRED)} resources valid.")
        return 0
    print("Invalid packaging resources; not invoking the packager:", file=sys.stderr)
    for problem in found:
        print(f"  {problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
