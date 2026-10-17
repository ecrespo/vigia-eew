"""The history screen: one filter, two readings of it (REQ-MAP-004, CA-112.6).

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

Responsive (ADR-030): side by side from the `lg` breakpoint, the map under the
table below it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import flet as ft

from vigia_eew.history import HistoryStore
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify import ui_scale
from vigia_eew.notify.history_map import DEFAULT_ZOOM, HistoryMap, centre_of
from vigia_eew.notify.history_view import HistoryList, HistoryView
from vigia_eew.notify.presentation import VENEZUELA_ZONE

#: Height of the map when it sits under the table on a narrow window.
MAP_HEIGHT = 520


class HistoryWindow:
    """The table beside the map, both reading the same query."""

    def __init__(
        self,
        store: HistoryStore,
        *,
        locale_code: str = DEFAULT_LOCALE,
        zone: str = VENEZUELA_ZONE,
        reference: tuple[float, float] | None = None,
        zoom: int = DEFAULT_ZOOM,
        with_map: bool = True,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.listing = HistoryList(store, locale_code=locale_code, zone=zone)
        # The map opens on the user's reference point when there is one: the
        # history is worldwide, and the midpoint of earthquakes in Alaska and
        # Georgia is the Atlantic. Without one it falls back to the midpoint
        # of what the history holds.
        centre = reference or centre_of(self.listing.records(), fallback=(10.4806, -66.9036))
        self.map = (
            HistoryMap(locale_code=locale_code, zoom=zoom, centre=centre) if with_map else None
        )
        self.table = HistoryView(self.listing, locale_code=locale_code, on_changed=self._redraw_map)
        panes: list[Any] = [
            ft.Container(
                col=ui_scale.HISTORY_TABLE_COLUMNS, height=MAP_HEIGHT, content=self.table.view
            )
        ]
        if self.map is not None:
            panes.append(
                ft.Container(
                    col=ui_scale.HISTORY_MAP_COLUMNS, height=MAP_HEIGHT, content=self.map.view
                )
            )
        header: list[Any] = [
            ft.Icon(ft.Icons.HISTORY, color=ft.Colors.PRIMARY),
            ft.Text(
                t("history_title", locale_code), size=20, weight=ft.FontWeight.BOLD, expand=True
            ),
        ]
        if on_close is not None:
            header.append(ft.IconButton(icon=ft.Icons.CLOSE, on_click=lambda _e: on_close()))
        self.view = ft.SafeArea(
            expand=True,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                        bgcolor=ft.Colors.SURFACE_CONTAINER,
                        content=ft.Row(controls=header),
                    ),
                    ft.Container(
                        padding=16,
                        content=ft.ResponsiveRow(controls=panes, spacing=16, run_spacing=16),
                    ),
                ],
            ),
        )
        self._redraw_map()

    def refresh(self) -> None:
        """Redraws both views from the current filter."""
        self.table.refresh()

    def _redraw_map(self) -> None:
        """Called by the table whenever what it shows has changed.

        One direction only: the list decides the set and the map follows it.
        """
        if getattr(self, "map", None) is not None:
            self.map.show(self.listing.records())  # type: ignore[union-attr]
