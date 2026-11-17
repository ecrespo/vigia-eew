"""The history screen: one filter, three readings of it (REQ-MAP-004, REQ-TLP-004).

The table, the map and the playback answer the same question in three ways,
so there is one filter and all of them obey it. A map still showing symbols the table has filtered
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

from collections.abc import Callable, Sequence
from typing import Any

import flet as ft

from vigia_eew.history import HistoryStore
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify import ui_scale
from vigia_eew.notify.history_map import DEFAULT_ZOOM, HistoryMap, centre_of
from vigia_eew.notify.history_view import HistoryList, HistoryView
from vigia_eew.notify.presentation import VENEZUELA_ZONE
from vigia_eew.notify.timelapse import PLAYBACK_SYMBOL_LIMIT, Frame
from vigia_eew.notify.timelapse_view import TimelapseView, Timer

#: Carries out a recovery of so many days and reports its outcome, line by
#: line, when it ends -- or returns at once the reason it will not start.
Recover = Callable[[int, Callable[[Sequence[str]], None]], str | None]

#: Height of each pane -- the table with its filters, and the map. Raised from
#: 520 when the filters went from two controls to five: the table was left
#: with room for six rows.
MAP_HEIGHT = 680

#: Symbols the static map draws at once. **Measured**: a redraw costs about
#: 0.22 ms per marker, so this many take some 110 ms -- and the static map is
#: redrawn when a filter changes, not on a timer
#: (docs/v1.1/10-SPIKE-TIMELAPSE.md §5). The playback has its own, lower
#: bound, `PLAYBACK_SYMBOL_LIMIT`, because it redraws once per step.
MAP_SYMBOL_LIMIT = 500


class HistoryWindow:
    """The table beside the map, with the playback under it, all reading one query.

    `after` is the shell's timer. With it -- and with a map -- the screen has
    a playback; without either there is nothing to advance it or to draw it
    on, and the screen is the table and the map.
    """

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
        rank: Sequence[str] = (),
        after: Timer | None = None,
        on_recover: Recover | None = None,
    ) -> None:
        self._locale = locale_code
        self._on_recover = on_recover
        self.listing = HistoryList(store, locale_code=locale_code, zone=zone, rank=rank)
        #: The filters of the set the playback holds, or None before it has one.
        self._played_signature: tuple[Any, ...] | None = None
        # The map opens on the user's reference point when there is one: the
        # history is worldwide, and the midpoint of earthquakes in Alaska and
        # Georgia is the Atlantic. Without one it falls back to the midpoint
        # of what the history holds.
        centre = reference or centre_of(self.listing.records(), fallback=(10.4806, -66.9036))
        self.map = (
            HistoryMap(
                locale_code=locale_code, zoom=zoom, centre=centre, on_select=self._symbol_pressed
            )
            if with_map
            else None
        )
        self.playback = (
            TimelapseView(
                paint=self._paint_frame,
                after=after,
                on_stop=self._draw_set,
                locale_code=locale_code,
                zone=zone,
            )
            if self.map is not None and after is not None
            else None
        )
        self.table = HistoryView(
            self.listing,
            locale_code=locale_code,
            on_changed=self._redraw_map,
            on_select=self._row_chosen,
        )
        panes: list[Any] = [
            ft.Container(
                col=ui_scale.HISTORY_TABLE_COLUMNS, height=MAP_HEIGHT, content=self.table.view
            )
        ]
        if self.map is not None:
            beside: Any = self.map.view
            if self.playback is not None:
                beside = ft.Column(
                    expand=True,
                    spacing=8,
                    controls=[
                        ft.Container(expand=True, content=self.map.view),
                        self.playback.view,
                    ],
                )
            panes.append(
                ft.Container(col=ui_scale.HISTORY_MAP_COLUMNS, height=MAP_HEIGHT, content=beside)
            )
        header: list[Any] = [
            ft.Icon(ft.Icons.HISTORY, color=ft.Colors.PRIMARY),
            ft.Text(
                t("history_title", locale_code), size=20, weight=ft.FontWeight.BOLD, expand=True
            ),
        ]
        header.extend(self._build_recovery())
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
                    self._recovery_outcome,
                    ft.Container(
                        padding=16,
                        content=ft.ResponsiveRow(controls=panes, spacing=16, run_spacing=16),
                    ),
                ],
            ),
        )
        self._redraw_map()

    # --- Completing the history from the catalogues (REQ-HIS-010) ---

    def _build_recovery(self) -> list[Any]:
        """The *Recover* action: how many days, a button, and what came of it.

        Only when somebody can carry it out. The screen does not recover
        anything itself -- it could not, without a network library -- it asks
        whoever built it, and is told the outcome later.

        The field and the button go in the header, so that they cost the
        table and the map no height; the outcome appears under it only once
        there is one to show.
        """
        self.recover_button: Any = None
        self.recover_status = ft.Text("", size=12, selectable=True, font_family="monospace")
        self._recovery_outcome = ft.Container(
            visible=False,
            padding=ft.Padding.only(left=16, right=16, top=10),
            content=self.recover_status,
        )
        if self._on_recover is None:
            return []
        loc = self._locale
        self.recover_days = ft.TextField(
            label=t("history_recover_days", loc),
            value="30",
            width=130,
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.recover_button = ft.OutlinedButton(
            content=ft.Text(t("history_recover", loc)),
            icon=ft.Icons.CLOUD_DOWNLOAD,
            tooltip=t("history_recover_hint", loc),
            on_click=lambda _e: self._recover(),
        )
        return [self.recover_days, self.recover_button]

    def _say(self, text: str) -> None:
        """Shows what became of the recovery under the header."""
        self.recover_status.value = text
        self._recovery_outcome.visible = bool(text)

    def _recover(self) -> None:
        """Asks for the days typed to be recovered. One recovery at a time."""
        if self._on_recover is None:
            return
        try:
            days = int((self.recover_days.value or "").strip())
        except ValueError:
            self._say(t("history_recover_invalid", self._locale))
            return
        self.recover_button.disabled = True
        self._say(t("history_recover_running", self._locale))
        refusal = self._on_recover(days, self._recovered)
        if refusal is not None:
            self._say(refusal)
            self.recover_button.disabled = False

    def _recovered(self, lines: Sequence[str]) -> None:
        """The recovery has ended: say what each network gave, and read the file again."""
        self._say("\n".join(lines))
        self.recover_button.disabled = False
        self.refresh()

    def refresh(self) -> None:
        """Redraws every view from the current filter, reading the file again."""
        # The agent writes while the screen is open: the set the playback
        # holds may no longer be what the same filters select.
        self._played_signature = None
        # The list first: the table draws what the list holds, and without
        # this it kept the page it had read before -- the map showed a
        # recovered earthquake the table did not.
        self.listing.refresh()
        self.table.refresh()

    def pause_playback(self) -> None:
        """Stops the playback advancing, where it is.

        What the shell is told to call when an alert covers the screen
        (REQ-TLP-006): the alert takes the window, and a timer that kept
        stepping underneath would leave the user somewhere else when they
        come back.
        """
        if self.playback is not None:
            self.playback.pause()

    def _redraw_map(self) -> None:
        """Called by the table whenever what it shows has changed.

        One direction only: the list decides the set and the map follows it.

        While the playback has the map, a change that leaves the set alone --
        a page turned, a column sorted, a row chosen -- leaves the frame on
        it. A change of filter replaces the set, and the playback lets go.
        """
        if getattr(self, "map", None) is None:
            return
        playback = getattr(self, "playback", None)  # not there yet while it is being built
        same_set = self.listing.filter_signature == self._played_signature
        if playback is not None and playback.engaged and same_set:
            table = getattr(self, "table", None)
            self.map.select(None if table is None else table.selected)  # type: ignore[union-attr]
            return
        self._draw_set()
        if playback is not None and not same_set:
            self._load_playback(playback)

    def _draw_set(self) -> None:
        """Draws the whole filtered set on the map: the static reading."""
        if self.map is None:
            return
        # The whole filtered set, not the table's page (ADR-032): turning a
        # page must not move the map.
        # @lat: [[history#The table pages, the map does not]]
        everything = self.listing.everything(MAP_SYMBOL_LIMIT)
        table = getattr(self, "table", None)  # not there yet while it is being built
        chosen = None if table is None else table.selected
        if (
            table is not None
            and chosen is not None
            and all(record.id != chosen for record in everything.records)
        ):
            # The filter removed it: a highlight on something no longer shown
            # would point at nothing.
            table.selected = chosen = None
        self.map.show(
            everything.records,
            total=everything.total,
            describe=lambda record: self.listing.row_for(record).summary,
            selected=chosen,
        )

    # --- The playback: a third reading of the same query (REQ-TLP-004) ---

    def _load_playback(self, playback: TimelapseView) -> None:
        """Hands the playback the set the filters select, per earthquake.

        Per earthquake whatever the table is reading, so that none plays
        twice; and the most recent ones when there are more than it holds,
        whatever the table is sorted by. It has no query of its own.
        """
        # @lat: [[history#The playback is a third reading of one query]]
        played = self.listing.everything(
            PLAYBACK_SYMBOL_LIMIT, reading="earthquake", newest_first=True
        )
        self._played_signature = self.listing.filter_signature
        playback.load(played.records, total=played.total)

    def _paint_frame(self, frame: Frame) -> None:
        """Draws one frame of the playback, through the map the static set uses.

        The same markers, so a paused frame answers the pointer like the
        static map does. Nothing here moves the map (REQ-TLP-008).
        """
        if self.map is None:
            return
        self.map.show(
            [record for record, _strength in frame.symbols],
            describe=lambda record: self.listing.row_for(record).summary,
            strengths={
                record.id: strength for record, strength in frame.symbols if record.id is not None
            },
        )

    # --- The table and the map point at the same thing (REQ-MAP-007) ---
    #
    # Wired here and nowhere else: the list still imports no map, and the map
    # still knows nothing about tables. Selection is keyed by the id of the row
    # a symbol stands for.

    def _row_chosen(self, row_id: int | None) -> None:
        """The user chose a row in the table: highlight its symbol."""
        if self.map is not None:
            self.map.select(row_id)

    def _symbol_pressed(self, row_id: int) -> None:
        """The user pressed a symbol: bring the table to its row and highlight it."""
        # @lat: [[history#The table and the map point at the same thing]]
        self.listing.go_to(row_id, limit=MAP_SYMBOL_LIMIT)
        self.table.select(row_id)


def unavailable_view(
    reason: str,
    *,
    locale_code: str = DEFAULT_LOCALE,
    on_close: Callable[[], None] | None = None,
) -> Any:
    """What the history screen shows when its file cannot be read (CA-113.3).

    It says so and gives the reason as the store reported it: a file from a
    newer version and a directory that cannot be read are different problems,
    and the user is the one who has to tell them apart.
    """
    header: list[Any] = [
        ft.Icon(ft.Icons.HISTORY, color=ft.Colors.PRIMARY),
        ft.Text(t("history_title", locale_code), size=20, weight=ft.FontWeight.BOLD, expand=True),
    ]
    if on_close is not None:
        header.append(ft.IconButton(icon=ft.Icons.CLOSE, on_click=lambda _e: on_close()))
    return ft.SafeArea(
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    content=ft.Row(controls=header),
                ),
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    padding=24,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color="#5A6472"),
                            ft.Text(
                                t("history_unavailable", locale_code),
                                size=18,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(reason, color="#5A6472", selectable=True),
                        ],
                    ),
                ),
            ],
        ),
    )
