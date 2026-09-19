# Ingestion sources

Four ingestors feed one common `raw_queue`. They are not interchangeable: each closes a specific
coverage gap, and their structural differences are deliberate.

Cursor vs. seen-set, GeoJSON vs. pipe-text — these are not accidental inconsistencies. All four
normalize into the single internal contract, so nothing downstream knows which source an event
came from except for display and dedup precedence.

## EMSC WebSocket — the primary channel

[[src/vigia_eew/ingest/ws_emsc.py#WSIngestor]] is the low-latency path: a persistent WebSocket
with a 15 s keepalive and reconnection with exponential backoff plus jitter.

It is the only source with an `update` concept, which is why update handling lives in the dedup
layer rather than in the ingestor. `websockets` was chosen over Tornado (EMSC's own example)
because the target stack is plain asyncio and Tornado is a whole framework for one connection.
See ADR-001 and ADR-009.

## USGS — cursor-based reconciliation, not a competitor

[[src/vigia_eew/ingest/rest_usgs.py#RESTReconciler]] polls FDSN every 60 s with a persisted
cursor, so it only asks for what happened since it last looked.

USGS's real push mechanism (PDL) was rejected: it is heavy and JVM-based, against the
"lightweight and self-hosted" constraint. The accepted consequence is a recovery window of up to
~60 s for anything the WebSocket dropped — fine for a backup, unacceptable as a primary.
See ADR-002.

## GEOFON — an independent global network, USGS's sibling

[[src/vigia_eew/ingest/rest_geofon.py#GEOFONPoller]] exists because EMSC and USGS can share blind
spots: a dropped WS message coinciding with a USGS reporting lag leaves the agent blind.

GEOFON (GFZ Potsdam) is a fully independent global network polled the same cursor-based way, so
it adds redundancy without adding a new class of failure. See ADR-016.

### Why GEOFON parses pipe-delimited text, not GeoJSON

GEOFON's `fdsnws-event` GeoJSON support was not confirmed during live verification, while
`format=text` (a pipe-delimited table) was.

Assuming GEOFON mirrors USGS's GeoJSON would have risked a silent format mismatch, which is worse
than an explicit text-parsing path (`docs/API-SPEC.md` §4.3). QuakeML/XML is available from the
same endpoint and deliberately unused, to avoid an XML dependency. This is why `GEOFONPoller` does
not reuse `RESTReconciler`'s parsing code even though the two are structurally similar; a shared
generic "FDSN poller" parametrized by format was considered and deferred until a third
FDSN-family source justifies the indirection.

## FUNVISIS — Venezuela-only local coverage

[[src/vigia_eew/ingest/rest_funvisis.py#FUNVISISPoller]] polls the `maravilla.json` file that
FUNVISIS's own web map consumes.

It exists because EMSC and USGS under-catalog small local Venezuelan earthquakes (M2–3), which
are exactly the ones the project's primary users feel. Scraping the web map HTML was rejected as
more fragile than its own data file. The endpoint has no valid HTTPS; plain HTTP is accepted
because the data is public and read-only, and no credentials or user data cross that channel.
See ADR-015.

### Why FUNVISIS uses a seen-set instead of a cursor

The endpoint returns the current top-N batch with no `starttime` parameter and no
`create`/`update` distinction, so there is nothing for a cursor to point at.

Novelty is tracked with an in-memory seen-set seeded from the very first poll **without
alerting**. Without that seeding, every restart would replay FUNVISIS's published history as a
burst of alerts. The set is intentionally not persisted: on restart, seeding does the same job.

## Distant-source events need no special-casing

FUNVISIS events are Venezuela-only, so for a non-Venezuelan user they simply fall outside
`radius_km` and are dropped by the ordinary geographic filter.

No source-aware logic exists in [[src/vigia_eew/pipeline/filter.py#GeoFilter]], and none should be
added — the radius check already expresses the intent.
