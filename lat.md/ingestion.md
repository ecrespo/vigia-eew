# Ingestion

Four independent sources feed a common raw queue. This file explains why there
are four, why they are not interchangeable, and the rules each one follows. All
of them emit [[src/vigia_eew/ingest/__init__.py#RawMessage]] and nothing else —
mapping to the internal contract happens later, in [[pipeline]].

## Push-primary, polling-backup

EMSC's WebSocket is the primary channel; the REST pollers exist to catch what
it misses, not to compete with it.

Latency is the product's reason to exist, so the push channel wins on speed.
But EMSC documents that its WebSocket can drop messages, and a safety tool
cannot rely on a lossy channel alone. The pollers therefore run at a low
frequency (60 s) and stay lightweight: their job is reconciliation, not
primary delivery. Polling as the primary strategy was rejected for the obvious
reason — it adds latency and load to buy nothing the push does not already
give.

The direct consequence is that the same earthquake arrives more than once, from
sources that assign it unrelated ids. That is what forces the heuristic in
[[pipeline#Cross-source dedup is heuristic because no shared id exists]].

## The WebSocket assumes it will drop

[[src/vigia_eew/ingest/ws_emsc.py#WSIngestor]] treats disconnection as normal
operation rather than an error: a 15 s keepalive detects a dead peer, and the
connect loop is perpetual, backing off exponentially with jitter and only
exiting on cancellation.

Jitter matters because every machine running this agent would otherwise
reconnect in lockstep after a shared outage and stampede the endpoint.

## USGS is polled with a cursor, not pushed

[[src/vigia_eew/ingest/rest_usgs.py#RESTReconciler]] polls USGS's FDSN endpoint
every 60 s and persists a cursor so each poll only asks for what came after the
last one.

USGS's actual push mechanism is PDL, which is a heavy JVM component; adopting
it would contradict the project's "one lightweight self-hosted process"
premise. Cursor polling costs a recovery window of up to ~60 s, which is
acceptable for a backup channel whose purpose is to catch the rare miss.

## FUNVISIS uses a seen-set because it has no cursor

[[src/vigia_eew/ingest/rest_funvisis.py#FUNVISISPoller]] polls a Venezuela-only
JSON file that always returns the current top-N events, with no `starttime`
parameter to page from. Novelty is therefore tracked with an in-memory seen-set
rather than a persisted cursor.

That set is seeded from the very first poll **without alerting**. Without this
seeding, every restart would replay FUNVISIS's already-published history as a
burst of alerts — the single most user-hostile failure this source could have.
Because the set lives only in memory, restarting deliberately forgets history
rather than risking that burst.

FUNVISIS is here because EMSC and USGS both under-catalog small local
Venezuelan earthquakes (M2–3), which are exactly the ones the project's primary
users feel. The endpoint has no working HTTPS; that is accepted because the
data is public and read-only, with no credentials or user data crossing the
channel.

## GEOFON is USGS's sibling, and parses text on purpose

[[src/vigia_eew/ingest/rest_geofon.py#GEOFONPoller]] polls GFZ Potsdam's
`fdsnws-event` service on the same cursor-based model as USGS, giving a fourth,
fully independent global network so a shared EMSC/USGS blind spot does not
leave the agent silent.

It parses the **pipe-delimited text** format rather than GeoJSON. USGS's
GeoJSON support is confirmed; GEOFON's was not, when the source was added.
Requesting a format that might silently differ is worse than explicitly parsing
the one that is documented and verified, so the GeoJSON code path is not
reused. QuakeML is available from the same endpoint and deliberately unused, to
avoid taking on an XML parser.

Merging both FDSN pollers behind one format-parametrized class was considered
and deferred: with two formats this deep apart, the shared abstraction would
add indirection and no benefit. Revisit it if a third FDSN-family source
appears.

## REST queries are floored at local midnight

When a cursor is absent (fresh install) or older than the current local day,
both cursor-based pollers floor the query's effective `starttime` at 00:00
local time via [[src/vigia_eew/timeutil.py#floor_starttime_ms]].

This changes nothing about *what gets alerted* — the freshness rule in
[[pipeline#Only today's earthquakes are alerted]] already guarantees that. It
bounds how much irrelevant history is fetched and parsed after a long outage,
so a week offline does not make the first poll pull days of backlog only to
discard it downstream. It is an efficiency guard sitting behind a correctness
guard, and both are kept because the query-side floor alone would not cover
EMSC (a push channel with no `starttime`) or FUNVISIS (no cursor at all).
