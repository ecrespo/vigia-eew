"""How big the configuration panel opens, and in what size type (T-151).

Tk has defaults for both and they are the wrong ones here: a window with no
geometry is packed to the natural width of its widest row -- with every
section collapsed, that is a button -- and the default font is whatever the
interpreter was built with, which on a HiDPI screen is small. Reported as
"se ve pequeño", and it is: the panel opened as a narrow strip of fine print.

Kept apart from `config_panel.py` because none of it needs a display to be
decided, and therefore none of it needs one to be tested.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vigia_eew.i18n import DEFAULT_LOCALE

#: The configuration surfaces -- the panel and the About window it opens --
#: ship in English and are not translated: the panel's field labels come from
#: the configuration schema, whose names are English by convention (RNF-10),
#: and an About in another language beside them would be half a translation.
#: The alert, the toast and the tray menu still follow `[notification]
#: language`.
PANEL_LOCALE = DEFAULT_LOCALE

#: What the panel opens at, screen permitting.
PREFERRED_SIZE = (820, 920)

#: What it never goes below. Under this the labels and their controls stop
#: fitting on one line, which is worse than scrolling.
MINIMUM_SIZE = (560, 520)

#: Margin left for the desktop's own furniture (panel, dock, title bar).
_SCREEN_MARGIN = (120, 160)

#: Points added to the panel's text. Three rather than one: the complaint was
#: not that it was marginally small.
FONT_BUMP = 3

#: The named fonts Tk resolves its widgets against. Not every platform defines
#: every one of them.
FONT_NAMES = ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont")


def panel_geometry(screen_width: int, screen_height: int) -> str:
    """The `WIDTHxHEIGHT` the panel opens at on a screen of this size."""
    width = min(PREFERRED_SIZE[0], max(MINIMUM_SIZE[0], screen_width - _SCREEN_MARGIN[0]))
    height = min(PREFERRED_SIZE[1], max(MINIMUM_SIZE[1], screen_height - _SCREEN_MARGIN[1]))
    return f"{width}x{height}"


def bumped_size(size: int, bump: int = FONT_BUMP) -> int:
    """A Tk font size, enlarged.

    Tk encodes points as a positive number and pixels as a negative one, so
    "bigger" is `+bump` in one case and `-bump` in the other. Getting the sign
    wrong shrinks the text instead, which is how this earns a test.
    """
    return size - bump if size < 0 else size + bump


def enlarge_fonts(lookup: Callable[[str], Any], *, bump: int = FONT_BUMP) -> list[str]:
    """Enlarge every named font `lookup` can resolve. Returns the ones changed.

    `lookup` is `tkinter.font.nametofont` bound to a window. Injected so the
    rule is testable without an interpreter, and because a platform that does
    not define one of these should lose a font, not the panel.
    """
    changed = []
    for name in FONT_NAMES:
        try:
            font = lookup(name)
            font.configure(size=bumped_size(int(font.cget("size")), bump))
        except Exception:  # noqa: BLE001 - a missing named font is not a failure
            continue
        changed.append(name)
    return changed


def wheel_units(*, num: int = 0, delta: int = 0) -> int:
    """How far one wheel event scrolls, in Tk "units".

    Two conventions, because Tk exposes two: X11 delivers the wheel as
    buttons 4 and 5, while Windows and macOS deliver a `delta` -- 120 per
    notch on Windows, and much smaller, continuous values on macOS. Rounding
    those to zero is a wheel that does nothing, so anything non-zero moves at
    least one unit.
    """
    if num == 4:
        return -1
    if num == 5:
        return 1
    if delta == 0:
        return 0
    return (-1 if delta > 0 else 1) * max(1, abs(delta) // 120)
