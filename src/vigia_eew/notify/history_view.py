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
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import flet as ft

from vigia_eew.history import ORDERABLE, EventRecord, HistoryQuery, HistoryStore
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify.presentation import VENEZUELA_ZONE, format_moment
from vigia_eew.timeutil import local_day_bounds

#: Rows on a page, which is what the table draws. A Flutter `DataTable` lays
#: out every cell up front, and 500 rows of seven cells took the screen several
#: seconds to appear. The rows past this are reached by paging (REQ-HIS-008),
#: not left out.
TABLE_ROW_LIMIT = 150


@dataclass(frozen=True, slots=True)
class Column:
    """One column of the table, declared once for the header and the row."""

    key: str
    label_key: str
    #: The field of the stored row this column sorts by, or None when sorting
    #: it would produce an order nobody means.
    sort_key: str | None = None
    width: int = 120


#: The header and the row are built from this one list, so they cannot come to
#: disagree about how many columns there are or what order they go in.
COLUMNS: tuple[Column, ...] = (
    Column("time", "history_column_time", "occurred_at", width=160),
    Column("magnitude", "history_column_magnitude", "magnitude", width=90),
    Column("place", "history_column_place", None, width=280),
    Column("distance", "history_column_distance", "distance_km", width=90),
    Column("source", "history_column_source", "source", width=100),
    Column("verdict", "history_column_verdict", "verdict", width=100),
    Column("reason", "history_column_reason", None, width=220),
)

#: Every reason the pipeline can attach to a discard, and the phrase for it.
#: The filter produces the first four and the deduplicator the fifth; a reason
#: added upstream without a phrase here fails the test that compares the two
#: sets, rather than reaching the user as the pipeline's internal word.
REASONS: dict[str, str] = {
    "radius": "history_reason_radius",
    "magnitude": "history_reason_magnitude",
    "country": "history_reason_country",
    "freshness": "history_reason_freshness",
    "duplicate": "history_reason_duplicate",
}


@dataclass(frozen=True, slots=True)
class Row:
    """One arrival, formatted for reading rather than for arithmetic."""

    time: str
    magnitude: str
    place: str
    distance: str
    source: str
    verdict: str
    reason: str
    #: Kept alongside the strings because the map draws from the same rows and
    #: needs the numbers the table has already turned into text.
    record: EventRecord

    @property
    def summary(self) -> str:
        """The entry in three lines, for a view that has room for one earthquake.

        What a symbol on the map says when it is pointed at (REQ-MAP-006). It
        is put together from the strings above and nothing else, so a symbol
        and its row cannot come to describe the same earthquake differently.
        """
        verdict = f"{self.verdict} — {self.reason}" if self.reason else self.verdict
        lines = [f"{self.magnitude} · {self.time}", self.place, f"{self.distance} · {verdict}"]
        return "\n".join(line for line in lines if line)


@dataclass(frozen=True, slots=True)
class Everything:
    """The filtered set in full, as far as the caller asked for it."""

    records: list[EventRecord]
    #: How many the filter matches. More than `records` when it was cut short.
    total: int

    @property
    def truncated(self) -> bool:
        return len(self.records) < self.total


class HistoryList:
    """What the table shows, and the single filter both views obey.

    The query object is deliberately exposed: the map reads the very query the
    table ran, which is how one filter can govern two views without either of
    them owning the other (REQ-MAP-004).

    Every filter and the page live here, not in the controls
    ([[lat.md/history#The list owns the filters and the paging]]). The
    controls only set them, which is what lets a second frontend -- the
    terminal -- offer the same filters without writing them again.
    """

    def __init__(
        self,
        store: HistoryStore,
        *,
        locale_code: str = DEFAULT_LOCALE,
        zone: str = VENEZUELA_ZONE,
        page_size: int = TABLE_ROW_LIMIT,
        rank: Sequence[str] = (),
    ) -> None:
        self._store = store
        self._locale = locale_code
        self._zone = zone
        self.page_size = page_size
        #: `rank` is the networks in the user's order of trust, best first. It
        #: decides nothing until two arrivals of one earthquake are otherwise
        #: equal (ADR-034), and it is handed in so the list need not know
        #: where that order is configured.
        self.query = HistoryQuery(limit=page_size, rank=tuple(rank))
        self.rows: list[Row] = []
        self.total = 0
        self.available_sources: list[str] = []
        self.available_verdicts: list[str] = []
        self.refresh()

    # --- Reading ---

    def refresh(self) -> None:
        """Runs the current query and formats what came back."""
        self.query = _replace(self.query, limit=self.page_size)
        records = self._store.query(self.query)
        self.rows = [self._format(record) for record in records]
        self.total = self._store.count(self.query)
        self.available_sources = self._store.sources()
        self.available_verdicts = self._store.verdicts()

    def _format(self, record: EventRecord) -> Row:
        return Row(
            time=format_moment(record.occurred_at, self._zone),
            magnitude=f"M {record.magnitude:.1f}",
            place=record.region or "",
            distance=f"{record.distance_km:.0f} km",
            source=record.source,
            verdict=t(f"history_verdict_{record.verdict}", self._locale),
            reason=self._reason(record),
            record=record,
        )

    def _reason(self, record: EventRecord) -> str:
        """The phrase for a discard, or the raw word when there is none.

        An unphrased reason is still shown. A row the product cannot put into
        words is a row somebody needs to see more, not less.
        """
        if record.verdict == "recovered":
            # Not a discard's reason: nobody decided anything about this row.
            # It is the honest answer to "why was I not warned?" for it.
            return t("history_reason_recovered", self._locale)
        if not record.reason:
            return ""
        key = REASONS.get(record.reason)
        return t(key, self._locale) if key else record.reason

    # --- Filtering and sorting ---

    def set_filter(self, **criteria: Any) -> None:
        """Narrows the view. Both views read the result, so there is one of these."""
        self.query = _replace(self.query, offset=0, **criteria)
        self.refresh()

    def set_period(self, first_day: date | None, last_day: date | None) -> None:
        """Keeps the arrivals of those local calendar days, both inclusive.

        Days are the user's, in the configured zone; either may be `None`. A
        period that ends before it starts raises `ValueError` and leaves the
        query -- and so what is on screen -- as it was (CA-114.4).
        """
        since, until = local_day_bounds(first_day, last_day, self._zone)
        self.set_filter(since=since, until=until)

    def set_min_magnitude(self, magnitude: float | None) -> None:
        self.set_filter(min_magnitude=magnitude)

    def set_max_distance(self, kilometres: float | None) -> None:
        self.set_filter(max_distance_km=kilometres)

    def set_verdict(self, verdict: str | None) -> None:
        self.set_filter(verdict=verdict)

    def set_sources(self, names: Sequence[str]) -> None:
        """Keeps the arrivals of those networks; none chosen means all of them."""
        self.set_filter(sources=tuple(names))

    def clear_filters(self) -> None:
        # The reading is not a filter: it is how the set is looked at, and
        # clearing what narrows the set leaves it alone.
        self.query = HistoryQuery(
            order_by=self.query.order_by,
            descending=self.query.descending,
            limit=self.page_size,
            reading=self.query.reading,
            rank=self.query.rank,
        )
        self.refresh()

    # --- One row per arrival, or one per earthquake (REQ-HIS-009) ---

    @property
    def reading(self) -> str:
        return self.query.reading

    def set_reading(self, reading: str) -> None:
        """Reads the same rows per arrival or per earthquake (ADR-034).

        Everything that reads the query follows -- the rows, the total, the
        whole set the map draws -- because the reading travels in it. It
        returns to the first page for the reason a filter does.
        """
        self.set_filter(reading=reading)

    def arrivals_of(self, record: EventRecord) -> list[Row]:
        """Every arrival of that record's earthquake, worded as the table words them.

        The per-earthquake reading shows one arrival and this is the rest
        (CA-115.5): *it came by two networks and this one prevailed* is still
        there to be read. An arrival tied to nothing is its own only arrival.
        """
        arrivals = self._store.arrivals(record.correlation_id) or [record]
        return [self._format(arrival) for arrival in arrivals]

    def sort_by(self, column_key: str) -> None:
        """Sorts by a column, reversing it when it is already the one in use.

        A column with no sort key is left alone: `place` is free text from four
        different catalogues, and ordering it would produce something that
        looks meaningful and is not.
        """
        column = next((c for c in COLUMNS if c.key == column_key), None)
        if column is None or column.sort_key is None or column.sort_key not in ORDERABLE:
            return
        descending = not self.query.descending if self.query.order_by == column.sort_key else True
        self.set_filter(order_by=column.sort_key, descending=descending)

    # --- Paging (REQ-HIS-008) ---

    @property
    def stretch(self) -> tuple[int, int, int]:
        """The first and last entry on screen, counted from one, and the total.

        A history that hides rows without saying which does not answer "why
        was I not warned?" for those rows. `(0, 0, 0)` when nothing matches.
        """
        if not self.rows:
            return (0, 0, self.total)
        return (self.query.offset + 1, self.query.offset + len(self.rows), self.total)

    @property
    def stretch_text(self) -> str:
        first, last, total = self.stretch
        return t("history_stretch", self._locale, first=first, last=last, total=total)

    @property
    def has_previous(self) -> bool:
        return self.query.offset > 0

    @property
    def has_next(self) -> bool:
        return self.query.offset + len(self.rows) < self.total

    def next_page(self) -> None:
        if self.has_next:
            self._turn_to(self.query.offset + self.page_size)

    def previous_page(self) -> None:
        if self.has_previous:
            self._turn_to(max(0, self.query.offset - self.page_size))

    def _turn_to(self, offset: int) -> None:
        self.query = _replace(self.query, offset=offset)
        self.refresh()

    def go_to(self, row_id: int, *, limit: int) -> bool:
        """Turns to the page that holds that row; False if it is not in the set.

        What a symbol pressed on the map needs (REQ-MAP-007): its row may be
        on a page the table is not showing. `limit` is how far into the set to
        look -- the caller knows it, because the symbol came from that stretch.
        """
        for position, record in enumerate(self.everything(limit).records):
            if record.id == row_id:
                self._turn_to(position - position % self.page_size)
                return True
        return False

    def records(self) -> list[EventRecord]:
        """The stored rows behind what is on screen.

        The map draws from these, so that the two views cannot come to show
        different sets: one query, one list of records, two readings of it
        (REQ-MAP-004).
        """
        return [row.record for row in self.rows]

    @property
    def filter_signature(self) -> tuple[Any, ...]:
        """What the filters select, and nothing about how it is looked at.

        Unchanged by turning a page, sorting or switching the reading. A view
        that holds the set -- the playback -- compares it to know whether the
        set it holds is still the one the filters select.
        """
        query = self.query
        return (
            query.since,
            query.until,
            query.min_magnitude,
            query.max_distance_km,
            query.verdict,
            query.sources,
        )

    def everything(
        self, limit: int, *, reading: str | None = None, newest_first: bool = False
    ) -> Everything:
        """The whole filtered set in the table's order, up to `limit` of it.

        The table pages; a map does not. A map that drew only the page would
        move its symbols every time the page was turned, and "the same set"
        (REQ-MAP-004) would have come to mean "the same 150 rows". So the views
        that draw the set -- the map, and later the playback -- read this, and
        say so when `limit` cut it short.

        `reading` asks for the set in a reading other than the table's, and
        `newest_first` for the most recent of it whatever the table is sorted
        by: the playback reads earthquakes, and when there are too many it
        plays the latest (ADR-035). Neither changes what the table shows.
        """
        request = _replace(self.query, limit=limit, offset=0)
        if newest_first:
            request = _replace(request, order_by="occurred_at", descending=True)
        if reading is None or reading == self.query.reading:
            return Everything(self._store.query(request), self.total)
        request = _replace(request, reading=reading)
        return Everything(self._store.query(request), self._store.count(request))

    def whole(self, reading: str | None = None) -> list[EventRecord]:
        """The filtered set with no bound, in the table's order.

        What the figures and the export read (ADR-038): a summary of the first
        five hundred, or a file holding them, would be a claim about a set
        nobody asked for. The retentions are what bound it. `reading` asks for
        it in a reading other than the one on screen -- the figures need both.
        """
        # A negative limit is SQLite's way of saying "all of them".
        request = _replace(self.query, limit=-1, offset=0, reading=reading or self.query.reading)
        return self._store.query(request)

    def row_for(self, record: EventRecord) -> Row:
        """That record as the table words it, for a view that shows one entry."""
        return self._format(record)

    def label(self, column: Column) -> str:
        return t(column.label_key, self._locale)


def _replace(query: HistoryQuery, **changes: Any) -> HistoryQuery:
    """A new query with those fields changed -- `HistoryQuery` is frozen."""
    from dataclasses import replace

    return replace(query, **changes)


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
            on_click=lambda _e: self._pick_day(field),
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
        value = _number(self._magnitude.value)
        if value is _NOT_YET:
            return
        self.listing.set_min_magnitude(value)
        self.refresh()

    def _apply_distance(self) -> None:
        value = _number(self._distance.value)
        if value is _NOT_YET:
            return
        self.listing.set_max_distance(value)
        self.refresh()

    def _apply_period(self) -> None:
        """Sets the period from the two fields, or says why it cannot (CA-114.4)."""
        first, last = _day(self._since.value), _day(self._until.value)
        if first is _NOT_YET or last is _NOT_YET:
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

    def _pick_day(self, field: Any) -> None:
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


#: How a day is typed into the period fields.
DATE_HINT = "YYYY-MM-DD"

#: "Not a value yet": what a half-typed number or date parses to. Distinct from
#: `None`, which is a value -- an empty field means "no bound".
_NOT_YET: Any = object()


def _number(raw: str | None) -> Any:
    """The number in a field: None when empty, `_NOT_YET` while it does not parse."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return _NOT_YET


def _day(raw: str | None) -> Any:
    """The day in a field: None when empty, `_NOT_YET` while it does not parse."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return _NOT_YET


def _arrival_line(row: Row) -> str:
    """One arrival of an earthquake: its network, what it said, and its verdict."""
    verdict = f"{row.verdict} — {row.reason}" if row.reason else row.verdict
    return f"{row.source} · {row.magnitude} · {verdict}"


def _verdict_label(verdict: str, locale_code: str) -> str:
    """The phrase for a verdict, or the stored word when there is none yet."""
    key = f"history_verdict_{verdict}"
    label = t(key, locale_code)
    return verdict if label == key else label


def rows_for(store: HistoryStore, query: HistoryQuery) -> Sequence[EventRecord]:
    """The records a query selects, for a view that wants them unformatted."""
    return store.query(query)
