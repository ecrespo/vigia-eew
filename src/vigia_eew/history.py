"""The event history: what the agent evaluated, and what it decided (REQ-HIS-001..006).

The agent used to forget. It remembered which events it had already alerted --
just enough not to repeat itself -- and nothing at all about the ones it
discarded. That left the question people actually ask when the product seems
to be failing with no answer available anywhere: *"why was I not warned about
that earthquake?"*

Every evaluated arrival is now a row, alerted or discarded, and a discard
carries the reason. The store is SQLite, decided in ADR-025 against the
constitution's "no database" rule and permitted by amendment E-05: that rule's
argument -- "the state is a few KB in memory, queried by membership" -- is
literally true of the operating state and literally false of a history of tens
of thousands of rows a year, queried by range.

Two properties this module exists to keep:

  - **It never stands between an earthquake and its alert.** REQ-HIS-002 and
    Art. 1. The store itself is synchronous and dumb; keeping the writing off
    the hot path is `HistoryWriter`'s job, and a failure anywhere in here is
    logged and swallowed by the caller, never raised at the pipeline.
  - **It never leaves the machine.** REQ-HIS-006 and amendment E-06. There is
    no client here to point anywhere: one local file, and a test that fails if
    this module so much as mentions a network library.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

from vigia_eew.config import APP_NAME

HISTORY_FILE_NAME = "history.sqlite3"

#: The schema this code writes. Bumping it means appending a migration.
SCHEMA_VERSION = 1

#: Retention by default. **An estimate, not a measurement**: the volume depends
#: on global seismicity and on what each network publishes, and discards are
#: far more numerous than alerts. It is configurable precisely because the
#: figure it absorbs is uncertain -- measure on first real use and adjust it
#: with the number, not with this guess (DATA-MODEL §3bis.4).
DEFAULT_RETENTION_DAYS = 90

Clock = Callable[[], datetime]
Migration = Callable[[sqlite3.Connection], None]


def default_history_path() -> Path:
    """Path to the history file in the user's data directory, beside the state."""
    return Path(user_data_dir(APP_NAME)) / HISTORY_FILE_NAME


class HistoryTooNew(RuntimeError):
    """The file was written by a newer version of the agent (REQ-HIS-003).

    Raised instead of opening it. Migrating forward is a decision somebody
    made; migrating backwards is guesswork, and the file being guessed at is
    the user's own record.
    """


@dataclass(frozen=True, slots=True)
class EventRecord:
    """One evaluated **arrival** -- not one earthquake (DATA-MODEL §3bis.1).

    An earthquake reported by two networks produces two rows, tied together by
    `correlation_id`. `distance_km` is stored rather than recomputed at query
    time because it is the distance to the reference point **of that moment**:
    if the user moves, the history still has to say how far away it was then.
    """

    correlation_id: str
    source: str
    source_event_id: str
    occurred_at: datetime
    recorded_at: datetime
    latitude: float
    longitude: float
    depth_km: float | None
    magnitude: float
    region: str | None
    distance_km: float
    verdict: str
    reason: str | None = None
    severity: str | None = None
    #: Row that prevailed, when this one was discarded as a duplicate. Resolved
    #: by the store, not by the caller: the pipeline knows about journeys, not
    #: about row ids.
    superseded_by: int | None = None
    id: int | None = None


_CREATE = """
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY,
    correlation_id  TEXT    NOT NULL,
    source          TEXT    NOT NULL,
    source_event_id TEXT    NOT NULL,
    occurred_at     TEXT    NOT NULL,
    recorded_at     TEXT    NOT NULL,
    latitude        REAL    NOT NULL,
    longitude       REAL    NOT NULL,
    depth_km        REAL,
    magnitude       REAL    NOT NULL,
    region          TEXT,
    distance_km     REAL    NOT NULL,
    severity        TEXT,
    verdict         TEXT    NOT NULL,
    reason          TEXT,
    superseded_by   INTEGER REFERENCES events(id),
    UNIQUE (source, source_event_id)
)
"""

#: One index per query REQ-HIS-005 names; none of them is "just in case".
#: The geographic one is a composite of two reals rather than a real spatial
#: index because SQLite's R*Tree module is optional and cannot be assumed
#: compiled into every interpreter this product packages (DATA-MODEL §3bis.2).
_INDEXES = (
    "CREATE INDEX IF NOT EXISTS events_occurred_at ON events(occurred_at)",
    "CREATE INDEX IF NOT EXISTS events_magnitude ON events(magnitude)",
    "CREATE INDEX IF NOT EXISTS events_verdict ON events(verdict)",
    "CREATE INDEX IF NOT EXISTS events_correlation_id ON events(correlation_id)",
    "CREATE INDEX IF NOT EXISTS events_location ON events(latitude, longitude)",
)

#: Written out rather than assembled from a list of column names. The values
#: are bound parameters either way, but a statement built at runtime is one a
#: reader -- and a SAST tool -- has to reason about before believing it, and
#: fifteen columns are not worth that.
_UPSERT = """
INSERT INTO events (
    correlation_id, source, source_event_id, occurred_at, recorded_at,
    latitude, longitude, depth_km, magnitude, region, distance_km,
    severity, verdict, reason, superseded_by
) VALUES (
    :correlation_id, :source, :source_event_id, :occurred_at, :recorded_at,
    :latitude, :longitude, :depth_km, :magnitude, :region, :distance_km,
    :severity, :verdict, :reason, :superseded_by
)
ON CONFLICT(source, source_event_id) DO UPDATE SET
    correlation_id = excluded.correlation_id,
    occurred_at    = excluded.occurred_at,
    recorded_at    = excluded.recorded_at,
    latitude       = excluded.latitude,
    longitude      = excluded.longitude,
    depth_km       = excluded.depth_km,
    magnitude      = excluded.magnitude,
    region         = excluded.region,
    distance_km    = excluded.distance_km,
    severity       = excluded.severity,
    verdict        = excluded.verdict,
    reason         = excluded.reason,
    superseded_by  = excluded.superseded_by
"""


def _initial_schema(db: sqlite3.Connection) -> None:
    db.execute(_CREATE)
    for statement in _INDEXES:
        db.execute(statement)


class HistoryStore:
    """The SQLite file, its schema, and the rows in it.

    Synchronous and blocking on purpose: it is a file. Keeping the writes off
    the path between an arrival and its alert is `HistoryWriter`'s job, and
    separating the two is what lets this be tested against a real database
    without an event loop anywhere near it.
    """

    #: Ordered, append-only. Index *i* takes the schema from version *i* to
    #: *i+1*, so a file records how far it has been taken in `user_version`.
    MIGRATIONS: tuple[Migration, ...] = (_initial_schema,)

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        migrations: Sequence[Migration] | None = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        prune_on_open: bool = True,
        now: Clock | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else default_history_path()
        self._migrations = tuple(migrations if migrations is not None else self.MIGRATIONS)
        self._retention_days = retention_days
        self._prune_on_open = prune_on_open
        self._now = now or (lambda: datetime.now(UTC))
        self._log = logger or logging.getLogger("vigia_eew.history")
        self._db: sqlite3.Connection | None = None

    # --- Lifecycle ---

    def open(self) -> HistoryStore:
        """Opens the file, migrating it if it is behind (REQ-HIS-003).

        `check_same_thread=False` because `HistoryWriter` hands each write to a
        worker thread so the event loop is never blocked by a disk. The queue
        in front of it is what makes that safe: one writer, one statement at a
        time, never two threads in the connection at once.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._migrate()
        if self._prune_on_open:
            self.prune(retention_days=self._retention_days)
        return self

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    @property
    def schema_version(self) -> int:
        return int(self._connection.execute("PRAGMA user_version").fetchone()[0])

    @property
    def _connection(self) -> sqlite3.Connection:
        if self._db is None:
            raise RuntimeError("the history store is not open")
        return self._db

    def _migrate(self) -> None:
        """Applies the pending migrations in one transaction each.

        A half-applied migration is worse than none: the rows are somebody's
        record of what their agent saw. A file from a *newer* version is left
        exactly as it is and said out loud, rather than degraded quietly.
        """
        db = self._connection
        version = self.schema_version
        if version > len(self._migrations):
            raise HistoryTooNew(
                f"{self.path} was written with schema version {version}; "
                f"this agent understands {len(self._migrations)}. Leaving it untouched."
            )
        for step in range(version, len(self._migrations)):
            with db:  # commits on success, rolls back on any exception
                self._migrations[step](db)
                db.execute(f"PRAGMA user_version = {step + 1}")
            self._log.info("history_migrated from=%d to=%d", step, step + 1)

    # --- Writing ---

    def record(self, event: EventRecord) -> int:
        """Stores one evaluated arrival; returns its row id.

        The same arrival recorded again **replaces** its row rather than adding
        another -- a revision from one network is the same arrival, which is
        the rule the deduplicator already applies upstream.
        """
        linked = self._prevailing_row(event)
        db = self._connection
        with db:
            cursor = db.execute(_UPSERT, self._values(replace(event, superseded_by=linked)))
        return int(cursor.lastrowid or self._row_id_of(event))

    def _prevailing_row(self, event: EventRecord) -> int | None:
        """The row this one was discarded in favour of, when there is one.

        Resolved here rather than by the caller: the pipeline reasons about
        journeys and the database reasons about rows, and the correlation id
        is precisely the thing that joins the two.
        """
        if event.reason != "duplicate" or not event.correlation_id:
            return event.superseded_by
        row = self._connection.execute(
            "SELECT id FROM events WHERE correlation_id = ? AND verdict = 'alerted' "
            "ORDER BY id LIMIT 1",
            (event.correlation_id,),
        ).fetchone()
        return int(row["id"]) if row is not None else None

    def _row_id_of(self, event: EventRecord) -> int:
        row = self._connection.execute(
            "SELECT id FROM events WHERE source = ? AND source_event_id = ?",
            (event.source, event.source_event_id),
        ).fetchone()
        return int(row["id"])

    @staticmethod
    def _values(event: EventRecord) -> dict[str, Any]:
        """The row as SQLite stores it -- timestamps as ISO-8601 in UTC.

        SQLite has no date type. In ISO-8601 with an offset, lexical order is
        chronological, so ranges and indexes work with no conversion at all,
        and Art. 4's "every datetime is tz-aware UTC" survives the round trip.
        """
        return {
            "correlation_id": event.correlation_id,
            "source": event.source,
            "source_event_id": event.source_event_id,
            "occurred_at": event.occurred_at.astimezone(UTC).isoformat(),
            "recorded_at": event.recorded_at.astimezone(UTC).isoformat(),
            "latitude": event.latitude,
            "longitude": event.longitude,
            "depth_km": event.depth_km,
            "magnitude": event.magnitude,
            "region": event.region,
            "distance_km": event.distance_km,
            "severity": event.severity,
            "verdict": event.verdict,
            "reason": event.reason,
            "superseded_by": event.superseded_by,
        }

    # --- Reading ---

    def count(self) -> int:
        return int(self._connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def rows(self, *, limit: int = 1000) -> list[EventRecord]:
        """The most recent arrivals, newest last. Filtering by the criteria that
        matter is REQ-HIS-005, and it belongs to the view that will ask for it."""
        cursor = self._connection.execute(
            "SELECT * FROM events ORDER BY occurred_at, id LIMIT ?", (limit,)
        )
        return [_from_row(row) for row in cursor]

    # --- Retention (REQ-HIS-004) ---

    def prune(self, *, retention_days: int | None = None, now: datetime | None = None) -> int:
        """Removes arrivals older than the retention; returns how many.

        Pruning happens when the file is opened rather than on a timer. A
        periodic task would have nothing to do most of the time and would still
        need supervising, restarting and shutting down; the history only grows
        while the agent runs, so bounding it at each start is equivalent with
        far less machinery -- the same argument `state.py` settled for
        prune-on-register.
        """
        days = self._retention_days if retention_days is None else retention_days
        cutoff = (now or self._now()).astimezone(UTC) - timedelta(days=days)
        db = self._connection
        with db:
            # The children first: a row kept cannot point at a row removed.
            db.execute(
                "UPDATE events SET superseded_by = NULL WHERE superseded_by IN "
                "(SELECT id FROM events WHERE occurred_at < ?)",
                (cutoff.isoformat(),),
            )
            cursor = db.execute("DELETE FROM events WHERE occurred_at < ?", (cutoff.isoformat(),))
        removed = int(cursor.rowcount or 0)
        if removed:
            self._log.info("history_pruned removed=%d retention_days=%d", removed, days)
        return removed


def _from_row(row: sqlite3.Row) -> EventRecord:
    return EventRecord(
        id=row["id"],
        correlation_id=row["correlation_id"],
        source=row["source"],
        source_event_id=row["source_event_id"],
        occurred_at=datetime.fromisoformat(row["occurred_at"]),
        recorded_at=datetime.fromisoformat(row["recorded_at"]),
        latitude=row["latitude"],
        longitude=row["longitude"],
        depth_km=row["depth_km"],
        magnitude=row["magnitude"],
        region=row["region"],
        distance_km=row["distance_km"],
        severity=row["severity"],
        verdict=row["verdict"],
        reason=row["reason"],
        superseded_by=row["superseded_by"],
    )


class HistoryWriter:
    """Keeps the history off the path between an arrival and its alert.

    REQ-HIS-002 is the requirement, and Art. 1 is the reason: the history is a
    *consequence* of an alert, never a condition of one. `submit` puts a record
    on an unbounded queue and returns; a supervised task drains it, and each
    write goes to a worker thread because SQLite blocks and the event loop
    carries the four ingestors and the pipeline.

    Every failure is logged and swallowed. An agent that cannot write its
    history is still an agent that alerts.
    """

    def __init__(
        self,
        store: HistoryStore,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._store = store
        self._log = logger or logging.getLogger("vigia_eew.history")
        self._queue: asyncio.Queue[EventRecord] = asyncio.Queue()
        self._available = True

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    def submit(self, record: EventRecord) -> None:
        """Hands a record over. Never blocks, never raises, never waits on a disk."""
        if not self._available:
            return
        self._queue.put_nowait(record)

    async def run(self) -> None:
        """Drains the queue until cancelled. One writer, one statement at a time."""
        while True:
            record = await self._queue.get()
            await self.write_one(record)

    async def write_one(self, record: EventRecord) -> None:
        """Writes a single record, off the loop and without ever propagating."""
        try:
            await asyncio.to_thread(self._store.record, record)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the alert already happened
            self._log.warning(
                "history_write_failed type=%s detail=%s trace=%s",
                type(exc).__name__,
                exc,
                record.correlation_id,
            )

    def close(self) -> None:
        """Stops accepting records and closes the file, best-effort."""
        self._available = False
        with contextlib.suppress(Exception):
            self._store.close()
