"""The history screen: one filter, and every reading of it (REQ-MAP-004, REQ-TLP-004).

The table, the map and the playback answer the same question in three ways,
so there is one filter and all of them obey it -- and so do the summary and
the export, which are that same set counted and that same set written out
(REQ-EST-001, REQ-HIS-014). A map still showing symbols the table has filtered
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

import contextlib
import os
import tempfile
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

import flet as ft
from platformdirs import user_documents_dir

from vigia_eew import history_export
from vigia_eew.history import EventRecord, HistoryStore
from vigia_eew.history_stats import summarise
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify import ui_scale
from vigia_eew.notify.history_map import DEFAULT_ZOOM, HistoryMap, centre_of
from vigia_eew.notify.history_stats_view import StatsView
from vigia_eew.notify.history_view import HistoryList, HistoryView
from vigia_eew.notify.presentation import VENEZUELA_ZONE
from vigia_eew.notify.timelapse import PLAYBACK_SYMBOL_LIMIT, Frame
from vigia_eew.notify.timelapse_view import TimelapseView, Timer

#: Carries out a recovery of so many days and reports its outcome, line by
#: line, when it ends -- or returns at once the reason it will not start.
Recover = Callable[[int, Callable[[Sequence[str]], None]], str | None]

#: Asks the user where to save: given the name to suggest and the directory to
#: open in, it answers with the path chosen, or None when they cancelled. It
#: raises where there is no dialog to ask with.
ChooseDestination = Callable[[str, str], Awaitable[str | None]]

#: The name an export is offered under; the format gives it its extension.
EXPORT_NAME = "vigia-eew-history"

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
        export_directory: Path | str | None = None,
        choose_destination: ChooseDestination | None = None,
    ) -> None:
        self._locale = locale_code
        self._on_recover = on_recover
        self._export_directory = Path(export_directory or user_documents_dir())
        self._choose_destination = choose_destination or _system_dialog
        self.listing = HistoryList(store, locale_code=locale_code, zone=zone, rank=rank)
        #: The filters of the set the playback holds, or None before it has one.
        self._played_signature: tuple[Any, ...] | None = None
        #: The filters of the set the summary on screen was computed over.
        self._summarised_signature: tuple[Any, ...] | None = None
        self.stats = StatsView(locale_code=locale_code, zone=zone)
        self._zone = zone
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
            on_changed=self._set_changed,
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
        header.extend(self._build_summary())
        header.extend(self._build_export())
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
                    self.export_panel,
                    self.stats_panel,
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
        self._summarised_signature = None
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

    def _set_changed(self) -> None:
        """Called by the table whenever what it shows has changed."""
        self._redraw_map()
        self._summarise()

    # --- The figures of the set (REQ-EST-001..003) ---

    def _build_summary(self) -> list[Any]:
        """The *Summary* action, and the panel it opens under the header.

        Put away until asked for: it costs the table and the map no height,
        and the whole set is not read for figures nobody is looking at.
        """
        self.stats_panel = ft.Container(
            visible=False,
            padding=ft.Padding.only(left=16, right=16, top=12),
            content=self.stats.view,
        )
        self.stats_button = ft.OutlinedButton(
            content=ft.Text(t("history_stats", self._locale)),
            icon=ft.Icons.BAR_CHART,
            tooltip=t("history_stats_hint", self._locale),
            on_click=lambda _e: self._toggle_summary(),
        )
        return [self.stats_button]

    def _toggle_summary(self) -> None:
        self.stats_panel.visible = not self.stats_panel.visible
        self._summarise()

    def _summarise(self) -> None:
        """Computes the figures of the filtered set, when they are on screen.

        Once per set: a page turned, a column sorted or the reading switched
        leaves the set -- and so its figures -- as they were. Both readings are
        read whatever the table shows, because each figure counts its own base
        (X-8): earthquakes for what is said about earthquakes, arrivals for
        what is said about networks.
        """
        panel = getattr(self, "stats_panel", None)  # not there yet while it is being built
        if panel is None or not panel.visible:
            return
        signature = self.listing.filter_signature
        if signature == self._summarised_signature:
            return
        # @lat: [[history#Figures name their base, and the export writes what is on screen]]
        self.stats.show(
            summarise(
                self.listing.whole("earthquake"), self.listing.whole("arrival"), zone=self._zone
            )
        )
        self._summarised_signature = signature

    # --- The set, written to a file of the user's (REQ-HIS-014) ---

    def _build_export(self) -> list[Any]:
        """The *Export…* action, and the panel it opens under the header.

        The destination is a path field, always: the system's dialog only
        fills it in. So the export works the same where there is no dialog to
        open -- a packaged binary on a machine without one (P-5) -- and no
        code has to find out which of the two cases it is in.
        """
        loc = self._locale
        self.export_format = ft.Dropdown(
            label=t("history_export_format", loc),
            value="csv",
            dense=True,
            width=220,
            options=[
                ft.DropdownOption(key=name, text=t(f"history_export_{name}", loc))
                for name in history_export.FORMATS
            ],
            on_select=lambda _e: self._format_chosen(),
        )
        self._offered_path = self._default_destination("csv")
        self.export_path = ft.TextField(
            label=t("history_export_path", loc), value=self._offered_path, dense=True, expand=True
        )
        self.export_browse = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("history_export_browse", loc),
            on_click=self._browse,
        )
        self.export_save = ft.FilledButton(
            content=ft.Text(t("history_export_save", loc)),
            icon=ft.Icons.SAVE_ALT,
            on_click=lambda _e: self._export(),
        )
        self.export_status = ft.Text("", size=12, selectable=True)
        self.export_panel = ft.Container(
            visible=False,
            padding=ft.Padding.only(left=16, right=16, top=12),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            self.export_format,
                            self.export_path,
                            self.export_browse,
                            self.export_save,
                        ],
                    ),
                    self.export_status,
                ],
            ),
        )
        self.export_button = ft.OutlinedButton(
            content=ft.Text(t("history_export", loc)),
            icon=ft.Icons.FILE_DOWNLOAD,
            tooltip=t("history_export_hint", loc),
            on_click=lambda _e: self._toggle_export(),
        )
        return [self.export_button]

    def _toggle_export(self) -> None:
        self.export_panel.visible = not self.export_panel.visible

    def _default_destination(self, format_name: str) -> str:
        extension = history_export.FORMATS[format_name].extension
        return str(self._export_directory / (EXPORT_NAME + extension))

    def _format_chosen(self) -> None:
        """Follows the format with the extension -- of the name it offered, not of one typed."""
        offered = self._default_destination(self.export_format.value or "csv")
        if self.export_path.value == self._offered_path:
            self.export_path.value = offered
        self._offered_path = offered

    async def _browse(self, _event: Any) -> None:
        """Asks the system's dialog where to save, and puts the answer in the field."""
        typed = Path((self.export_path.value or "").strip() or self._offered_path).expanduser()
        try:
            chosen = await self._choose_destination(typed.name, str(typed.parent))
        except Exception:  # noqa: BLE001 - whatever it was, there is no dialog here
            self.export_status.value = t("history_export_no_dialog", self._locale)
            return
        if chosen:
            self.export_path.value = chosen

    def _export(self) -> None:
        """Writes the reading on screen, whole, to the path in the field."""
        typed = (self.export_path.value or "").strip()
        if not typed:
            self.export_status.value = t("history_export_no_path", self._locale)
            return
        destination = Path(typed).expanduser()
        # The whole filtered set in the reading on screen, not the page: the
        # file holds as many entries as the table says there are (CA-118.8).
        records = self.listing.whole()
        try:
            write_export(destination, records, self.export_format.value or "csv")
        except (OSError, ValueError) as exc:
            reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
            self.export_status.value = t("history_export_failed", self._locale, reason=reason)
            return
        self.export_status.value = t(
            "history_export_done", self._locale, count=len(records), path=destination
        )

    def _redraw_map(self) -> None:
        """Follows the table on the map and in the playback.

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


def write_export(destination: Path, records: Sequence[EventRecord], format_name: str) -> None:
    """Writes those records to `destination`, whole or not at all (CA-118.12).

    To a temporary file beside the destination, renamed over it once complete
    -- the rule `state.json` and the configuration already follow -- so a disk
    that fills half-way leaves the earlier export, or nothing, and never half
    a file somebody will open as if it were all of it.
    """
    fd, tmp = tempfile.mkstemp(dir=destination.parent, suffix=".tmp")
    try:
        # `newline=""`: the tabular writer ends its own rows.
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as out:
            history_export.write(records, out, format_name)
        os.replace(tmp, destination)  # atomic on the same filesystem
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


async def _system_dialog(file_name: str, directory: str) -> str | None:
    """The system's save dialog, through the toolkit (ADR-038 §7).

    It raises wherever it cannot be opened -- off a page, or on a machine with
    no dialog to show -- and the screen then says to type the path instead.
    """
    return await ft.FilePicker().save_file(file_name=file_name, initial_directory=directory)


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
