# GEOFON independent global-network source (RF-39) — design

Status: ✅ implemented (Phase 14). Poller in `ingest/rest_geofon.py`, wired in `app.py`.

## Problem

EMSC (WS, primary) and USGS (REST, backup) are both excellent global sources, but they
are not the only seismic networks, and outages or catalog gaps at either provider leave
the agent temporarily blind. GEOFON (GFZ Potsdam, Germany) operates an independent
`fdsnws-event` REST service with global coverage, no API key, and no rate-limit
gatekeeping known to be an issue for polling every 60 s. Adding it as a fourth,
independent source increases redundancy against a single provider's outage or missed
catalog entry, without introducing a paid dependency or new protocol (it reuses the
project's existing `httpx` REST-polling pattern).

This is a documentation-only phase per the project's SDD gate: no `ingest/rest_geofon.py`
code exists yet. This document, together with the updated `PRD.md` (RF-39), `API-SPEC.md`
(§4), `DATA-MODEL.md` (`GEOFONSource`), `TECHNICAL-DESIGN.md` (ADR-016), and
`IMPLEMENTATION-PLAN.md` (Phase 14), is the full set of artifacts to be approved before
`ingest/rest_geofon.py` is written.

## Decisions (from brainstorming)

1. **Polling, not push.** GEOFON's `fdsnws-event` is a plain REST query endpoint with no
   WebSocket/streaming variant, so GEOFON is architecturally EMSC's backup's sibling
   (like `RESTReconciler`/USGS), not a second primary channel. Default
   `poll_interval_s = 60`, matching USGS and FUNVISIS.
2. **Cursor-based, not seen-set.** Unlike FUNVISIS (Venezuela-only, small volume, no
   reliable timestamp cursor semantics confirmed), GEOFON's `fdsnws-event` supports a
   `starttime` query parameter, so — like `RESTReconciler` — `GEOFONPoller` persists a
   cursor (`cursor_geofon_ms` or reuses `AppState`'s timestamp-based cursor pattern) to
   query only new events since the last successful poll, avoiding re-fetching history on
   every cycle.
3. **`format=text` (pipe-delimited), not GeoJSON.** GEOFON's `fdsnws-event` supports
   multiple output formats; `format=text` was verified to return a stable pipe-delimited
   schema (`#EventID|Time|Latitude|Longitude|Depth/km|Author|Catalog|Contributor|
   ContributorID|MagType|Magnitude|MagAuthor|EventLocationName|EventType`, see
   `API-SPEC.md` §4.2). This is a genuinely different wire shape from EMSC/USGS/FUNVISIS
   (all JSON), so `Normalizer` needs a small dedicated text-parsing branch
   (line-split on `|`, skip the `#`-prefixed header) rather than reusing the JSON mapping
   path — the field mapping itself (§API-SPEC.md §5.1) still funnels into the same
   `SeismicEvent`.
4. **Global scope, filtered like every other source.** No country/region restriction is
   applied at ingestion; the existing radius/magnitude `GeoFilter` (RF-12) and the
   optional country filter (RF-37) apply uniformly, so GEOFON does not need its own
   geographic scoping logic.
5. **Participates fully in cross-source dedup.** A GEOFON report of an earthquake already
   alerted via EMSC/USGS/FUNVISIS must not produce a duplicate alert (CA-18). No changes
   to the dedup heuristic itself (RF-09: ≤100 km, ≤90 s, ≤0.5 mag) are needed — it is
   already source-count-agnostic — but the regression test suite gains cases with a
   fourth source in the mix.
6. **Independent failure isolation.** Like every ingestion source, `GEOFONPoller` runs as
   its own supervised asyncio task with its own timeout/backoff; a GEOFON outage or format
   change never blocks or crashes EMSC/USGS/FUNVISIS ingestion (RNF-03).

## Components (planned — Phase 14)

- `ingest/rest_geofon.py` — `GEOFONPoller`: `httpx`-based polling of
  `https://geofon.gfz.de/fdsnws/event/1/query?format=text&...`, parses the pipe-delimited
  response, emits `RawMessage`s onto `raw_queue`; persisted cursor via `StateStore`.
- `pipeline/normalize.py` — new text-format parsing branch for GEOFON payloads, mapping
  into `SeismicEvent` (source=`"GEOFON"`); reuses `geo.py::haversine_km` and severity
  derivation unchanged.
- `config.py` — `GEOFONSource` pydantic model (`enabled`, `url`, `poll_interval_s`,
  `timeout_s`), already drafted in `DATA-MODEL.md` §3.2.
- `models.py` — `SeismicEvent.source` literal gains `"GEOFON"` (already drafted in
  `DATA-MODEL.md` §1.1).
- `supervisor.py` — wires `GEOFONPoller` as a fourth supervised task alongside `ws`,
  `rest` (USGS), and `rest_funvisis`, each independently restarted with backoff on
  failure.
- `state.py` — extends `AppState`/`StateStore` with a GEOFON cursor field, following the
  existing `cursor_usgs_ms` pattern.

## Testing (planned)

- Unit: text-format parsing (header skip, `|`-split, type coercion, malformed-line
  handling) against the verified example response in `API-SPEC.md` §4.2.
- Unit: cursor advancement/persistence logic, mirroring existing USGS cursor tests.
- Integration: fake GEOFON HTTP server returning fixture text responses (happy path,
  empty result, 429/5xx, invalid/truncated text) — mirrors the existing USGS/FUNVISIS
  integration test pattern.
- Regression: cross-source dedup test suite extended with GEOFON-vs-EMSC,
  GEOFON-vs-USGS, and GEOFON-vs-FUNVISIS duplicate scenarios (CA-18), plus a
  GEOFON-only new-event scenario (no duplicate suppression).
- Resilience: GEOFON unreachable/format-change does not affect EMSC/USGS/FUNVISIS
  ingestion or crash the Supervisor (mirrors `ARCHITECTURE.md` §6 resilience row).

## Trade-offs / future

- Text format means GEOFON needs its own parser instead of reusing a shared JSON path —
  slightly more code than a "just another JSON source" would need, but avoids relying on
  an unverified GeoJSON variant of `fdsnws-event`.
- Adding a fourth polling source increases the number of independent 60 s HTTP round
  trips per cycle (now three: USGS, FUNVISIS, GEOFON) but each is independently
  lightweight and non-blocking (asyncio); no batching across sources is planned since
  each has a different query contract.
- If GEOFON later exposes a real-time push channel (not currently known to exist), the
  polling approach here could be revisited the same way EMSC WS became primary over an
  initial polling-only design.
