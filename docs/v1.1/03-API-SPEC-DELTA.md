# API Spec delta — Vigía-eew v1.1

> Artifact 03 of the v1.1 kit · 2026-11-16 · Base commit: `bb58be8`
> Base documents: [`docs/API-SPEC.md`](../API-SPEC.md) and
> [`docs/v1/03-API-SPEC-DELTA.md`](../v1/03-API-SPEC-DELTA.md)

## 1. What it contains and what it does not

Vigía-eew still exposes no network API of its own. This delta specifies:

| § | Contract | Kind | New or extended |
|---|---|---|---|
| 2 | Command line | external, consumed by users and launchers | extended: two options |
| 3 | Catalogue recovery | external, **consumed** from three networks | **new** |
| 4 | History store | internal | extended |
| 5 | History list | internal | extended |
| 6 | Timeline | internal | **new** |
| 7 | Figures and export | internal | **new** |
| 8 | Shaking estimate | internal | **new** |
| 9 | Shell and alert queue | internal | extended |

It does not repeat the live contracts of EMSC, USGS, FUNVISIS and GEOFON (`API-SPEC.md` §1–§4), nor
the configuration-writing and tile contracts of the v1.0 delta. None of them changes.

---

## 2. Command line *(extended)*

| Option | Does | Starts the agent | Exit |
|---|---|---|---|
| `--history` | Opens the history screen in a standalone window | no | 0 when the window is closed |
| `--backfill DAYS` | Recovers the last `DAYS` days from the catalogues, prints the outcome | no | 0 if at least one network was recovered or there was nothing to recover; 1 if every recoverable network failed; 2 if `DAYS` is refused |

`--history` is dispatched before `--tui`, `--simulate` and the agent, like `--settings`. `--history`
and `--settings` together open the history; the navigation leads to the other.

`--backfill` outcome, one line per configured network, on standard output:

```text
EMSC      recovered 109 · already present 12
USGS      recovered 91 · already present 0
GEOFON    failed: timeout after 30 s
FUNVISIS  not recoverable: the service offers no query by date
```

Refusal, on standard error, naming the limit (REQ-HIS-012):

```text
cannot recover 400 days: recovered entries are kept for 365 ([history] recovered_retention_days)
```

**Launcher.** Every packaged platform's launcher entry declares a *History* action that runs
`vigia-eew --history`. On Linux: `Actions=Settings;History;Simulate;` in `vigia-eew.desktop`.

---

## 3. Catalogue recovery *(new, consumed)*

Three networks serve an FDSN `fdsnws-event` catalogue that takes a date range. The agent already
polls two of them live; this contract is the **same service asked for a period** instead of *"since
my cursor"*.

| Network | URL | Configured in | Format asked | Parsed by |
|---|---|---|---|---|
| EMSC | `https://www.seismicportal.eu/fdsnws/event/1/query` | `[emsc] catalog_url` **(new key)** | `json` | the EMSC normaliser — the `properties` are the WebSocket's |
| USGS | `https://earthquake.usgs.gov/fdsnws/event/1/query` | `[usgs] url` | `geojson` | the USGS normaliser |
| GEOFON | `https://geofon.gfz.de/fdsnws/event/1/query` | `[geofon] url` | `text` | the GEOFON normaliser |
| FUNVISIS | — | — | — | **not recoverable**: `maravilla.json` returns the ~20 most recent events and takes no parameters |

### 3.1 Request

```text
GET {url}?format={format}
        &starttime={ISO-8601 UTC}&endtime={ISO-8601 UTC}
        &latitude={ref.lat}&longitude={ref.lon}&maxradius={degrees}
        &minmagnitude={recovery_min_magnitude}
        &orderby=time&limit={page}&offset={n}
```

| Parameter | Value | Note |
|---|---|---|
| `starttime`, `endtime` | A window of at most 30 days | A recovery of 365 days is 13 windows per network |
| `maxradius` | `recovery_radius_km` ÷ 111.195 | FDSN expresses the radius in degrees. USGS also accepts `maxradiuskm`; degrees are used for all three so that there is one conversion |
| `limit`, `offset` | Page of 1 000; `offset` starts at 1 | FDSN's `offset` is 1-based. A page shorter than `limit` ends the window |
| `eventtype` | `earthquake`, for USGS only | As the live poller does |

The client is the shared `httpx` client with the application's user agent and a 30 s timeout.
Windows are requested one at a time per network: no parallel requests to one host.

### 3.2 Verified against the live service — EMSC, 2026-11-16

`format=json` returns a GeoJSON `FeatureCollection`. Each feature's `properties` carries `unid`,
`time`, `lat`, `lon`, `depth`, `mag`, `magtype`, `flynn_region`, `auth`, `lastupdate` — the fields
of the WebSocket's `data.properties` (`API-SPEC.md` §1). `unid` is the id the agent stores as
`source_event_id`, so a recovered event the agent already holds collides on the unique key.

`format=text` returns the pipe-delimited layout GEOFON uses, with the header
`#EventID|Time|Latitude|Longitude|Depth/km|Author|Catalog|Contributor|ContributorID|MagType|Magnitude|MagAuthor|EventLocationName`.

A count for October 2026, 9° around Caracas, M ≥ 2.5: EMSC 109, USGS 91, GEOFON 4.

> ⚠️ **Quirk.** In EMSC's GeoJSON the third coordinate is the depth as a **negative** number
> (`-39.6`), while `properties.depth` is positive (`39.6`). The normaliser reads `properties.depth`,
> as it does for the WebSocket.

### 3.3 Responses

| Response | Meaning | What the recovery does |
|---|---|---|
| 200 with events | — | Normalises and records them |
| 204, or 200 with none | Nothing in that window | Next window |
| 400 | The request was refused | That network fails with the body's first line; the others continue |
| 429, 5xx, timeout | Unavailable | One retry after a backoff; then that network fails and the others continue |
| A record that does not parse | — | Skipped and counted; the rest of the page is recorded |

### 3.4 What this contract does not do

- It does not write to `raw_queue`, and nothing it reads reaches the pipeline's filter,
  deduplicator or alert controller.
- It does not read or move the live cursors in `state.json`.
- It does not run by itself: only on `--backfill` or the screen's *Recover…* action.

---

## 4. History store *(extended)*

| Operation | Signature | Contract |
|---|---|---|
| `record_recovered` | `(EventRecord) → bool` | Inserts with verdict `recovered`. Returns `False` and changes nothing if a row for that `(source, source_event_id)` exists |
| `near` | `(occurred_at, window_s) → list[EventRecord]` | Rows within the window, for the recovery to compare with the deduplicator's predicate |
| `arrivals` | `(correlation_id) → list[EventRecord]` | Every arrival of one earthquake, prevailing first |
| `verdicts` | `() → list[str]` | The verdicts present, like `sources()` |
| `query`, `count` | `(HistoryQuery)` | Honour `reading`; in the earthquake reading `count` counts earthquakes |
| `prune` | `(retention_days, recovered_retention_days, now)` | Two cut-offs, one statement |

`record()` is unchanged, including that it replaces the row of the same arrival — which is what
lets a live evaluation overwrite a recovered row.

Every statement stays a prepared constant with bound parameters.

## 5. History list *(extended)*

The only object the views talk to. It imports no toolkit and no network library.

| Operation | Contract |
|---|---|
| `set_period(first_day, last_day)` | Local calendar days in the configured zone; either may be `None`. Raises `ValueError` if the last precedes the first, leaving the query as it was |
| `set_max_distance(km)`, `set_sources(names)`, `set_verdict(v)`, `set_min_magnitude(m)` | Each returns to the first page |
| `set_reading("arrival" \| "earthquake")` | Returns to the first page |
| `next_page()`, `previous_page()`, `go_to(row_id)` | `go_to` moves to the page holding that row |
| `stretch` | `(first, last, total)` of the page on screen; `total` is the store's count |
| `rows` | The page, formatted for display |
| `everything(limit)` | The filtered set in full, up to `limit`, and whether it was cut short |
| `row_for(record)` | The formatted row for one record — what the table shows and what the map's tooltip shows |

## 6. Timeline *(new)*

Pure. No toolkit, no clock.

| Operation | Contract |
|---|---|
| `Timeline(records, fade, trail)` | Sorted by `occurred_at`; equal instants share a step |
| `len(timeline)` | Number of steps |
| `frame(i) → Frame` | `instant`, and for every earthquake with `occurred_at ≤ instant` an intensity in `[0, 1]` |
| `dwell(i, speed) → seconds` | Gap to the next step ÷ speed, clamped to `[MIN_DWELL, MAX_DWELL]`; the last step returns `MAX_DWELL` |
| `step_at(instant) → i` | The last step at or before an instant, for seeking |

**Invariants**, each a test: no earthquake in `frame(i)` happened after `frame(i).instant`; an
earthquake's intensity is 1 at its own step and never increases with *i*; `frame(i)` does not depend
on how *i* was reached nor on the speed.

## 7. Figures and export *(new)*

| Operation | Contract |
|---|---|
| `summarise(earthquakes, arrivals, period) → Summary` | Splits per local day, magnitude band, verdict and reason over earthquakes; split by network and median latency over arrivals. Every figure with its sample size |
| `to_csv(records, file)` | Header row, UTC instants with offset |
| `to_geojson(records, file)` | RFC 7946 `FeatureCollection`, points as `[longitude, latitude]` |

`summarise` of empty sequences returns a `Summary` that says it is empty; it does not return zeros.

## 8. Shaking estimate *(new)*

| Operation | Contract |
|---|---|
| `estimate(event, now) → ShakingEstimate \| None` | `seconds`: positive while the S wave is on its way, negative once it should have arrived. `None` if the origin time is ahead of `now` beyond the tolerance or an input is not finite |
| `format_shaking(estimate, locale) → str` | Remaining: whole seconds, rounded down. Elapsed: seconds below a minute, whole minutes above. Always with the approximation mark |

## 9. Shell and alert queue *(extended)*

| Operation | Change |
|---|---|
| `FletShell.show_screen(key, title, view, on_covered=None, on_uncovered=None)` | The two callbacks are called when an alert takes the window from this screen and when it returns it |
| `AlertQueue.enqueue(event)` | If the alert on screen is a drill and `event` is not, the drill is closed unacknowledged and `event` is shown |
| `AlertQueue.idle` | True when nothing is shown and nothing is pending — what a drill waits for |

## 10. Invariants every contract of this delta respects

1. **Nothing here can present an alert** except the alert queue, and the only new thing that
   enqueues is the drill.
2. **Nothing here writes outside its own store**: recovery to the history, the drill to
   `state.json`, the export to the path the user chose.
3. **Every instant crossing a contract is tz-aware UTC.** Local time exists in `timeutil` and in
   `presentation`.
4. **Every clock and every network client is injected.**
5. **A failure in any of this costs no alert** (Art. 1, Art. 3).
