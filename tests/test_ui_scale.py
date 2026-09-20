"""Tests for the panel's window size and font scale (T-151).

Both defaults were absent, and Tk's answer to an absent default is its own:
it packs the window to the natural width of its widest row -- with every
section collapsed, a button -- and draws everything in the interpreter's
default font. The result was reported as "se ve pequeño": a tall narrow strip
of small text.
"""

from __future__ import annotations

from vigia_eew.notify.ui_scale import FONT_NAMES, bumped_size, enlarge_fonts, panel_geometry


class _FakeFont:
    def __init__(self, size: int) -> None:
        self._size = size

    def cget(self, key: str) -> int:
        assert key == "size"
        return self._size

    def configure(self, **kwargs: int) -> None:
        self._size = kwargs["size"]


# --- Window size ---


def test_the_panel_opens_at_a_readable_size_on_a_normal_screen():
    assert panel_geometry(1920, 1080) == "820x920"


def test_the_panel_never_exceeds_the_screen_it_opens_on():
    """A window taller than the display has its buttons below the edge."""
    width, height = (int(part) for part in panel_geometry(1366, 768).split("x"))
    assert width <= 1366 and height <= 768


def test_the_panel_has_a_floor_a_smaller_screen_cannot_push_through():
    """Below this the sections stop being readable at all; scrolling is the tradeoff."""
    assert panel_geometry(640, 480) == "560x520"


# --- Font size ---


def test_point_sizes_grow_and_pixel_sizes_grow_downward():
    """Tk encodes points as positive and pixels as negative; both have to get bigger."""
    assert bumped_size(10) == 13
    assert bumped_size(-12) == -15


def test_a_bump_of_zero_changes_nothing():
    assert bumped_size(11, bump=0) == 11


def test_enlarge_fonts_reports_what_it_changed():
    """Named fonts are shared by the interpreter; the caller is told which moved."""
    fonts = {name: _FakeFont(10) for name in FONT_NAMES}
    changed = enlarge_fonts(lambda name: fonts[name])
    assert changed == list(FONT_NAMES)
    assert all(font.cget("size") == 13 for font in fonts.values())


def test_a_font_the_interpreter_does_not_define_is_skipped():
    """Tk defines a different set per platform; a missing one is not a failure."""

    def lookup(name: str) -> _FakeFont:
        if name == FONT_NAMES[0]:
            return _FakeFont(10)
        raise RuntimeError(f"no font named {name}")

    assert enlarge_fonts(lookup) == [FONT_NAMES[0]]


# --- Wheel scrolling (pure: the arithmetic, not the binding) ---


def test_x11_sends_buttons_four_and_five():
    from vigia_eew.notify.ui_scale import wheel_units

    assert wheel_units(num=4) == -1  # up
    assert wheel_units(num=5) == 1  # down


def test_windows_and_macos_send_a_delta():
    from vigia_eew.notify.ui_scale import wheel_units

    assert wheel_units(delta=120) == -1
    assert wheel_units(delta=-120) == 1
    assert wheel_units(delta=360) == -3


def test_a_delta_smaller_than_one_notch_still_scrolls():
    """macOS sends fine-grained deltas; rounding them to zero freezes the wheel."""
    from vigia_eew.notify.ui_scale import wheel_units

    assert wheel_units(delta=20) == -1


def test_an_event_that_says_nothing_scrolls_nothing():
    from vigia_eew.notify.ui_scale import wheel_units

    assert wheel_units() == 0
