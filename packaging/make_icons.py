#!/usr/bin/env python3
"""Generate the launcher icons the three packagers install (REQ-OPS-007).

One mark, three formats, no image editor: the concentric target that
`src/vigia_eew/assets/tray_icon.png` already carries, rasterised at every size
a desktop asks for.

  - Linux: `icons/vigia-eew-<size>.png` for the hicolor theme, plus a scalable
    `icons/vigia-eew.svg`. The `.desktop` file names `vigia-eew`; if the theme
    has no file under that name the launcher shows a grey placeholder, which
    is the failure this script exists to prevent.
  - Windows: `icon.ico`, the sizes the shell picks between (the taskbar takes
    a small one, the Alt+Tab switcher a large one).
  - macOS: `icon.icns`, up to the 1024 px Retina variant the Finder wants.

Stdlib only, deliberately -- the same rule `scripts/check_packaging_assets.py`
follows. This runs on a build machine before anything is installed, and Pillow
is a dependency of the product, not of its build.

Usage: `python3 packaging/make_icons.py [packaging-dir]`
"""

from __future__ import annotations

import struct
import sys
import zlib
from functools import cache
from math import hypot
from pathlib import Path

#: The mark's colour, sampled from the tray icon that has shipped since v0.5.
COLOUR = (198, 40, 40)

#: Ring geometry as fractions of the canvas, measured off that same 64 px icon:
#: (outer radius, inner radius); an inner radius of 0 is a filled disc.
RINGS: tuple[tuple[float, float], ...] = (
    (0.469, 0.422),  # outer ring
    (0.3125, 0.25),  # middle ring
    (0.133, 0.0),  # centre disc
)

#: Hicolor sizes. 22 and 24 are the panel sizes GNOME and Xfce ask for; a theme
#: that lacks them scales the nearest one and it shows.
PNG_SIZES: tuple[int, ...] = (16, 22, 24, 32, 48, 64, 128, 256, 512)

#: What the Windows shell picks between. 256 is the one Explorer's large view
#: uses, and the one the format encodes as a zero.
ICO_SIZES: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)

#: OSType -> pixel side. `ic10` is 512@2x: the Retina icon, and the reason the
#: mark is drawn rather than scaled from a 64 px source.
ICNS_TYPES: tuple[tuple[bytes, int], ...] = (
    (b"ic11", 32),
    (b"ic12", 64),
    (b"ic07", 128),
    (b"ic08", 256),
    (b"ic09", 512),
    (b"ic10", 1024),
)


def _coverage(distance: float, outer: float, inner: float) -> float:
    """How much of a pixel at `distance` from the centre the ring covers.

    Analytic antialiasing: one sample per pixel, feathered half a pixel either
    side of each edge. Supersampling would mean 16 samples for every pixel of
    a 1024 px canvas to reach the same place.
    """
    inside = min(max(outer + 0.5 - distance, 0.0), 1.0)
    outside = 1.0 if inner <= 0.0 else min(max(distance - inner + 0.5, 0.0), 1.0)
    return min(inside, outside)


def _row(size: int, y: int) -> bytes:
    """One row of the mark, left half computed and mirrored."""
    centre = size / 2.0
    red, green, blue = COLOUR
    half = (size + 1) // 2
    left = bytearray()
    for x in range(half):
        distance = hypot(x + 0.5 - centre, y + 0.5 - centre)
        alpha = max(_coverage(distance, outer * size, inner * size) for outer, inner in RINGS)
        left += bytes((red, green, blue, round(alpha * 255)))
    right = bytearray()
    for x in range(size - half - 1, -1, -1):
        right += left[x * 4 : x * 4 + 4]
    return bytes(left + right)


def mark(size: int) -> bytes:
    """The mark at `size` px, as raw RGBA rows (no PNG framing).

    The target is symmetric about both axes, so a quarter of it is computed
    and the rest mirrored: a 1024 px Retina element is a million pixels of
    arithmetic in pure Python, and three quarters of it was the same answer.
    """
    half = (size + 1) // 2
    top = [_row(size, y) for y in range(half)]
    rows = bytearray()
    for y in range(size):
        rows += top[y if y < half else size - 1 - y]
    return bytes(rows)


def pixel(rows: bytes, size: int, x: int, y: int) -> tuple[int, int, int, int]:
    """The RGBA tuple at (x, y) of a buffer `mark` returned."""
    start = (y * size + x) * 4
    r, g, b, a = rows[start : start + 4]
    return (r, g, b, a)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


@cache
def png(size: int) -> bytes:
    """The mark as an 8-bit RGBA PNG, `size` x `size`.

    Cached: the 1024 px Retina element costs a million pixels of arithmetic,
    and `ico()`, `icns()` and `write_all()` all ask for the same sizes.
    """
    rows = mark(size)
    stride = size * 4
    raw = b"".join(b"\x00" + rows[y * stride : (y + 1) * stride] for y in range(size))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    # Fixed compression level and no timestamp chunk: the same mark has to
    # produce the same bytes, or every release diff carries noise.
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def ico() -> bytes:
    """A PNG-compressed `.ico` carrying `ICO_SIZES` (Vista and later)."""
    images = [png(size) for size in ICO_SIZES]
    directory = b""
    offset = 6 + 16 * len(images)
    for size, image in zip(ICO_SIZES, images, strict=True):
        side = 0 if size >= 256 else size  # the format's one byte; 256 is written as 0
        directory += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(image), offset)
        offset += len(image)
    return struct.pack("<HHH", 0, 1, len(images)) + directory + b"".join(images)


def icns() -> bytes:
    """An `.icns` whose every element is a PNG, as 10.7 and later accept."""
    body = b""
    for ostype, size in ICNS_TYPES:
        image = png(size)
        body += ostype + struct.pack(">I", len(image) + 8) + image
    return b"icns" + struct.pack(">I", len(body) + 8) + body


def svg() -> str:
    """The same mark as a scalable icon, for `hicolor/scalable`."""
    red = "#{:02x}{:02x}{:02x}".format(*COLOUR)
    circles = []
    for outer, inner in RINGS:
        if inner <= 0.0:
            circles.append(f'  <circle cx="32" cy="32" r="{outer * 64:.3g}" fill="{red}"/>')
        else:
            width = (outer - inner) * 64
            radius = (outer + inner) / 2 * 64
            circles.append(
                f'  <circle cx="32" cy="32" r="{radius:.3g}" fill="none" '
                f'stroke="{red}" stroke-width="{width:.3g}"/>'
            )
    body = "\n".join(circles)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" '
        'viewBox="0 0 64 64" role="img" aria-label="Vigia-eew">\n'
        f"{body}\n"
        "</svg>\n"
    )


def write_all(root: Path) -> list[Path]:
    """Write every icon under `root` (the `packaging/` directory). Returns the paths."""
    icons = root / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    written = []
    for size in PNG_SIZES:
        path = icons / f"vigia-eew-{size}.png"
        path.write_bytes(png(size))
        written.append(path)
    scalable = icons / "vigia-eew.svg"
    scalable.write_text(svg(), encoding="utf-8")
    written.append(scalable)
    for name, data in (("icon.ico", ico()), ("icon.icns", icns())):
        path = root / name
        path.write_bytes(data)
        written.append(path)
    return written


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent
    written = write_all(root)
    for path in written:
        print(f"  {path.relative_to(root.parent)} ({path.stat().st_size} B)")
    print(f"Icons: {len(written)} files written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
