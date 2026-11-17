"""The history, as a table somebody can read (REQ-HIS-005, HU-111).

This is where the history stops being a file and becomes an answer. Somebody
asks *"why was I not warned about that earthquake?"*, and the reply is a row
with a reason in it -- "outside the radius", "below the minimum magnitude",
"already reported by another network".

The plan is explicit that this task, not the map, carries the feature: if
scope had to be cut, the map goes and this stays. So it depends on nothing
but the local file -- no network, no tiles, no third party -- and there is a
test that fails if this module so much as mentions one
([[lat.md/history#The map is a view on the list, never the other way round]]).

Split the same way as the configuration panel, for the same reason:
`HistoryList` decides -- what is shown, in what order, phrased how -- and
needs no display; `HistoryView` only draws it, in Flet controls (ADR-030).
The list lives in `history_list`, with no toolkit in it, so that the terminal
can read the history through the same one (ADR-041).
"""

from __future__ import annotations

from typing import Any

import flet as ft

from vigia_eew.history import EventRecord
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify.history_list import (
    COLUMNS,
    DATE_HINT,
    NOT_YET,
    REASONS,
    TABLE_ROW_LIMIT,
    Column,
    Everything,
    HistoryList,
    Row,
    day_in,
    number_in,
    rows_for,
)

#: The list and what it is made of are handed out from here too: the view is
#: where callers have always asked for them.
__all__ = [
    "COLUMNS",
    "DATE_HINT",
    "REASONS",
    "TABLE_ROW_LIMIT",
    "Column",
    "Everything",
    "HistoryList",
    "HistoryView",
    "Row",
    "rows_for",
]

# --- The controls ----------------------------------------------------------------


class HistoryView:
    """The table itself: headers that sort, filters above, a pager below.

    Decides nothing. Every question it displays an answer to was answered by
    `HistoryList`, which is why those answers are testable without a screen.
    The filters sit in a `ResponsiveRow` (one per line on a narrow window) and
    the table scrolls sideways rather than squeezing its columns (ADR-030).

    There is a control for each criterion the store can filter by (REQ-HIS-007).
    v1.0 offered two of the five, and the requirement was marked met because a
    test on the store passed: `filters` exists so that a test can ask the
    screen, not the store, what can be set from it.
    """

    def __init__(
        self,
        listing: HistoryList,
        *,
        locale_code: str = DEFAULT_LOCALE,
        on_changed: Any = None,
        on_select: Any = None,
    ) -> None:
        self.listing = listing
        self._locale = locale_code
        self._on_changed = on_changed
        self._on_select = on_select
        #: The id of the row the user chose, or None. Kept by id rather than by
        #: position: the row may leave the page and still be the one chosen.
        self.selected: int | None = None
        #: The record behind `selected`, kept from when it was last on the page.
        self._chosen: EventRecord | None = None
        self._chosen_sources: list[str] = []
        filters = self._build_filters()
        self.table = self._build_table()
        self.status = ft.Text("", italic=True)
        self.view = ft.Column(
            expand=True,
            spacing=8,
            controls=[
                filters,
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[ft.Row(scroll=ft.ScrollMode.AUTO, controls=[self.table])],
                    ),
                ),
                self.arrivals,
                self._build_pager(),
            ],
        )
        self.refresh()

    # --- Building ---

    def _build_filters(self) -> Any:
        loc = self._locale
        self._since = self._date_field("history_filter_since")
        self._until = self._date_field("history_filter_until")
        self._period_error = ft.Text(
            t("history_period_invalid", loc), color=ft.Colors.ERROR, size=12, visible=False
        )
        self._magnitude = ft.TextField(
            label=t("history_filter_magnitude", loc),
            keyboard_type=ft.KeyboardType.NUMBER,
            dense=True,
            on_change=lambda _e: self._apply_magnitude(),
        )
        self._distance = ft.TextField(
            label=t("history_filter_distance", loc),
            keyboard_type=ft.KeyboardType.NUMBER,
            dense=True,
            on_change=lambda _e: self._apply_distance(),
        )
        self._any = t("history_filter_any", loc)
        self._verdict = ft.Dropdown(
            label=t("history_filter_verdict", loc),
            value=self._any,
            dense=True,
            expand=True,
            options=[],
            on_select=lambda _e: self._apply_verdict(),
        )
        self._source_chips = ft.Row(wrap=True, spacing=6, run_spacing=4, controls=[])
        #: Off is one row per arrival, as stored; on is one per earthquake.
        self.reading = ft.Switch(
            label=t("history_reading_earthquake", loc),
            value=self.listing.reading == "earthquake",
            on_change=lambda _e: self._apply_reading(),
        )
        #: The arrivals of the chosen earthquake, under the table. A heading
        #: and then one line each; hidden until there is one to describe.
        self.arrivals = ft.Column(spacing=2, visible=False, controls=[])
        #: Which criterion each control sets, by the names REQ-HIS-005 uses.
        self.filters: dict[str, Any] = {
            "period": (self._since, self._until),
            "magnitude": self._magnitude,
            "distance": self._distance,
            "verdict": self._verdict,
            "sources": self._source_chips,
        }
        return ft.Column(
            spacing=8,
            controls=[
                ft.ResponsiveRow(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    run_spacing=8,
                    controls=[
                        # Two to a line: the table's pane is half a window
                        # wide, and four fields across wrapped their labels.
                        ft.Container(col=6, content=self._since),
                        ft.Container(col=6, content=self._until),
                        ft.Container(col=6, content=self._magnitude),
                        ft.Container(col=6, content=self._distance),
                    ],
                ),
                self._period_error,
                self.reading,
                ft.ResponsiveRow(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    run_spacing=8,
                    controls=[
                        ft.Container(col={"xs": 12, "sm": 4}, content=self._verdict),
                        ft.Container(
                            col={"xs": 12, "sm": 5},
                            content=ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Text(t("history_filter_source", loc), size=12),
                                    ft.Container(expand=True, content=self._source_chips),
                                ],
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 3},
                            content=ft.OutlinedButton(
                                content=ft.Text(t("history_filter_clear", loc)),
                                icon=ft.Icons.FILTER_ALT_OFF,
                                on_click=lambda _e: self._clear(),
                            ),
                        ),
                    ],
                ),
            ],
        )

    def _date_field(self, label_key: str) -> Any:
        """A day typed as YYYY-MM-DD, with a calendar beside it for whoever prefers one."""
        field = ft.TextField(
            label=t(label_key, self._locale),
            hint_text=DATE_HINT,
            dense=True,
            on_change=lambda _e: self._apply_period(),
        )
        # `suffix_icon`, not `suffix`: a suffix is drawn only while the field
        # has focus or text, and a calendar nobody can see is no help.
        field.suffix_icon = ft.IconButton(
            icon=ft.Icons.CALENDAR_MONTH,
            icon_size=18,
            on_click=lambda _e: self._pickday_in(field),
        )
        return field

    def _build_table(self) -> Any:
        return ft.DataTable(
            columns=[
                ft.DataColumn(
                    label=ft.Text(self.listing.label(column), weight=ft.FontWeight.BOLD),
                    numeric=column.key in ("magnitude", "distance"),
                    on_sort=(
                        (lambda _e, key=column.key: self._sort(key))
                        if column.sort_key is not None
                        else None
                    ),
                )
                for column in COLUMNS
            ],
            rows=[],
            column_spacing=20,
            heading_row_color=ft.Colors.SURFACE_CONTAINER,
            # A row is chosen by pressing it; the column of tick boxes Flutter
            # adds to a selectable table would suggest choosing several.
            show_checkbox_column=False,
        )

    def _build_pager(self) -> Any:
        """Where in the filtered set the table is, and the way to the rest of it."""
        self._previous = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            tooltip=t("history_page_previous", self._locale),
            on_click=lambda _e: self._turn(-1),
        )
        self._next = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            tooltip=t("history_page_next", self._locale),
            on_click=lambda _e: self._turn(+1),
        )
        return ft.Row(
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[self._previous, self._next, ft.Container(expand=True, content=self.status)],
        )

    # --- Behaviour ---

    def refresh(self) -> None:
        """Redraws the table from whatever the listing currently holds."""
        listing = self.listing
        self.table.rows = [
            ft.DataRow(
                data=row.record.id,
                selected=row.record.id is not None and row.record.id == self.selected,
                on_select_change=lambda _e, row_id=row.record.id: self.choose(row_id),
                cells=[ft.DataCell(ft.Text(str(getattr(row, c.key)))) for c in COLUMNS],
            )
            for row in listing.rows
        ]
        self.status.value = (
            listing.stretch_text if listing.total else t("history_empty", self._locale)
        )
        self._previous.disabled = not listing.has_previous
        self._next.disabled = not listing.has_next
        self._offer_what_is_there()
        if self._on_changed is not None:
            self._on_changed()
        # After the listener: it may have let go of a row the set no longer holds.
        self._show_arrivals()

    def _show_arrivals(self) -> None:
        """Lists the arrivals of the chosen earthquake, in the earthquake reading.

        Per arrival every one of them is already a row, and the list would
        only repeat the table. The record is remembered from when its row was
        last on the page, so turning the page does not put the list away.
        """
        on_page = next(
            (row.record for row in self.listing.rows if row.record.id == self.selected), None
        )
        if on_page is not None:
            self._chosen = on_page
        chosen = self._chosen
        if (
            self.selected is None
            or chosen is None
            or chosen.id != self.selected
            or self.listing.reading != "earthquake"
        ):
            self.arrivals.visible = False
            self.arrivals.controls = []
            return
        rows = self.listing.arrivals_of(chosen)
        self.arrivals.controls = [
            ft.Text(
                t("history_arrivals", self._locale, count=len(rows)),
                size=12,
                weight=ft.FontWeight.BOLD,
            ),
            *(ft.Text(_arrival_line(row), size=12, selectable=True) for row in rows),
        ]
        self.arrivals.visible = True

    def _offer_what_is_there(self) -> None:
        """Lists the verdicts and networks the history holds (CA-114.3).

        Rebuilt on every refresh: what is in the file changes while the screen
        is open -- the agent is writing to it -- and a filter that offers a
        network nobody has heard from can only ever return nothing.
        """
        loc = self._locale
        self._verdict.options = [
            ft.DropdownOption(key=self._any, text=self._any),
            *(
                ft.DropdownOption(key=verdict, text=_verdict_label(verdict, loc))
                for verdict in self.listing.available_verdicts
            ),
        ]
        self._source_chips.controls = [
            ft.Chip(
                label=ft.Text(source),
                data=source,
                selected=source in self._chosen_sources,
                on_select=lambda _e, name=source: self._toggle_source(name),
            )
            for source in self.listing.available_sources
        ]

    def choose(self, row_id: int | None) -> None:
        """The user pressed that row: choose it, or let go of it if it was chosen."""
        self.select(None if row_id == self.selected else row_id)
        if self._on_select is not None:
            self._on_select(self.selected)

    def select(self, row_id: int | None) -> None:
        """Marks that row as the chosen one, without telling anybody.

        `choose` is the user acting on the table; this is the table being told
        -- by the map, when a symbol was pressed. Keeping the two apart is what
        stops a selection from echoing between the views.
        """
        self.selected = row_id
        self.refresh()

    def _sort(self, column_key: str) -> None:
        self.listing.sort_by(column_key)
        self.refresh()

    def _turn(self, step: int) -> None:
        if step > 0:
            self.listing.next_page()
        else:
            self.listing.previous_page()
        self.refresh()

    def _apply_reading(self) -> None:
        self.listing.set_reading("earthquake" if self.reading.value else "arrival")
        self.refresh()

    def _apply_magnitude(self) -> None:
        value = number_in(self._magnitude.value)
        if value is NOT_YET:
            return
        self.listing.set_min_magnitude(value)
        self.refresh()

    def _apply_distance(self) -> None:
        value = number_in(self._distance.value)
        if value is NOT_YET:
            return
        self.listing.set_max_distance(value)
        self.refresh()

    def _apply_period(self) -> None:
        """Sets the period from the two fields, or says why it cannot (CA-114.4)."""
        first, last = day_in(self._since.value), day_in(self._until.value)
        if first is NOT_YET or last is NOT_YET:
            return  # a half-typed date is not a filter yet
        try:
            self.listing.set_period(first, last)
        except ValueError:
            # The list refused and kept its query, so the table still shows the
            # entries of the last period that made sense.
            self._period_error.visible = True
            return
        self._period_error.visible = False
        self.refresh()

    def _pickday_in(self, field: Any) -> None:
        """Opens a calendar for that field. Typing the date works without it."""
        page = self._page_of(field)
        if page is None:
            return  # not on a page: nothing to open a dialog on

        def chosen(event: Any) -> None:
            picked = getattr(event.control, "value", None)
            if picked is not None:
                field.value = picked.strftime("%Y-%m-%d")
                self._apply_period()
                page.update()

        page.show_dialog(ft.DatePicker(on_change=chosen))

    @staticmethod
    def _page_of(field: Any) -> Any:
        """The page that field is on, or None before the view is shown."""
        try:
            return field.page
        except RuntimeError:
            return None

    def _apply_verdict(self) -> None:
        chosen = self._verdict.value
        self.listing.set_verdict(chosen if chosen in self.listing.available_verdicts else None)
        self.refresh()

    def _toggle_source(self, name: str) -> None:
        if name in self._chosen_sources:
            self._chosen_sources.remove(name)
        else:
            self._chosen_sources.append(name)
        self.listing.set_sources(self._chosen_sources)
        self.refresh()

    def _clear(self) -> None:
        self._since.value = self._until.value = ""
        self._magnitude.value = self._distance.value = ""
        self._verdict.value = self._any
        self._chosen_sources.clear()
        self._period_error.visible = False
        self.listing.clear_filters()
        self.refresh()


def _arrival_line(row: Row) -> str:
    """One arrival of an earthquake: its network, what it said, and its verdict."""
    verdict = f"{row.verdict} — {row.reason}" if row.reason else row.verdict
    return f"{row.source} · {row.magnitude} · {verdict}"


def _verdict_label(verdict: str, locale_code: str) -> str:
    """The phrase for a verdict, or the stored word when there is none yet."""
    key = f"history_verdict_{verdict}"
    label = t(key, locale_code)
    return verdict if label == key else label
