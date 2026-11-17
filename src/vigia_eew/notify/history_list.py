"""What the history shows, and the one filter every view of it obeys (REQ-HIS-005).

`HistoryList` decides -- what is shown, in what order, phrased how, on which
page -- and draws nothing. It lives in a module of its own, with no toolkit
in it, because two frontends read the history through it: the window, in Flet
controls, and the terminal dashboard, in Textual ones (ADR-041). A terminal
on a machine with no display must not load the graphical toolkit to list a
history, and a filter written twice is a filter that comes to mean two things
([[lat.md/history#The list owns the filters and the paging]]).

It depends on nothing but the local file -- no network, no tiles, no third
party -- and a test on its imports keeps it that way
([[lat.md/history#The map is a view on the list, never the other way round]]).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

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
    return replace(query, **changes)


# --- What a filter field holds ----------------------------------------------------
#
# Shared by the frontends: a half-typed number is "not a filter yet" in a
# terminal for the reason it is in a window.

#: How a day is typed into the period fields.
DATE_HINT = "YYYY-MM-DD"

#: "Not a value yet": what a half-typed number or date parses to. Distinct from
#: `None`, which is a value -- an empty field means "no bound".
NOT_YET: Any = object()


def number_in(raw: str | None) -> Any:
    """The number in a field: None when empty, `NOT_YET` while it does not parse."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return NOT_YET


def day_in(raw: str | None) -> Any:
    """The day in a field: None when empty, `NOT_YET` while it does not parse."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return NOT_YET


def rows_for(store: HistoryStore, query: HistoryQuery) -> Sequence[EventRecord]:
    """The records a query selects, for a view that wants them unformatted."""
    return store.query(query)
