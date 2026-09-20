"""The history on a map (REQ-MAP-002, REQ-MAP-003, REQ-MAP-005, ADR-027).

Two earthquakes of magnitude 4, one fifty kilometres away and one at two
hundred and fifty, mean different things — and a table of coordinates does not
communicate that. The map does.

It is a **view on the list**, never the other way round
([[lat.md/history#The map is a view on the list, never the other way round]]).
Everything here can be unavailable — no network, no cached tiles, a provider
that is down — and the history still answers the question it exists for,
because the list is right there and depends on none of it.

What to draw is decided by `plan()`: which tiles sit where, how big each
symbol is, which symbols are alerts. It needs no display, which is what makes
"a magnitude 6 is visibly bigger than a 3" and "alerted and discarded are told
apart" checkable at all. `HistoryMap` paints what the plan already decided and
decides nothing itself.

`ImageTk` is imported at module scope on purpose: the bridge from Pillow to a
Tk canvas is exactly the kind of thing that goes missing from a frozen binary,
and an import the packager can see statically is one it will collect.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from PIL import Image, ImageTk

from vigia_eew.history import EventRecord
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.tiles import ATTRIBUTION, TILE_SIZE, TileCache, TileClient, TileRef, tile_of

#: Smallest and largest a symbol may get, in pixels. The floor keeps a
#: magnitude 1 visible and clickable; the ceiling stops a magnitude 8 from
#: covering the country it happened in.
MIN_RADIUS = 4
MAX_RADIUS = 22

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


class TileSource(Protocol):
    """Whatever can hand over a tile's bytes, or admit it cannot."""

    def tile(self, ref: TileRef) -> bytes | None: ...


@dataclass(frozen=True, slots=True)
class PlacedTile:
    """One tile and the canvas position its top-left corner goes to."""

    ref: TileRef
    x: int
    y: int
    data: bytes


@dataclass(frozen=True, slots=True)
class Marker:
    """One arrival, placed and sized."""

    x: float
    y: float
    radius: int
    style: MarkerStyle
    record: EventRecord


@dataclass(frozen=True, slots=True)
class MapDrawing:
    """Everything the canvas needs, decided before any widget is touched."""

    available: bool
    tiles: list[PlacedTile] = field(default_factory=list)
    markers: list[Marker] = field(default_factory=list)
    attribution: str = ATTRIBUTION


def marker_radius(magnitude: float) -> int:
    """How big a symbol is, from the magnitude it represents (REQ-MAP-003).

    Linear in magnitude rather than in released energy. Energy is the honest
    physical scale and it is useless here: a magnitude 7 releases about thirty
    thousand times what a 4 does, which on a screen is either a dot or a
    continent. What the criterion asks for is that the order be readable and
    a 6 be visibly bigger than a 3, and that is what this gives.
    """
    radius = MIN_RADIUS + max(0.0, magnitude) * 2.4
    return int(min(MAX_RADIUS, max(MIN_RADIUS, radius)))


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


def plan(
    records: Sequence[EventRecord],
    *,
    tiles: TileSource,
    zoom: int,
    width: int,
    height: int,
    centre: tuple[float, float] | None = None,
    logger: logging.Logger | None = None,
) -> MapDrawing:
    """Works out the whole drawing without touching a widget.

    A tile that cannot be had is left out rather than waited for, and a map
    with **no** tiles at all declares itself unavailable and draws no markers:
    a symbol at a pixel with no geography under it is a picture of nowhere
    (REQ-MAP-002). One tile in hand is still a map, so a partly cached zone
    draws what it has instead of throwing away a usable cache.
    """
    log = logger or logging.getLogger("vigia_eew.notify.history_map")
    middle = centre if centre is not None else centre_of(records, fallback=(0.0, 0.0))
    centre_x, centre_y = tile_of(middle[0], middle[1], zoom)
    origin_x = centre_x * TILE_SIZE - width / 2
    origin_y = centre_y * TILE_SIZE - height / 2

    placed = _fetch_tiles(
        tiles,
        middle,
        zoom=zoom,
        width=width,
        height=height,
        origin=(origin_x, origin_y),
        log=log,
    )
    if not placed:
        return MapDrawing(available=False)

    markers = [
        Marker(
            x=tile_of(record.latitude, record.longitude, zoom)[0] * TILE_SIZE - origin_x,
            y=tile_of(record.latitude, record.longitude, zoom)[1] * TILE_SIZE - origin_y,
            radius=marker_radius(record.magnitude),
            style=marker_style(record.verdict),
            record=record,
        )
        for record in records
    ]
    return MapDrawing(available=True, tiles=placed, markers=markers)


def _fetch_tiles(
    tiles: TileSource,
    centre: tuple[float, float],
    *,
    zoom: int,
    width: int,
    height: int,
    origin: tuple[float, float],
    log: logging.Logger,
) -> list[PlacedTile]:
    """Asks for the tiles under the viewport; keeps the ones that came back."""
    from vigia_eew.tiles import tiles_covering

    placed = []
    for ref in tiles_covering(centre[0], centre[1], zoom=zoom, width=width, height=height):
        try:
            data = tiles.tile(ref)
        except Exception as exc:  # noqa: BLE001 - a map that degrades, not a window that falls
            log.warning("map_tile_failed ref=%s detail=%s", ref.name, exc)
            continue
        if data is not None:
            placed.append(
                PlacedTile(
                    ref=ref,
                    x=int(ref.x * TILE_SIZE - origin[0]),
                    y=int(ref.y * TILE_SIZE - origin[1]),
                    data=data,
                )
            )
    return placed


# --- The canvas ------------------------------------------------------------------


class HistoryMap:
    """The map widget: tiles, symbols, a legend and the attribution.

    Decides nothing -- `plan` already did. What is left here is Tk, and the
    one piece of Tk trivia that matters: a `PhotoImage` nobody holds a
    reference to is garbage-collected, and the tile silently disappears from
    the canvas. `self._images` exists for exactly that.
    """

    def __init__(
        self,
        master: Any,
        *,
        tiles: TileSource | None = None,
        locale_code: str = DEFAULT_LOCALE,
        width: int = TILE_SIZE * 3,
        height: int = TILE_SIZE * 2,
        zoom: int = DEFAULT_ZOOM,
        centre: tuple[float, float] | None = None,
    ) -> None:
        import tkinter as tk

        self._tiles: TileSource = tiles if tiles is not None else TileClient(TileCache())
        self._locale = locale_code
        self._width = width
        self._height = height
        self._zoom = zoom
        self._centre = centre
        self._images: list[Any] = []
        self.drawing = MapDrawing(available=False)
        self.canvas = tk.Canvas(master, width=width, height=height, background="#EEF1F5")
        self.canvas.pack(fill="both", expand=True)

    def show(self, records: Sequence[EventRecord]) -> None:
        """Draws those arrivals. Called again whenever the filters change."""
        self.drawing = plan(
            records,
            tiles=self._tiles,
            zoom=self._zoom,
            width=self._width,
            height=self._height,
            centre=self._centre,
        )
        self._paint()

    def _paint(self) -> None:
        self.canvas.delete("all")
        self._images.clear()
        if self.drawing.available:
            self._paint_tiles()
            self._paint_markers()
        else:
            self._paint_unavailable()
        self._paint_legend()

    def _paint_tiles(self) -> None:
        for tile in self.drawing.tiles:
            try:
                # `master=` is not optional here, whatever the signature says.
                # A `PhotoImage` binds to an interpreter, and without being
                # told which it takes the default one -- which is the wrong
                # one the moment a second Tk root exists in the process. The
                # symptom is `image "pyimage2" doesn't exist` at draw time,
                # and it was the GUI smoke that produced it.
                image = ImageTk.PhotoImage(Image.open(io.BytesIO(tile.data)), master=self.canvas)
            except Exception:  # noqa: BLE001 - a corrupt tile is one blank square
                continue
            # Held here because Tk keeps no reference of its own: without this
            # list the image is collected and the tile vanishes.
            self._images.append(image)
            self.canvas.create_image(tile.x, tile.y, image=image, anchor="nw")

    def _paint_markers(self) -> None:
        for marker in self.drawing.markers:
            style = marker.style
            self.canvas.create_oval(
                marker.x - marker.radius,
                marker.y - marker.radius,
                marker.x + marker.radius,
                marker.y + marker.radius,
                fill=style.fill,
                outline=style.outline,
                width=2,
            )

    def _paint_unavailable(self) -> None:
        self.canvas.create_text(
            self._width / 2,
            self._height / 2,
            text=t("map_unavailable", self._locale),
            width=self._width - 40,
            justify="center",
            fill="#5A6472",
        )

    def _paint_legend(self) -> None:
        """The legend and the attribution are on screen whatever else is not.

        The attribution because the licence requires it wherever a tile is
        (REQ-MAP-005), and the legend because a symbol nobody can read is not
        an explanation (CA-112.5).
        """
        entries = (
            (ALERTED_STYLE, t("map_legend_alerted", self._locale)),
            (DISCARDED_STYLE, t("map_legend_discarded", self._locale)),
        )
        y = 16
        for style, label in entries:
            self.canvas.create_oval(
                12, y - 5, 22, y + 5, fill=style.fill, outline=style.outline, width=2
            )
            self.canvas.create_text(32, y, text=label, anchor="w", fill="#1B2028")
            y += 20
        self.canvas.create_text(
            32, y, text=t("map_legend_size", self._locale), anchor="w", fill="#5A6472"
        )
        self.canvas.create_text(
            self._width - 8,
            self._height - 8,
            text=self.drawing.attribution,
            anchor="se",
            fill="#1B2028",
        )


def map_factory(
    locale_code: str = DEFAULT_LOCALE,
) -> Callable[[Any], HistoryMap]:
    """Builds a map bound to the real tile client, once somebody opens one."""
    return lambda master: HistoryMap(master, locale_code=locale_code)
