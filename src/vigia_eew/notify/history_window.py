"""The history window: one filter, two readings of it (REQ-MAP-004, CA-112.6).

The table and the map answer the same question in two ways, so there is one
filter and both obey it. A map still showing symbols the table has filtered
away is not a second opinion -- it is the product contradicting itself on one
screen.

This module exists so that neither view has to know about the other. The list
must stay free of the map: it is the part that works with no network, no
tiles and no third party, and a test on its imports keeps it that way
([[lat.md/history#The map is a view on the list, never the other way round]]).
So the wiring lives here, above both of them, and the direction is one-way --
the map is fed the records the list produced, and never the reverse.
"""

from __future__ import annotations

from typing import Any

from vigia_eew.history import HistoryStore
from vigia_eew.i18n import DEFAULT_LOCALE
from vigia_eew.notify.history_map import DEFAULT_ZOOM, HistoryMap, TileSource, centre_of
from vigia_eew.notify.history_view import HistoryList, HistoryView
from vigia_eew.notify.presentation import VENEZUELA_ZONE


class HistoryWindow:
    """The table over the map, both reading the same query."""

    def __init__(
        self,
        master: Any,
        store: HistoryStore,
        *,
        locale_code: str = DEFAULT_LOCALE,
        zone: str = VENEZUELA_ZONE,
        tiles: TileSource | None = None,
        reference: tuple[float, float] | None = None,
        zoom: int = DEFAULT_ZOOM,
    ) -> None:
        from tkinter import ttk

        self.listing = HistoryList(store, locale_code=locale_code, zone=zone)
        frame = ttk.Frame(master)
        frame.pack(fill="both", expand=True)
        # The map is centred on what the history actually holds, falling back
        # to the agent's reference point so that an empty history opens on
        # somewhere the user recognises rather than in the Atlantic.
        centre = centre_of(self.listing.records(), fallback=reference or (10.4806, -66.9036))
        self.map = HistoryMap(frame, tiles=tiles, locale_code=locale_code, zoom=zoom, centre=centre)
        self.view = HistoryView(
            frame, self.listing, locale_code=locale_code, on_changed=self._redraw_map
        )
        self._redraw_map()

    def refresh(self) -> None:
        """Redraws both views from the current filter."""
        self.view.refresh()

    def _redraw_map(self) -> None:
        """Called by the table whenever what it shows has changed.

        One direction only: the list decides the set and the map follows it.
        """
        self.map.show(self.listing.records())
