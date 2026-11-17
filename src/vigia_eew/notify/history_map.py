"""The history on a map (REQ-MAP-002, REQ-MAP-003, REQ-MAP-005, ADR-027, ADR-030).

Two earthquakes of magnitude 4, one fifty kilometres away and one at two
hundred and fifty, mean different things — and a table of coordinates does not
communicate that. The map does.

It is a **view on the list**, never the other way round
([[lat.md/history#The map is a view on the list, never the other way round]]).
Everything here can be unavailable — no network, no cached tiles, a provider
that is down — and the history still answers the question it exists for,
because the list is right there and depends on none of it.

What to draw is decided by `plan()`: where each symbol goes, how big it is,
and which symbols are alerts. It needs no display, which is what makes "a
magnitude 6 is visibly bigger than a 3" and "alerted and discarded are told
apart" checkable at all. `HistoryMap` turns the plan into `flet-map` layers
and decides nothing itself; the tiles are fetched and cached by the map
control, and a tile that fails flips the map into its "unavailable" notice.

The symbols are **markers holding a control**, not painted circles
([[lat.md/history#A symbol can be pointed at]]): a `CircleMarker` has neither
a tooltip nor events, so it could not say which earthquake it was.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import flet as ft
import flet_map as fm

from vigia_eew.history import EventRecord
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify.map_view import (
    ATTRIBUTION,
    MAX_RADIUS,
    MIN_RADIUS,
    attribution_layer,
    marker_radius,
    tile_layer,
)

__all__ = [
    "ALERTED_STYLE",
    "ATTRIBUTION",
    "DEFAULT_ZOOM",
    "DISCARDED_STYLE",
    "LEGEND",
    "MAX_RADIUS",
    "MIN_RADIUS",
    "RECOVERED_STYLE",
    "HistoryMap",
    "Marker",
    "MarkerStyle",
    "centre_of",
    "marker_radius",
    "marker_style",
    "plan",
]

#: Where the map opens when the history has nothing to centre on.
DEFAULT_ZOOM = 6

#: How much larger the selected symbol is drawn, and how thick its ring, in
#: pixels. Both, so that the selection reads without relying on a colour.
SELECTED_GROWTH = 5
RING = 2
SELECTED_RING = 5

#: "Leave the selection as it is": what `show` assumes when it is not told.
_KEEP: Any = object()


@dataclass(frozen=True, slots=True)
class MarkerStyle:
    """How one class of arrival looks.

    Colour is not the only difference, deliberately. An alert is filled and a
    discard is an outline, so the distinction survives a screenshot, a
    printout, and a reader who cannot tell the two colours apart. A recovered
    arrival is an outline too, and square: three verdicts, three shapes.
    """

    fill: str
    outline: str
    filled: bool
    legend_key: str
    #: A circle, or a square with barely rounded corners.
    round: bool = True


ALERTED_STYLE = MarkerStyle(
    fill="#D32F2F", outline="#7F1010", filled=True, legend_key="map_legend_alerted"
)
DISCARDED_STYLE = MarkerStyle(
    fill="", outline="#5A6472", filled=False, legend_key="map_legend_discarded"
)


#: An arrival nobody evaluated: read from a catalogue afterwards (REQ-HIS-011).
#: Hollow like a discard -- it did not alert either -- and square, because it
#: is not a discard: the agent did not decide against it, it was not watching.
RECOVERED_STYLE = MarkerStyle(
    fill="", outline="#1565C0", filled=False, legend_key="map_legend_recovered", round=False
)

#: What the legend explains, in the order it lists them.
LEGEND: tuple[MarkerStyle, ...] = (ALERTED_STYLE, DISCARDED_STYLE, RECOVERED_STYLE)

#: The corner radius of a square symbol, in pixels.
SQUARE_CORNER = 2


@dataclass(frozen=True, slots=True)
class Marker:
    """One arrival, placed and sized."""

    latitude: float
    longitude: float
    radius: int
    style: MarkerStyle
    record: EventRecord
    #: The one the user chose in the table, or pressed here (REQ-MAP-007).
    selected: bool = False
    #: How strongly it is drawn, from 0 to 1. Always 1 on the static map; a
    #: playback draws an older earthquake weaker (REQ-TLP-005).
    strength: float = 1.0


def marker_style(verdict: str) -> MarkerStyle:
    """The look for a verdict. Anything unrecognised is drawn as a discard.

    Leaving an unknown verdict off the map would silently under-report the
    history, which is worse than drawing it in the more modest of the two
    styles.
    """
    if verdict == "alerted":
        return ALERTED_STYLE
    if verdict == "recovered":
        return RECOVERED_STYLE
    return DISCARDED_STYLE


def centre_of(
    records: Sequence[EventRecord], *, fallback: tuple[float, float]
) -> tuple[float, float]:
    """The midpoint of what is being shown, or the fallback when nothing is.

    An empty history still has to open on somewhere the user recognises, so
    the caller passes its reference point rather than landing on the Atlantic.
    """
    if not records:
        return fallback
    latitudes = [record.latitude for record in records]
    longitudes = [record.longitude for record in records]
    return (
        (min(latitudes) + max(latitudes)) / 2,
        (min(longitudes) + max(longitudes)) / 2,
    )


def plan(
    records: Sequence[EventRecord],
    *,
    selected: int | None = None,
    strengths: Mapping[int, float] | None = None,
) -> list[Marker]:
    """Works out every symbol without touching a control.

    Every record is placed -- the map does not get to drop one the table is
    showing (CA-112.6). Alerts go last so they are drawn over discards, and
    the selected one last of all.

    `selected` is the id of the row the user chose. Its symbol is larger and
    its ring thicker -- a difference of shape, like the one between an alert
    and a discard, so that it does not rest on telling two colours apart.

    `strengths` is how strongly to draw each row, by id; a row it does not
    name is drawn in full. Which earthquake is how old is not decided here.
    """
    strengths = strengths or {}
    markers = []
    for record in records:
        chosen = selected is not None and record.id == selected
        markers.append(
            Marker(
                latitude=record.latitude,
                longitude=record.longitude,
                radius=marker_radius(record.magnitude) + (SELECTED_GROWTH if chosen else 0),
                style=marker_style(record.verdict),
                record=record,
                selected=chosen,
                strength=strengths.get(record.id, 1.0) if record.id is not None else 1.0,
            )
        )
    return sorted(markers, key=lambda marker: (marker.selected, marker.style.filled))


# --- The control -------------------------------------------------------------------


class HistoryMap:
    """The map control: tiles, symbols, a legend and the attribution.

    `available` turns False the first time a tile fails, and the notice
    saying so appears over the map (REQ-MAP-002). The symbols stay: they are
    still in the right place relative to each other, and the list beside them
    is unaffected either way.
    """

    def __init__(
        self,
        *,
        locale_code: str = DEFAULT_LOCALE,
        zoom: int = DEFAULT_ZOOM,
        centre: tuple[float, float] | None = None,
        on_select: Callable[[int], None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._locale = locale_code
        self._log = logger or logging.getLogger("vigia_eew.notify.history_map")
        self.available = True
        self.markers: list[Marker] = []
        self._describe: Callable[[EventRecord], str] | None = None
        self._on_select = on_select
        self._records: Sequence[EventRecord] = ()
        self._selected: int | None = None
        self._strengths: Mapping[int, float] | None = None
        self._symbols = fm.MarkerLayer(markers=[])
        #: Says so when the set is larger than what is drawn. Leaving
        #: earthquakes off the map in silence would under-report the history,
        #: the same reason an unknown verdict is still drawn.
        self.truncation = ft.Text("", size=11, color="#5A6472", visible=False)
        self._notice = ft.Container(
            visible=False,
            bgcolor="#FFFFFFE6",
            border_radius=8,
            padding=12,
            margin=40,
            content=ft.Text(
                t("map_unavailable", locale_code),
                color="#5A6472",
                text_align=ft.TextAlign.CENTER,
            ),
        )
        middle = centre if centre is not None else (0.0, 0.0)
        self.map = fm.Map(
            expand=True,
            initial_center=fm.MapLatitudeLongitude(*middle),
            initial_zoom=zoom,
            layers=[tile_layer(on_error=self._tile_failed), self._symbols, attribution_layer()],
        )
        self.view = ft.Container(
            expand=True,
            border_radius=12,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Stack(
                expand=True,
                controls=[
                    self.map,
                    ft.Container(left=8, top=8, content=self._legend()),
                    # Fills the stack to centre the notice, so it must let the
                    # pointer through: above the map, an ordinary container
                    # this size takes every hover and press meant for a symbol.
                    ft.TransparentPointer(
                        content=ft.Container(alignment=ft.Alignment.CENTER, content=self._notice)
                    ),
                ],
            ),
        )

    def show(
        self,
        records: Sequence[EventRecord],
        *,
        total: int | None = None,
        describe: Callable[[EventRecord], str] | None = None,
        selected: Any = _KEEP,
        strengths: Mapping[int, float] | None = None,
    ) -> None:
        """Draws those arrivals. Called again whenever the filters change.

        `total` is how many the filter matches; when it is more than what was
        handed over, the legend says how many of how many are on the map.

        `describe` words an arrival for its tooltip (REQ-MAP-006). The map does
        not word it itself: the list already has, for the table, and a second
        wording would be a second chance to disagree.

        `strengths` draws some of them weaker, by row id -- a frame of the
        playback. It belongs to this call: showing again without it draws
        everything in full.
        """
        self._describe = describe
        self._records = records
        self._strengths = strengths
        if selected is not _KEEP:
            self._selected = selected
        self._draw()
        cut_short = total is not None and total > len(records)
        self.truncation.visible = cut_short
        self.truncation.value = (
            t("map_truncated", self._locale, shown=len(records), total=total) if cut_short else ""
        )

    def select(self, row_id: int | None) -> None:
        """Highlights the symbol of that row, or none. The set drawn is unchanged."""
        self._selected = row_id
        self._draw()

    def press(self, row_id: int) -> None:
        """A symbol was pressed: say which row it stands for."""
        if self._on_select is not None:
            self._on_select(row_id)

    def _draw(self) -> None:
        self.markers = plan(self._records, selected=self._selected, strengths=self._strengths)
        self._symbols.markers = [self._symbol(marker) for marker in self.markers]

    def _symbol(self, marker: Marker) -> Any:
        """One planned symbol as a control: a round container that can be pointed at."""
        diameter = 2 * marker.radius
        return fm.Marker(
            coordinates=fm.MapLatitudeLongitude(marker.latitude, marker.longitude),
            width=diameter,
            height=diameter,
            content=ft.Container(
                opacity=marker.strength,
                border_radius=marker.radius if marker.style.round else SQUARE_CORNER,
                bgcolor=(
                    ft.Colors.with_opacity(0.75, marker.style.fill) if marker.style.filled else None
                ),
                border=ft.Border.all(
                    SELECTED_RING if marker.selected else RING, marker.style.outline
                ),
                tooltip=self._describe(marker.record) if self._describe is not None else None,
                on_click=(
                    (lambda _event, row_id=marker.record.id: self.press(row_id))
                    if marker.record.id is not None
                    else None
                ),
            ),
        )

    def _tile_failed(self, event: Any) -> None:
        if self.available:
            self._log.warning("map_tile_failed detail=%s", getattr(event, "data", None))
        self.available = False
        self._notice.visible = True

    def _legend(self) -> Any:
        """The legend is on screen whatever else is not (CA-112.5)."""

        def entry(style: MarkerStyle) -> Any:
            return ft.Row(
                spacing=6,
                controls=[
                    ft.Container(
                        width=12,
                        height=12,
                        border_radius=6 if style.round else SQUARE_CORNER,
                        bgcolor=style.fill or None,
                        border=ft.Border.all(2, style.outline),
                    ),
                    ft.Text(t(style.legend_key, self._locale), size=12, color="#1B2028"),
                ],
            )

        return ft.Container(
            bgcolor="#FFFFFFD9",
            border_radius=8,
            padding=8,
            content=ft.Column(
                spacing=4,
                controls=[
                    *(entry(style) for style in LEGEND),
                    ft.Text(t("map_legend_size", self._locale), size=11, color="#5A6472"),
                    self.truncation,
                ],
            ),
        )
