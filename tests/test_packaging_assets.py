"""Tests for packaging asset validation (REQ-OPS-007, HU-107).

Two consecutive releases shipped broken because of a packaging resource:
`7b1c71c` (an invalid placeholder icon) and `c38d9f6` (a valid PNG whose
resolution linuxdeploy rejects). Both were found by the packager, which
means both were found after the build had already started -- and the second
proves that "is it a PNG" is not the question. The question is whether it is
a PNG the packager will accept.

Validation is stdlib-only on purpose: it has to be able to run before
anything is installed, and the generated AppImage icon is built the same way
in `packaging/build_linux.sh` for the same reason.
"""

from __future__ import annotations

import importlib.util
import struct
import sys
import wave
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _checker():
    spec = importlib.util.spec_from_file_location(
        "check_packaging_assets", REPO_ROOT / "scripts" / "check_packaging_assets.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _png(path: Path, width: int, height: int) -> None:
    """Write a solid PNG of exactly `width` x `height`, with no Pillow."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes((200, 60, 60)) * width
    body = zlib.compress(row * height)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", body) + chunk(b"IEND", b"")
    )


def _wav(path: Path) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(b"\x00\x00" * 100)


def test_the_repository_assets_pass(tmp_path: Path) -> None:
    """CA-107.2: the current resources produce no false positive."""
    assert _checker().problems(REPO_ROOT) == []


def test_a_png_of_invalid_resolution_is_reported(tmp_path: Path) -> None:
    """CA-107.1: the 1x1 placeholder that broke v0.1.2 is caught by name.

    A 1x1 PNG is a perfectly valid image and linuxdeploy rejects it anyway,
    which is the whole reason dimensions are checked and not just format.
    """
    checker = _checker()
    assets = tmp_path / "src" / "vigia_eew" / "assets"
    assets.mkdir(parents=True)
    _png(assets / "tray_icon.png", 1, 1)
    for name in ("critical.wav", "warning.wav", "info.wav"):
        _wav(assets / name)
    (assets / "countries.geojson").write_text('{"type": "FeatureCollection", "features": []}')

    reported = checker.problems(tmp_path)

    assert len(reported) == 1
    assert "tray_icon.png" in reported[0]
    assert "1x1" in reported[0]


def test_a_file_that_is_not_a_png_is_reported(tmp_path: Path) -> None:
    """CA-107.1: the invalid placeholder that broke v0.1.1 is caught by name."""
    checker = _checker()
    assets = tmp_path / "src" / "vigia_eew" / "assets"
    assets.mkdir(parents=True)
    (assets / "tray_icon.png").write_bytes(b"not a png at all")

    reported = checker.problems(tmp_path)

    assert any("tray_icon.png" in problem for problem in reported)


def test_a_missing_asset_is_reported(tmp_path: Path) -> None:
    """CA-107.1: an asset the spec bundles but the tree lacks stops the build."""
    checker = _checker()
    (tmp_path / "src" / "vigia_eew" / "assets").mkdir(parents=True)

    reported = checker.problems(tmp_path)

    assert any("critical.wav" in problem for problem in reported)


def test_a_truncated_sound_is_reported(tmp_path: Path) -> None:
    """CA-107.1: a sound that is not readable audio is caught before packaging.

    `sound.py` opens these at alert time. A corrupt one is silence exactly
    when the product is supposed to be impossible to ignore.
    """
    checker = _checker()
    assets = tmp_path / "src" / "vigia_eew" / "assets"
    assets.mkdir(parents=True)
    _png(assets / "tray_icon.png", 64, 64)
    (assets / "critical.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVEjunk")
    for name in ("warning.wav", "info.wav"):
        _wav(assets / name)
    (assets / "countries.geojson").write_text('{"type": "FeatureCollection", "features": []}')

    reported = checker.problems(tmp_path)

    assert any("critical.wav" in problem for problem in reported)
