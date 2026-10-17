"""Tests for the icon generator (`packaging/make_icons.py`).

The launcher icon is the first thing a desktop shows and the last thing anyone
checks: a `.desktop` file that names an icon nobody installed shows a grey
question mark, and an `.ico` the Windows shell rejects shows the generic
executable. Both fail silently, which is why the formats are generated from
one mark and validated here rather than drawn by hand and trusted.

Stdlib only, like `scripts/check_packaging_assets.py` and for the same reason:
it runs before anything is installed.
"""

from __future__ import annotations

import importlib.util
import struct
import sys
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@lru_cache(maxsize=1)
def _generator():
    spec = importlib.util.spec_from_file_location(
        "make_icons", REPO_ROOT / "packaging" / "make_icons.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _png_size(data: bytes) -> tuple[int, int]:
    assert data.startswith(_PNG_MAGIC)
    width, height = struct.unpack(">II", data[16:24])
    return width, height


# --- The mark itself ---


def test_png_is_square_and_the_size_it_was_asked_for():
    make = _generator()
    for size in (16, 64, 512):
        assert _png_size(make.png(size)) == (size, size)


def test_the_mark_is_a_red_target_on_a_transparent_field():
    """The centre is the disc, the corner is nothing: the tray icon's own shape."""
    make = _generator()
    rows = make.mark(64)
    centre = make.pixel(rows, 64, 32, 32)
    corner = make.pixel(rows, 64, 0, 0)
    assert centre == (198, 40, 40, 255)
    assert corner[3] == 0


def test_generation_is_deterministic():
    """A rebuild that changes the bytes turns every release diff into noise."""
    make = _generator()
    assert make.png(128) == make.png(128)


# --- Windows: .ico ---


def test_ico_declares_every_image_it_carries():
    make = _generator()
    data = make.ico()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind) == (0, 1)
    assert count == len(make.ICO_SIZES)
    for index in range(count):
        entry = 6 + index * 16
        length, offset = struct.unpack("<II", data[entry + 8 : entry + 16])
        assert data[offset : offset + 8] == _PNG_MAGIC
        assert len(data[offset : offset + length]) == length


def test_ico_writes_256_as_zero_like_the_format_demands():
    """The directory holds one byte per side; 256 is encoded as 0 and 256 is the size."""
    make = _generator()
    assert 256 in make.ICO_SIZES
    data = make.ico()
    sides = {data[6 + i * 16] for i in range(len(make.ICO_SIZES))}
    assert 0 in sides


# --- macOS: .icns ---


def test_icns_header_matches_its_payload():
    make = _generator()
    data = make.icns()
    assert data[:4] == b"icns"
    assert struct.unpack(">I", data[4:8])[0] == len(data)


def test_icns_carries_the_types_the_finder_looks_for():
    make = _generator()
    data = make.icns()
    seen = []
    offset = 8
    while offset < len(data):
        ostype = data[offset : offset + 4]
        length = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
        assert length >= 8
        assert data[offset + 8 : offset + 16] == _PNG_MAGIC
        seen.append(ostype)
        offset += length
    assert offset == len(data)
    assert b"ic07" in seen  # 128
    assert b"ic08" in seen  # 256
    assert b"ic09" in seen  # 512
    assert b"ic10" in seen  # 1024, the Retina one


# --- Writing them out ---


def test_write_all_produces_every_file_the_packagers_name(tmp_path):
    make = _generator()
    written = make.write_all(tmp_path)
    names = {path.relative_to(tmp_path).as_posix() for path in written}
    assert "icon.ico" in names
    assert "icon.icns" in names
    assert "icons/vigia-eew.svg" in names
    for size in make.PNG_SIZES:
        assert f"icons/vigia-eew-{size}.png" in names
    assert all(path.is_file() for path in written)


def test_the_svg_is_the_same_mark_scaled(tmp_path):
    make = _generator()
    make.write_all(tmp_path)
    svg = (tmp_path / "icons" / "vigia-eew.svg").read_text(encoding="utf-8")
    assert svg.startswith("<?xml")
    assert "viewBox" in svg
    assert "#c62828" in svg.lower()
