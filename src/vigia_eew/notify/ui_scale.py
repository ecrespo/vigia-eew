"""Window sizes and responsive breakpoints for the Flet views (T-151, ADR-030).

Kept apart from the views because none of it needs a display to be decided,
and therefore none of it needs one to be tested.

Flet lays out by breakpoints: the same panel is one column on a narrow window and
two or three on a wide one, so what is left to decide here is where it opens
and which column spans each breakpoint gives a field.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vigia_eew.i18n import DEFAULT_LOCALE

if TYPE_CHECKING:
    from flet import ResponsiveRowBreakpoint

#: Column spans keyed by breakpoint name, in the shape Flet's `col=` takes.
type Columns = dict[str | ResponsiveRowBreakpoint, int | float]

#: The configuration surfaces -- the panel and the About screen it opens --
#: ship in English and are not translated: the panel's field labels come from
#: the configuration schema, whose names are English by convention (RNF-10),
#: and an About in another language beside them would be half a translation.
#: The alert, the toast and the tray menu still follow `[notification]
#: language`.
PANEL_LOCALE = DEFAULT_LOCALE

#: What an ordinary screen (panel, history, About) opens at.
PREFERRED_SIZE = (1040, 860)

#: What it never goes below. The layout collapses to one column long before
#: this, so the floor is about the footer's buttons still fitting on a line.
MINIMUM_SIZE = (420, 480)

#: What a non-fullscreen alert opens at. Wide enough for the text and the map
#: side by side; below the `md` breakpoint they stack instead.
ALERT_SIZE = (1180, 780)

#: Column spans (out of 12) per breakpoint. Flet's breakpoints: xs < 576 px,
#: sm >= 576, md >= 768, lg >= 992, xl >= 1200, xxl >= 1400.
FIELD_COLUMNS: Columns = {"xs": 12, "sm": 12, "md": 6, "xl": 4}
ALERT_TEXT_COLUMNS: Columns = {"xs": 12, "md": 5}
ALERT_MAP_COLUMNS: Columns = {"xs": 12, "md": 7}
HISTORY_TABLE_COLUMNS: Columns = {"xs": 12, "lg": 7}
HISTORY_MAP_COLUMNS: Columns = {"xs": 12, "lg": 5}


def spans(columns: Columns) -> list[int | float]:
    """The spans in breakpoint order, for checking that each one fits in 12."""
    return list(columns.values())
