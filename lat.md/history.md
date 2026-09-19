# Event history

[[src/vigia_eew/history.py#HistoryStore]] keeps one row per **evaluated arrival** — alerted or
discarded — so that "why was I not warned about that earthquake?" has an answer.

The agent used to remember only what it had already alerted, which is just enough not to repeat
itself and nothing at all about what it threw away. Recording only the alerts would leave
unanswered exactly the question people ask when the product seems to be failing.

## Why a database, against the constitution's own rule

The constitution says "no database", and its argument is that the state is a few KB in memory
queried by membership.

That is literally true of the operating state and literally false of a history: tens of thousands
of rows a year, queried by date range, magnitude and network. A JSON file you have to load whole
in order to filter by date is the reason databases exist. SQLite ships with Python, so the
amendment costs no dependency — see amendment E-05 and ADR-025.

The operating state stays JSON, without exception. Mixing the alert's hot path with data that
exists to be queried is precisely what the amendment avoids.

## The history is a consequence of an alert, never a condition of one

[[src/vigia_eew/history.py#HistoryWriter]] takes a record, puts it on a queue and returns. A
supervised task drains it, and each write goes to a worker thread because SQLite blocks and the
event loop is carrying four ingestors and the pipeline.

Every failure on that path is logged and swallowed. An agent that cannot write its history is
still an agent that alerts — Art. 1, REQ-HIS-002. The store failing to open at all is the same
decision one level up: a warning, a `None`, and an agent that comes up without its history.

The pipeline records **after** the alert callback, never before. That order is the requirement,
not an optimisation.

## One row per arrival, two rows for one earthquake

An earthquake reported by two networks produces two rows tied together by the correlation id.

The arrival that lost carries `superseded_by`, pointing at the row that prevailed — resolved by
the store, because the pipeline reasons about journeys and the database reasons about rows.
Deleting the duplicate instead would throw away the very thing worth keeping: *it arrived by two
networks, and this one prevailed*.

A revision from the same network replaces its row rather than adding one, which is the rule
[[lat.md/pipeline#Deduplication]] already applies upstream.

## Times are text, and that is deliberate

SQLite has no date type. Stored as ISO-8601 with an offset, lexical order is chronological, so
ranges and indexes work with no conversion — and Art. 4's "every datetime is tz-aware UTC"
survives the round trip untouched.

`distance_km` is stored rather than recomputed when queried. It is the distance to the reference
point **of that moment**: if the user moves, the history still has to say how far away the
earthquake was then.

## Retention is where an admitted guess lives

Entries older than the configured retention are removed when the agent opens the file.

Ninety days is an **estimate, not a measurement**. Discards far outnumber alerts and the volume
depends on global seismicity, so the figure is configurable from the start precisely because it is
the parameter that absorbs the error. Measure on first real use and adjust it with the number.

Pruning happens at open rather than on a timer. A periodic task would have nothing to do most of
the time and would still need supervising, restarting and shutting down; the history only grows
while the agent runs, so bounding it at each start is equivalent with far less machinery — the
same argument [[lat.md/state#Pruning happens where the state grows]] settled.

## It does not leave the machine

No sync, no remote backup, no telemetry — amendment E-06 and REQ-HIS-006.

There is no client in this module to point anywhere, and a test fails if the module so much as
mentions a network library. It is a file on one computer, and that is the whole design.

## The query is a finite set of statements, not a string that gets built

[[src/vigia_eew/history.py#HistoryQuery]] carries every filter as a bound value, and the ordering
picks one of a table of whole statements built from a list of column names.

The filters are static SQL — `(:min_magnitude IS NULL OR magnitude >= :min_magnitude)` — so
combining them never assembles anything. They combine with AND, which is what CA-111.8 asks for:
by magnitude *and* date range returns the rows satisfying both, not either. Verified by swapping
one AND for an OR and watching five tests fail.

The ordering is the one part that cannot be a bound value, so it is a lookup keyed by column and
direction. An ordering nobody declared fails in Python, naming it, instead of reaching SQLite —
and the set of queries the store can possibly issue stays finite and visible.

The source filter is a delimited string rather than an `IN` list, because an `IN` list is the one
filter whose length would force the statement to be built at call time. The delimiters are what
keep it a membership test: `MSC` does not match `|EMSC|`.

One query object drives the list and the map, so that filtering cannot come to mean two different
things in two views of one history.
\n

## The map is a view on the list, never the other way round

[[src/vigia_eew/notify/history_view.py#HistoryList]] depends on the local file and nothing else.
No network, no third party, no image decoding.

That is Art. 3 applied to a feature rather than to a failure: the history answers "why was I not
warned?" whether or not there is connectivity, and the geographic reading is an addition on top.
The plan says the same thing in scope terms — if something had to be cut, the map goes and the
list stays.

A test walks the module's imports and fails if a network library or the tile client appears among
them. Prose about the map is fine; an import of it is not.

Both views read **one** query object. The list owns it and the map reads it, so a filter cannot
come to mean two different things in two views of one history.

## Tiles are fetched only because somebody is looking at a map

[[src/vigia_eew/tiles.py#TileClient]] is the only place in the agent that contacts the tile
provider, and nothing constructs one except the map window.

Amendment E-06 is what makes that worth enforcing rather than intending. Until v1.0 the agent
talked to seismic sources and, once, to a geolocation service; a map adds a **new kind of
destination**, and the amendment bounds it to the time the map is on screen.

So the bound is structural, not behavioural: a test walks every import in the package and fails if
any module other than the map imports the tile client. "No requests while closed" is a property of
who can call this at all — and a second caller added in a year is exactly what would break it
quietly.

### The cost that cannot be engineered away is declared instead

While the map is open, the provider can infer roughly which area the user is looking at.

The cache reduces it and fetching on demand bounds it. Neither removes it, and pretending
otherwise would be worse than saying so — see ADR-027 and E-06.

### What the provider is owed

Every request identifies the application, its version and a contact, because the tile usage policy
asks for it and an anonymous client is blocked. `© OpenStreetMap contributors` is on screen
wherever a tile is.

A viewport asks for the tiles it shows and no others: no speculative ring, no neighbouring zoom
levels, no prefetching. Tiles off the edge of the grid are left out rather than requested — there
is no tile x=-1, and asking for one is a 404 the provider counts against this client.

### The cache is a cache, and the difference matters

It lives in the platform's **cache** directory, not the data one, because losing it costs a
download while losing [[lat.md/state#Persisted state]] costs a repeated alert. The user, or the
operating system, can clear it without consequence.

It is bounded and least-recently-used, so it cannot grow into somebody's disk. A failure is never
cached as an answer: caching "no" would leave a zone blank long after the network came back, which
looks exactly like a map that is simply broken.

## What the map says, and how it says it

[[src/vigia_eew/notify/history_map.py#plan]] works out the whole drawing before a widget is
touched: which tile goes where, how big each symbol is, which symbols are alerts.

That separation is what makes the product's claims checkable. "A magnitude 6 is visibly bigger
than a 3" is a number in a test, not an impression; "alerted and discarded are told apart" is an
assertion about two styles, not a screenshot somebody looked at once.

**The symbol scales linearly with magnitude, not with energy.** Energy is the honest physical
scale and it is useless here — a magnitude 7 releases about thirty thousand times what a 4 does,
which on a screen is either a dot or a continent. What REQ-MAP-003 asks for is a readable order.

**The difference is shape as well as colour.** An alert is filled and a discard is an outline, so
the distinction survives a printout, a screenshot, and a reader who cannot tell the two colours
apart. A verdict nobody planned for is drawn as a discard rather than left out: silently
under-reporting the history is worse than drawing it modestly.

### No tiles means no map, and it says so

With nothing to draw under them, the symbols are not drawn either.

A dot at a pixel with no geography beneath it is a picture of nowhere, and it would look like a
map. Saying the map is unavailable is the honest answer, and the list is already on screen
answering the real question (REQ-MAP-002, Art. 3).

One tile in hand is still a map, though: a partly cached zone draws what it has rather than
throwing away a usable cache.

### The legend and the attribution are never conditional

Both are painted whatever else is or is not there — the attribution because the licence requires
it wherever a tile is, and the legend because a symbol nobody can read explains nothing.

## One filter, two readings of it

[[src/vigia_eew/notify/history_window.py#HistoryWindow]] owns the wiring so that neither view has
to know about the other.

The direction is one-way: the list decides the set and the map is handed the records it produced.
A map still showing symbols the table has filtered away would not be a second opinion — it would
be the product contradicting itself on one screen (REQ-MAP-004).

It lives in its own module rather than in either view, because the list has to stay free of the
map. The list is the part that works with nothing but the file, and an import guard keeps it that
way; putting the wiring inside it would have been the first step to losing that.

Sorting is the exception that proves the direction: order is a property of a table and a map has
no rows to reorder, so sorting changes the table and leaves the map showing the same earthquakes.
