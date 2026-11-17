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

## Which arrival stands for an earthquake

Read per earthquake, one arrival of each `correlation_id` is kept, chosen by a fixed order in
[[src/vigia_eew/history.py#HistoryQuery]]'s statements (ADR-034, REQ-HIS-009).

The order: the arrival that alerted; else one nothing superseded; else the best-ranked network
(the user's own order, the one [[lat.md/pipeline#Deduplication]] obeys); else the lowest row id.
What the user was told is what the earthquake was, for them — so the alerted row wins even when
a better-ranked network also reported it.

It is a reading, not a table. A materialised `earthquakes` table would be a second source of
truth to keep in step with every write. Grouping in Python would page and count rows that had
not been grouped yet, so the window function does it inside the statement, one per ordering.

The filters apply to arrivals **first**, and what matches is grouped after. Filtered to USGS, an
earthquake EMSC alerted appears once, as USGS saw it: the filter still means what it means per
arrival. An arrival with no correlation id is tied to nothing and stands alone, rather than
merging with every other arrival that has none.

The rank travels as one bound, delimited string — a network's position in it is its rank — for
the reason the source filter does: nothing is interpolated. The screen's switch only sets the
reading on the query, so the pager, the total and the map follow without knowing about it;
[[src/vigia_eew/notify/history_view.py#HistoryList]]`.arrivals_of()` gives back the arrivals the
reading folded away.

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

## The map is a view on the list, never the other way round

[[src/vigia_eew/notify/history_view.py#HistoryList]] depends on the local file and nothing else.
No network, no third party, no image decoding.

That is Art. 3 applied to a feature rather than to a failure: the history answers "why was I not
warned?" whether or not there is connectivity, and the geographic reading is an addition on top.
The plan says the same thing in scope terms — if something had to be cut, the map goes and the
list stays.

A test walks the module's imports and fails if a network library or a map module appears among
them. Prose about the map is fine; an import of it is not.

Both views read **one** query object. The list owns it and the map reads it, so a filter cannot
come to mean two different things in two views of one history.

## The list owns the filters and the paging

[[src/vigia_eew/notify/history_view.py#HistoryList]] holds every filter and the page;
[[src/vigia_eew/notify/history_view.py#HistoryView]] only sets them.

v1.0 shipped with REQ-HIS-005 marked as met — *filter by date range, magnitude, distance, verdict
and network* — and a screen that offered two of the five. The requirement says *"when the user
queries"*; its criterion said *"a query"*, and a test on the store satisfied it. Nobody had asked
the screen. `HistoryView.filters` now names the control behind each criterion so that a test can.

The state is in the list, not in the Flet controls, because the list imports no toolkit. A second
frontend — the terminal — can then offer the same filters by driving the same object, instead of
implementing them again and drifting.

Dates are **local calendar days**, converted to UTC bounds by
[[src/vigia_eew/timeutil.py#local_day_bounds]], next to the other local-day boundary (RF-40), so
that "a day" means one thing in the filter that discards and in the filter that reads. A period
that ends before it starts is refused by the list, which keeps its query: the screen says so and
still shows the entries of the last period that made sense.

The verdicts and networks offered are the ones the file holds. A filter that offers a network
nobody has heard from can only return nothing — and a verdict added later is offered without
anyone touching the control.

Setting any filter, or sorting, returns to the first page: page three of the old set means nothing
in the new one. The page is the table's limit, 150 rows, because a Flutter `DataTable` lays out
every cell up front. v1.0 loaded 500 and drew 150 with no way to the rest; a history that hides
rows without saying which does not answer "why was I not warned?" for those rows.

## The table pages, the map does not

[[src/vigia_eew/notify/history_view.py#HistoryList]]`.everything()` hands the whole filtered set
to the views that draw it; [[src/vigia_eew/notify/history_window.py#HistoryWindow]] feeds the map
from that, not from the page.

If the map drew the table's page, turning the page would move the symbols, and "both views show
the same set" would have quietly come to mean "the same 150 rows". The set is what the filter
selects; the page is how much of it a table can lay out.

The map draws up to `MAP_SYMBOL_LIMIT` and says how many of how many when the set is larger,
for the reason an unknown verdict is still drawn: leaving earthquakes off in silence under-reports
the history. **The limit is provisional** — 500 is what v1.0 happened to draw, not a measurement —
and the spike that opens the timelapse replaces it.

## A symbol can be pointed at

[[src/vigia_eew/notify/history_map.py#HistoryMap]] draws each symbol as a `flet-map` `Marker`
holding a round container, not as a `CircleMarker`.

A `CircleMarker` is a painted shape: it has no tooltip and no events, so a circle could not say
which earthquake it was. That was checked on the real client before designing around it — a
marker's tooltip shows, pointing and pressing fire, and the press does not also reach the map. A
view whose whole argument is *where* and that cannot answer *which one is that?* delivers half.

The tooltip is the row the list already formatted for the table, joined into three lines. The map
is handed the words; it does not word an earthquake itself, because a second wording is a second
chance for a symbol and its row to disagree.

The cost is real: a marker carries a control where a circle carried none. How many the map can
redraw is unmeasured, which is why the limit above is provisional.

**Nothing above the map may take the pointer from it.** The "map unavailable" notice is centred by
a container that fills the whole stack, drawn over the map. With painted circles nobody noticed.
With markers it swallowed every hover and press, so no symbol answered — and every test passed,
because Flet controls are dataclasses here and a dataclass has no hit-testing. It was found by
opening the real window, and is held by a test on the structure: whatever fills the stack above
the map is a `TransparentPointer`. A feature whose point is "the user can point at it" is not
verified until something has pointed at it.

## The table and the map point at the same thing

[[src/vigia_eew/notify/history_window.py#HistoryWindow]] wires the selection in both directions,
keyed by the id of the row a symbol stands for.

A row pressed in the table highlights its symbol. A symbol pressed on the map brings the table to
the page that holds its row and highlights it. The list still imports no map and the map knows
nothing about tables: each reports what was pressed, and the window decides what that means.

`choose` and `select` are separate on purpose. `choose` is the user acting on a view, and tells
the window; `select` is a view being told. With one method the two views would echo each other.

The selected symbol is larger and its ring thicker — shape, not colour — following the rule the
map already applies to alerts and discards. A filter that removes the chosen earthquake lets go
of it; turning the page does not, because the earthquake is still in the set and on the map.

## Tiles are fetched only because somebody is looking at a map

[[src/vigia_eew/notify/map_view.py#tile_layer]] is the only place in the agent that names the tile
provider, and only the views that put a map on screen — the alert and the history — build one.

Amendment E-06 is what makes that worth enforcing rather than intending. Until v1.0 the agent
talked to seismic sources and, once, to a geolocation service; a map adds a **new kind of
destination**, and the amendment bounds it to the time a map is on screen. Since ADR-030 the
tiles are fetched by the Flet client itself (flet-map), so the alert's epicentre map counts too:
an alert on screen is a map on screen.

So the bound is structural, not behavioural: a test walks every import in the package and fails if
any module other than the map views reaches `flet_map` or `map_view`, and another fails if the tile
URL is spelled anywhere else. "No requests while closed" is a property of who can build a tile
layer at all — and a second caller added in a year is exactly what would break it quietly.

### The cost that cannot be engineered away is declared instead

While a map is open, the provider can infer roughly which area the user is looking at.

Fetching only what is on screen bounds it. It does not remove it, and pretending otherwise would be
worse than saying so — see ADR-027 and E-06.

### What the provider is owed

Every request identifies the application by its package name, because the tile usage policy asks
for it and an anonymous client is blocked. `© OpenStreetMap contributors` is on screen wherever a
tile is.

The client asks for the tiles of the viewport it shows. There is no cache of our own any more: the
Tk-era disk cache went with ADR-030, and what flet-map keeps is in memory, for the life of the
window. Losing it costs a download, never an alert.

## What the map says, and how it says it

[[src/vigia_eew/notify/history_map.py#plan]] works out the whole drawing before a control is
built: where each symbol goes, how big it is, which symbols are alerts.

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

When a tile fails to load, the map says it is unavailable rather than pretending to be one.

A dot at a pixel with no geography beneath it is a picture of nowhere, and it would look like a
map. [[src/vigia_eew/notify/history_map.py#HistoryMap]] shows a notice over it on the first tile
error, and the list is already on screen answering the real question (REQ-MAP-002, Art. 3).

### The legend and the attribution are never conditional

Both are painted whatever else is or is not there — the attribution because the licence requires
it wherever a tile is, and the legend because a symbol nobody can read explains nothing.

## One filter, two readings of it

[[src/vigia_eew/notify/history_window.py#HistoryWindow]] owns the wiring so that neither view has
to know about the other.

The direction is one-way for **the set**: the list decides it and the map is handed the records it
produced. (Which one is highlighted travels both ways, and is a separate matter.)
A map still showing symbols the table has filtered away would not be a second opinion — it would
be the product contradicting itself on one screen (REQ-MAP-004).

It lives in its own module rather than in either view, because the list has to stay free of the
map. The list is the part that works with nothing but the file, and an import guard keeps it that
way; putting the wiring inside it would have been the first step to losing that.

Sorting is the exception that proves the direction: order is a property of a table and a map has
no rows to reorder, so sorting changes the table and leaves the map showing the same earthquakes.

## The playback steps by earthquake, and a frame depends only on its step

[[src/vigia_eew/notify/timelapse.py#Timeline]] turns a set of earthquakes into steps, one per
instant something happened, and says what each step shows. It is pure: no toolkit, no clock.

**By earthquake, not by a clock** (decision D-8). The map is redrawn when the next earthquake of
the set happens and not in between. A fixed frame rate would redraw at a pace unrelated to the
data — most frames identical to the last — and continuous fading between steps is a clock again.
So intensity comes in a few discrete levels, worked out at each step from the earthquake's age in
the history's own time, and speed is only how long a step stays on screen.

`frame(i)` is a function of *i* and nothing else. Seeking to an earthquake and reaching it by
playing are the same call, so they cannot come to show different things, and changing the speed
cannot change what is shown. That is why every promise about order, seeking and fading is tested
with no screen: the three invariants run over generated sets.

A step stays on screen for the real gap to the next earthquake divided by the speed, held between
`MIN_DWELL` and `MAX_DWELL`: a burst a second apart must still be seen, and a silent week must
not look like a playback that stopped.

Those limits and `PLAYBACK_SYMBOL_LIMIT` are **measured**, in `docs/v1.1/10-SPIKE-TIMELAPSE.md`:
400 markers redraw in about 86 ms, inside a shortest step of 150 ms. Their product is the longest
a playback of clamped steps can last, and it must stay at or under a minute. If a slower machine
needs relief, lower the limit; do not raise the minimum.

Two parts, split like the list and its view.
[[src/vigia_eew/notify/timelapse_view.py#TimelapseView]] holds the controls and asks the shell's
timer for one step at a time. A timer cannot take a step back, so pausing makes it stale instead:
every play, pause, seek and reload starts a new generation, and a step that comes due under an
old one does nothing. An import contract fails if the timeline ever imports the toolkit.

## The playback is a third reading of one query

[[src/vigia_eew/notify/history_window.py#HistoryWindow]] hands the playback the set the filters
select; the playback has no query of its own (REQ-TLP-004).

It reads the set **per earthquake** whatever the table is reading, so that none plays twice
([[lat.md/history#Which arrival stands for an earthquake]]), and the most recent ones when there
are more than it holds — whatever the table is sorted by — saying how many of how many.

A change of filter replaces the set, and the playback lets go of the map. A change that leaves
the set alone — a page turned, a column sorted, a row chosen — leaves the frame where it is. The
window tells the two apart by comparing what the filters select, not by who called.

It paints through the same [[src/vigia_eew/notify/history_map.py#HistoryMap]] the static set
uses, each symbol drawn weaker by its age. The spike found markers fast enough, so there is no
second painter, and a paused frame answers the pointer like the static map. It also means the
"map unavailable" notice is inherited rather than rebuilt.

The control holds a painter, not the map, so it has no way to pan or zoom: a playback that
wandered the map would fetch tiles nobody decided to fetch (REQ-TLP-008, E-06).

An alert pauses it. The wiring registers the window's pause with the shell
([[lat.md/notification#A screen is told when an alert covers it]]); after the alert the screen is
back as it was, paused on the same step. Leaving or closing the history pauses it too, since the
timer would otherwise keep a playback nobody sees alive.
