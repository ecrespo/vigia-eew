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
needs no display; `HistoryView` only draws it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from vigia_eew.history import ORDERABLE, EventRecord, HistoryQuery, HistoryStore
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify.presentation import VENEZUELA_ZONE, format_moment


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


class HistoryList:
    """What the table shows, and the single filter both views obey.

    The query object is deliberately exposed: the map reads the very query the
    table ran, which is how one filter can govern two views without either of
    them owning the other (REQ-MAP-004).
    """

    def __init__(
        self,
        store: HistoryStore,
        *,
        locale_code: str = DEFAULT_LOCALE,
        zone: str = VENEZUELA_ZONE,
        page_size: int = 500,
    ) -> None:
        self._store = store
        self._locale = locale_code
        self._zone = zone
        self.page_size = page_size
        self.query = HistoryQuery(limit=page_size)
        self.rows: list[Row] = []
        self.total = 0
        self.available_sources: list[str] = []
        self.refresh()

    # --- Reading ---

    def refresh(self) -> None:
        """Runs the current query and formats what came back."""
        self.query = _replace(self.query, limit=self.page_size)
        records = self._store.query(self.query)
        self.rows = [self._format(record) for record in records]
        self.total = self._store.count(self.query)
        self.available_sources = self._store.sources()

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
        if not record.reason:
            return ""
        key = REASONS.get(record.reason)
        return t(key, self._locale) if key else record.reason

    # --- Filtering and sorting ---

    def set_filter(self, **criteria: Any) -> None:
        """Narrows the view. Both views read the result, so there is one of these."""
        self.query = _replace(self.query, offset=0, **criteria)
        self.refresh()

    def clear_filters(self) -> None:
        self.query = HistoryQuery(
            order_by=self.query.order_by,
            descending=self.query.descending,
            limit=self.page_size,
        )
        self.refresh()

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
        self.query = _replace(self.query, order_by=column.sort_key, descending=descending)
        self.refresh()

    def records(self) -> list[EventRecord]:
        """The stored rows behind what is on screen.

        The map draws from these, so that the two views cannot come to show
        different sets: one query, one list of records, two readings of it
        (REQ-MAP-004).
        """
        return [row.record for row in self.rows]

    def label(self, column: Column) -> str:
        return t(column.label_key, self._locale)

    @property
    def count_text(self) -> str:
        return t("history_count", self._locale, shown=len(self.rows), total=self.total)


def _replace(query: HistoryQuery, **changes: Any) -> HistoryQuery:
    """A new query with those fields changed -- `HistoryQuery` is frozen."""
    from dataclasses import replace

    return replace(query, **changes)


# --- The widget tree -------------------------------------------------------------


class HistoryView:
    """The table itself: headers that sort, filters above, a count below.

    Decides nothing. Every question it displays an answer to was answered by
    `HistoryList`, which is why those answers are testable without a screen.
    """

    def __init__(
        self,
        master: Any,
        listing: HistoryList,
        *,
        locale_code: str = DEFAULT_LOCALE,
        on_changed: Any = None,
    ) -> None:
        from tkinter import ttk

        self.listing = listing
        self._locale = locale_code
        self._on_changed = on_changed
        self.frame = ttk.Frame(master, padding=8)
        self.frame.pack(fill="both", expand=True)
        self._build_filters()
        self.table = self._build_table()
        self.status = ttk.Label(self.frame, text="")
        self.status.pack(anchor="w", pady=(6, 0))
        self.refresh()

    def _build_filters(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text=t("history_filter_magnitude", self._locale)).pack(side="left")
        self._magnitude = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self._magnitude, width=6)
        entry.pack(side="left", padx=(4, 12))
        self._magnitude.trace_add("write", lambda *_: self._apply_magnitude())

        ttk.Label(bar, text=t("history_filter_verdict", self._locale)).pack(side="left")
        self._verdict = tk.StringVar(value=t("history_filter_any", self._locale))
        verdicts = ttk.Combobox(
            bar,
            textvariable=self._verdict,
            width=12,
            state="readonly",
            values=[
                t("history_filter_any", self._locale),
                t("history_verdict_alerted", self._locale),
                t("history_verdict_discarded", self._locale),
            ],
        )
        verdicts.pack(side="left", padx=(4, 12))
        verdicts.bind("<<ComboboxSelected>>", lambda _e: self._apply_verdict())

        ttk.Button(bar, text=t("history_filter_clear", self._locale), command=self._clear).pack(
            side="left"
        )

    def _build_table(self) -> Any:
        from tkinter import ttk

        table = ttk.Treeview(
            self.frame,
            columns=tuple(column.key for column in COLUMNS),
            show="headings",
            height=18,
        )
        for column in COLUMNS:
            table.heading(
                column.key,
                text=self.listing.label(column),
                command=lambda key=column.key: self._sort(key),  # type: ignore[misc]
            )
            table.column(column.key, width=column.width, anchor="w")
        table.pack(fill="both", expand=True)
        return table

    # --- Behaviour ---

    def refresh(self) -> None:
        """Redraws the table from whatever the listing currently holds."""
        self.table.delete(*self.table.get_children())
        for row in self.listing.rows:
            self.table.insert(
                "", "end", values=tuple(getattr(row, column.key) for column in COLUMNS)
            )
        empty = t("history_empty", self._locale)
        self.status.configure(text=self.listing.count_text if self.listing.total else empty)
        if self._on_changed is not None:
            self._on_changed()

    def _sort(self, column_key: str) -> None:
        self.listing.sort_by(column_key)
        self.refresh()

    def _apply_magnitude(self) -> None:
        raw = self._magnitude.get().strip()
        try:
            value = float(raw) if raw else None
        except ValueError:
            return  # a half-typed number is not a filter yet
        self.listing.set_filter(min_magnitude=value)
        self.refresh()

    def _apply_verdict(self) -> None:
        chosen = self._verdict.get()
        verdicts = {
            t("history_verdict_alerted", self._locale): "alerted",
            t("history_verdict_discarded", self._locale): "discarded",
        }
        self.listing.set_filter(verdict=verdicts.get(chosen))
        self.refresh()

    def _clear(self) -> None:
        self._magnitude.set("")
        self._verdict.set(t("history_filter_any", self._locale))
        self.listing.clear_filters()
        self.refresh()


def rows_for(store: HistoryStore, query: HistoryQuery) -> Sequence[EventRecord]:
    """The records a query selects, for a view that wants them unformatted."""
    return store.query(query)
