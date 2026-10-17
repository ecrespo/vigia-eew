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
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
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
    "MAX_RADIUS",
    "MIN_RADIUS",
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


@dataclass(frozen=True, slots=True)
class MarkerStyle:
    """How one class of arrival looks.

    Colour is not the only difference, deliberately. An alert is filled and a
    discard is an outline, so the distinction survives a screenshot, a
    printout, and a reader who cannot tell the two colours apart.
    """

    fill: str
    outline: str
    filled: bool
    legend_key: str


ALERTED_STYLE = MarkerStyle(
    fill="#D32F2F", outline="#7F1010", filled=True, legend_key="map_legend_alerted"
)
DISCARDED_STYLE = MarkerStyle(
    fill="", outline="#5A6472", filled=False, legend_key="map_legend_discarded"
)


@dataclass(frozen=True, slots=True)
class Marker:
    """One arrival, placed and sized."""

    latitude: float
    longitude: float
    radius: int
    style: MarkerStyle
    record: EventRecord


def marker_style(verdict: str) -> MarkerStyle:
    """The look for a verdict. Anything unrecognised is drawn as a discard.

    Leaving an unknown verdict off the map would silently under-report the
    history, which is worse than drawing it in the more modest of the two
    styles.
    """
    return ALERTED_STYLE if verdict == "alerted" else DISCARDED_STYLE


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


def plan(records: Sequence[EventRecord]) -> list[Marker]:
    """Works out every symbol without touching a control.

    Every record is placed -- the map does not get to drop one the table is
    showing (CA-112.6). Alerts go last so they are drawn over discards.
    """
    markers = [
        Marker(
            latitude=record.latitude,
            longitude=record.longitude,
            radius=marker_radius(record.magnitude),
            style=marker_style(record.verdict),
            record=record,
        )
        for record in records
    ]
    return sorted(markers, key=lambda marker: marker.style.filled)


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
        logger: logging.Logger | None = None,
    ) -> None:
        self._locale = locale_code
        self._log = logger or logging.getLogger("vigia_eew.notify.history_map")
        self.available = True
        self.markers: list[Marker] = []
        self._circles = fm.CircleLayer(circles=[])
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
            layers=[tile_layer(on_error=self._tile_failed), self._circles, attribution_layer()],
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
                    ft.Container(alignment=ft.Alignment.CENTER, content=self._notice),
                ],
            ),
        )

    def show(self, records: Sequence[EventRecord]) -> None:
        """Draws those arrivals. Called again whenever the filters change."""
        self.markers = plan(records)
        self._circles.circles = [
            fm.CircleMarker(
                coordinates=fm.MapLatitudeLongitude(marker.latitude, marker.longitude),
                radius=marker.radius,
                color=(
                    ft.Colors.with_opacity(0.75, marker.style.fill)
                    if marker.style.filled
                    else ft.Colors.TRANSPARENT
                ),
                border_color=marker.style.outline,
                border_stroke_width=2,
            )
            for marker in self.markers
        ]

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
                        border_radius=6,
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
                    entry(ALERTED_STYLE),
                    entry(DISCARDED_STYLE),
                    ft.Text(t("map_legend_size", self._locale), size=11, color="#5A6472"),
                ],
            ),
        )
