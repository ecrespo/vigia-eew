# API Spec — Source Contracts and Normalized Event

| Field | Value |
|---|---|
| Document | Contract of the sources consumed by Vigía + internal normalized schema |
| Version | 1.0 (draft for review) |
| Status | 🟡 Pending approval |
| Related | `PRD.md` (RF-01..RF-11, RF-38, RF-39), `DATA-MODEL.md`, `ARCHITECTURE.md` |

> Vigía **consumes** four external contracts (input) — EMSC, USGS, FUNVISIS, GEOFON — and
> defines **one** internal contract (the normalized event) that the rest of the system produces
> and consumes. It does not expose any network API of its own in v1. The EMSC and USGS contracts
> were verified against the live endpoints on 2026-06-28; the FUNVISIS contract was verified
> against the live endpoint on 2026-07-05 (documented retroactively, already shipped in v0.4.0);
> the GEOFON contract (§4) was verified against the live `fdsnws-event` endpoint on 2026-07-05,
> ahead of its implementation (Phase 14).

---

## 1. PRIMARY source — EMSC WebSocket (real push)

### 1.1 Endpoint and transport
- **URL**: `wss://www.seismicportal.eu/standing_order/websocket`
- **Transport**: WebSocket (RFC 6455). Also served via SockJS (`/standing_order`), but the Python client uses the direct **`/websocket`** endpoint with the `websockets` library.
- **Authentication**: none (public, free).
- **Direction**: server→client only. The client does not send data messages; only control frames (ping/pong).

### 1.2 Keepalive (MANDATORY) — RF-02
The socket dies **silently** without keepalive. A **ping every ~15 s** must be sent
(`PING_INTERVAL = 15`, confirmed in the official EMSC example). With the `websockets` library:

```python
async with websockets.connect(
    "wss://www.seismicportal.eu/standing_order/websocket",
    ping_interval=15,   # sends a ping every 15 s
    ping_timeout=20,    # closes if no pong → triggers reconnection
) as ws:
    async for raw in ws:
        ...
```

### 1.3 Message format
Each message is **JSON text**. Confirmed structure:

```json
{
  "action": "create",
  "data": {
    "type": "Feature",
    "geometry": { "type": "Point", "coordinates": [-66.90, 10.48, 12.0] },
    "id": "20260628_0000123",
    "properties": {
      "lat": 10.48,
      "lon": -66.90,
      "depth": 12.0,
      "mag": 6.1,
      "magtype": "mw",
      "time": "2026-06-28T13:39:00.0Z",
      "lastupdate": "2026-06-28T13:41:00.0Z",
      "auth": "INGV",
      "unid": "20260628_0000123",
      "flynn_region": "NEAR COAST OF VENEZUELA",
      "evtype": "ke"
    }
  }
}
```

| Message field | Type | Meaning | Use in Vigía |
|---|---|---|---|
| `action` | enum `create` \| `update` | Event inserted or corrected | `create`→possible new alert; `update`→update without re-alerting (RF-11) |
| `data` | GeoJSON Feature | The event | Source for normalization |
| `data.properties.unid` | string | **Unique identifier** of the event | internal `id`; intra-EMSC dedup key |
| `data.properties.mag` | number | Magnitude | `magnitude` |
| `data.properties.magtype` | string (**lowercase**) | Magnitude type (`mw`, `mb`, `ml`…) | `magType` (⚠️ name is normalized) |
| `data.properties.lat` / `lon` | number | Coordinates | `lat` / `lon` |
| `data.properties.depth` | number | Depth (km) | `depth_km` |
| `data.properties.time` | ISO-8601 UTC | Origin time | `time_utc` |
| `data.properties.lastupdate` | ISO-8601 UTC | Last update | event version control |
| `data.properties.auth` | string | Authoring agency (INGV, GFZ…) | metadata/audit |
| `data.properties.flynn_region` | string | Flynn-Engdahl region | `region`/`place` |

> ⚠️ **Quirks**: EMSC uses `magtype` (lowercase); the coordinates in `geometry.coordinates`
> follow the GeoJSON order **[lon, lat, depth]**. The `properties` fields (`lat`,
> `lon`, `depth`) are preferred for clarity, using `geometry` as verification.

### 1.4 Behavior and known limitations
- The WS carries events from **many agencies** (including small global earthquakes) → geographic/magnitude filtering happens client-side (RF-12).
- **CAN LOSE MESSAGES** (documented timeouts and bursts). This is why the USGS fallback exists (RF-05).
- May emit several `update`s for the same `unid` (magnitude/location refinement).
- There is no history *replay* on reconnect: anything lost during an outage is recovered via USGS.

---

## 2. FALLBACK source — USGS FDSN (low-frequency polling)

### 2.1 Endpoint
```
GET https://earthquake.usgs.gov/fdsnws/event/1/query
```
**Sole purpose**: (a) recover regional events the WS missed and (b) cover small
local earthquakes. It is **not** a second loop of the same weight as the WS. Frequency: **every 60 s** (RF-05).

### 2.2 Query parameters
| Parameter | Default value | Notes |
|---|---|---|
| `format` | `geojson` | Output format |
| `latitude` | `10.4806` | Reference point (Caracas) — from config |
| `longitude` | `-66.9036` | from config |
| `maxradiuskm` | `300` | Radius of interest — from config |
| `minmagnitude` | `2.5` | Minimum magnitude — from config (RF-12) |
| `orderby` | `time` | Most recent first |
| `eventtype` | `earthquake` | Earthquakes only |
| `starttime` / `updatedafter` | **persisted cursor** | "since the last event seen" (RF-06) |
| `limit` | (optional) | Limit response size |

Example (verified live):
```
https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&latitude=10.4806&longitude=-66.9036&maxradiuskm=300&minmagnitude=2.5&orderby=time&eventtype=earthquake
```

### 2.3 Cursor strategy (RF-06)
- The `time` (epoch ms) of the **most recently processed event** is persisted.
- Each poll queries with `starttime` = cursor (or `updatedafter` to capture revisions).
- After processing, the cursor advances to the maximum `time` seen. The cursor survives restarts (see `DATA-MODEL.md`).

### 2.4 Response format (GeoJSON `FeatureCollection`)
Confirmed live (trimmed to relevant fields):

```json
{
  "type": "FeatureCollection",
  "metadata": { "generated": 1782668911000, "title": "USGS Earthquakes", "status": 200, "api": "2.4.0" },
  "features": [
    {
      "type": "Feature",
      "id": "us6000t8sx",
      "properties": {
        "mag": 4.3,
        "place": "19 km WSW of Morón, Venezuela",
        "time": 1782639238852,
        "updated": 1782655565862,
        "magType": "mb",
        "status": "reviewed",
        "ids": ",us6000t8sx,",
        "sources": ",us,",
        "net": "us",
        "code": "6000t8sx",
        "type": "earthquake",
        "title": "M 4.3 - 19 km WSW of Morón, Venezuela"
      },
      "geometry": { "type": "Point", "coordinates": [-68.3766, 10.4497, 10] }
    }
  ]
}
```

| Field | Type | Meaning | Use in Vigía |
|---|---|---|---|
| `id` (Feature) | string | USGS identifier (`us6000t8sx`) | internal `id`; intra-USGS dedup key |
| `properties.mag` | number | Magnitude | `magnitude` |
| `properties.magType` | string (**camelCase**) | Magnitude type | `magType` (⚠️ name differs from EMSC) |
| `properties.place` | string | Place description | `place` |
| `properties.time` | epoch **ms** | Origin time | `time_utc` (convert from ms) |
| `properties.updated` | epoch **ms** | Last revision | `updatedafter` cursor |
| `properties.status` | string | `reviewed`/`automatic` | metadata/quality |
| `geometry.coordinates` | [lon, lat, depth_km] | Position | `lon`, `lat`, `depth_km` |

> ⚠️ **Quirks**: USGS uses `magType` (camelCase) and `time`/`updated` in **epoch milliseconds**;
> EMSC uses `magtype` (lowercase) and ISO-8601 `time`. The normalizer resolves both (see §3 and `DATA-MODEL.md`).

### 2.5 Errors and resilience (RNF-03)
| Situation | Handling |
|---|---|
| HTTP 429 (rate limit) | Respect `Retry-After` if present; back off; the cycle continues. |
| HTTP 5xx | Retry on the next cycle; warning log; do not abort. |
| Network timeout | `httpx` with timeout; skip the cycle; keep the cursor. |
| Invalid JSON / unexpected schema | Validate with pydantic; discard invalid Feature; log; do not terminate. |

---

## 3. LOCAL source — FUNVISIS (Venezuela-only, low-frequency polling)

### 3.1 Endpoint
```
GET http://www.funvisis.gob.ve/maravilla.json
```
FUNVISIS (Fundación Venezolana de Investigaciones Sismológicas, the Venezuelan national seismic
network) publishes no real-time push channel; this is the JSON file its own web map polls,
listing the ~20 most recent events. **Sole purpose**: cover the small local earthquakes (M2–3)
that EMSC/USGS don't catalog, for **Venezuela only**. Plain **HTTP** — FUNVISIS offers no valid
HTTPS; the data is public, so no encrypted channel is required. Frequency: **every 60 s** (RF-38).

### 3.2 Response format
Confirmed live (trimmed to relevant fields; exact key names/types depend on the live payload and
are validated defensively with pydantic — unexpected or missing fields cause the single Feature to
be discarded, not the whole batch):

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "id": "2026abcd123",
        "mag": 2.8,
        "place": "10 km SE de Caracas",
        "date": "2026-07-05 14:22:10",
        "depth": 8.0
      },
      "geometry": { "type": "Point", "coordinates": [-66.85, 10.40] }
    }
  ]
}
```

| Field | Type | Meaning | Use in Vigía |
|---|---|---|---|
| `properties.id` | string | FUNVISIS identifier | internal `id`; intra-FUNVISIS dedup (seen-set) |
| `properties.mag` | number | Magnitude | `magnitude` |
| `properties.place` | string | Place description (Spanish) | `place` |
| `properties.date` | local Venezuela time (naive) | Origin time | `time_utc` (converted from America/Caracas, made tz-aware) |
| `properties.depth` | number | Depth (km) | `depth_km` |
| `geometry.coordinates` | [lon, lat] | Position | `lon`, `lat` |

> ⚠️ **Quirks**: FUNVISIS has no explicit `magType`/`magtype` field in the public feed; a fixed
> placeholder (e.g. `"ml"`, local magnitude) is used pending confirmation from FUNVISIS. Timestamps
> are in **local Venezuela time**, not UTC — the normalizer must localize to `America/Caracas`
> before converting to UTC (unlike EMSC/USGS, which are already UTC).

### 3.3 Behavior and known limitations
- **No real push**: the agent polls every 60 s (RF-38); there is no `create`/`update` distinction
  like EMSC — every poll returns the current top-N batch.
- **Startup seeding**: the first poll's ids populate an in-memory seen-set **without** alerting,
  so the agent doesn't replay FUNVISIS's history as a burst of alerts on every restart; only ids
  appearing in a **later** poll are new and trigger the pipeline.
- **Venezuela-only**: FUNVISIS only reports Venezuelan events; for users outside Venezuela these
  simply fall outside `radius_km` (RF-12) and are filtered out like any other distant event.
- No documented rate limit; the 60 s interval is a courtesy default, configurable.

### 3.4 Errors and resilience (RNF-03)
| Situation | Handling |
|---|---|
| HTTP error / network timeout | Logged as a warning; the cycle is skipped; the seen-set is preserved; polling continues. |
| Invalid JSON / unexpected schema | Validate with pydantic; discard the invalid Feature; log; do not terminate. |
| Endpoint unreachable for an extended period | No alert is raised about the outage itself (best-effort source); EMSC/USGS coverage is unaffected. |

---

## 4. Additional source — GEOFON (GFZ Potsdam, global network, low-frequency polling)

### 4.1 Endpoint
```
GET http://geofon.gfz.de/fdsnws/event/1/query
```
GEOFON is the global seismic network operated by the GFZ German Research Centre for Geosciences
(Potsdam). It exposes a standard **FDSN `fdsnws-event`** web service (the same family of service
USGS implements), providing **redundant coverage from a different network** than EMSC/USGS, with
**no API key required**. **Sole purpose**: additional independent low-frequency polling
(every 60 s, RF-39), analogous in role to the USGS fallback (RF-05) but from a distinct source, to
catch events either EMSC or USGS might miss or classify differently.

### 4.2 Query parameters
| Parameter | Default value | Notes |
|---|---|---|
| `format` | `text` | Pipe-delimited text (see §4.3) — GeoJSON support is **not confirmed** for this endpoint, unlike USGS's fdsnws-event, so the text format is used instead of reusing the USGS GeoJSON parser. |
| `lat` | `10.4806` | Reference point (Caracas) — from config |
| `lon` | `-66.9036` | from config |
| `maxradius` | derived from `maxradiuskm` (config) | fdsnws-event expresses radius in **degrees**, not km; converted at query time |
| `minmagnitude` | `2.5` | Minimum magnitude — from config (RF-12) |
| `orderby` | `time` | Most recent first |
| `starttime` | **persisted cursor** | "since the last event seen", same strategy as USGS (§2.3) |

Example (verified live):
```
http://geofon.gfz.de/fdsnws/event/1/query?eventid=gfz2020smye&format=text
```

### 4.3 Response format (FDSN pipe-delimited text)
Confirmed live. One header line followed by one `|`-delimited row per event:

```
#EventID|Time|Latitude|Longitude|Depth/km|Author|Catalog|Contributor|ContributorID|MagType|Magnitude|MagAuthor|EventLocationName|EventType
gfz2020smye|2020-01-15T12:00:00.0|10.48|-66.90|12.0|GFZ|GFZ|GFZ|gfz2020smye|Mw|6.1|GFZ|NEAR COAST OF VENEZUELA|earthquake
```

| Column | Type | Meaning | Use in Vigía |
|---|---|---|---|
| `EventID` | string | GEOFON identifier | internal `id`; intra-GEOFON dedup key |
| `Time` | ISO-8601 UTC | Origin time | `time_utc` |
| `Latitude` / `Longitude` | number | Coordinates | `lat` / `lon` |
| `Depth/km` | number | Depth (km) | `depth_km` |
| `MagType` | string | Magnitude type (`Mw`, `mb`…) | `magType` (⚠️ mixed case, normalized like EMSC/USGS) |
| `Magnitude` | number | Magnitude | `magnitude` |
| `EventLocationName` | string | Free-text location | `place`/`region` |
| `EventType` | string | e.g. `earthquake` | filter to earthquakes only, same as USGS's `eventtype` |

> ⚠️ **Quirks**: the response is **not JSON** — it must be parsed as pipe-delimited text (split on
> `|`, first line is the header/column names). QuakeML (XML) is also available from the same
> endpoint but is **not used** in v1 to avoid an XML-parsing dependency; the text format is
> sufficient and dependency-free (RNF-06).

### 4.4 Errors and resilience (RNF-03)
| Situation | Handling |
|---|---|
| HTTP 204 (no matching events) | Not an error: empty result, cycle completes normally. |
| HTTP 4xx/5xx | Retry on the next cycle; warning log; do not abort. |
| Network timeout | `httpx` with timeout; skip the cycle; keep the cursor. |
| Malformed text row (wrong column count) | Discard the single row; log; do not terminate; do not discard the rest of the batch. |

---

## 5. INTERNAL contract — Normalized event

All sources are normalized to **one common schema** (RF-07). This is the contract that flows between
layers (ingestion → dedup/filter → notification). Canonical schema (type details in `DATA-MODEL.md`):

```json
{
  "id": "us6000t8sx",
  "source": "USGS",
  "magnitude": 4.3,
  "magType": "mb",
  "place": "19 km WSW of Morón, Venezuela",
  "region": "NEAR COAST OF VENEZUELA",
  "lat": 10.4497,
  "lon": -68.3766,
  "depth_km": 10.0,
  "time_utc": "2026-06-28T13:33:58.852Z",
  "distance_km": 162.4,
  "severity": "warning",
  "lastupdate_utc": "2026-06-28T13:46:05.862Z"
}
```

### 5.1 Field mapping by source

| Normalized field | EMSC (WS) | USGS (FDSN) | FUNVISIS | GEOFON (FDSN) |
|---|---|---|---|---|
| `id` | `properties.unid` | `id` (Feature) | `properties.id` | `EventID` |
| `source` | `"EMSC"` | `"USGS"` | `"FUNVISIS"` | `"GEOFON"` |
| `magnitude` | `properties.mag` | `properties.mag` | `properties.mag` | `Magnitude` |
| `magType` | `properties.magtype` (↑normalized to consistent lowercase) | `properties.magType` | fixed placeholder (not published; pending confirmation) | `MagType` (↑normalized, mixed case) |
| `place` | — (use `flynn_region`) | `properties.place` | `properties.place` | `EventLocationName` |
| `region` | `properties.flynn_region` | derived from `place` | derived from `place` | derived from `EventLocationName` |
| `lat` | `properties.lat` | `geometry.coordinates[1]` | `geometry.coordinates[1]` | `Latitude` |
| `lon` | `properties.lon` | `geometry.coordinates[0]` | `geometry.coordinates[0]` | `Longitude` |
| `depth_km` | `properties.depth` | `geometry.coordinates[2]` | `properties.depth` | `Depth/km` |
| `time_utc` | `properties.time` (ISO-8601) | `properties.time` (epoch ms → ISO) | `properties.date` (local America/Caracas → UTC) | `Time` (ISO-8601) |
| `lastupdate_utc` | `properties.lastupdate` | `properties.updated` (epoch ms → ISO) | not available (no revision channel) | not available (no revision channel) |
| `distance_km` | calculated (haversine vs. reference point) | calculated | calculated | calculated |
| `severity` | calculated (by magnitude, config RF-13) | calculated | calculated | calculated |

### 5.2 Internal contract invariants
- `id` is stable per source; **cross-source** dedup uses the heuristic (≤100 km, ≤90 s, ≤0.5 mag), not the `id` (RF-09).
- `time_utc` is always in UTC; conversion to local time (America/Caracas) happens **only in the presentation layer** (RF-18, RNF-12).
- `distance_km` and `severity` are **derived**: they are calculated during normalization/filtering, never coming from the source.

---

## 6. Auxiliary source — IP geolocation (RF-33)

Used **only** when the user does not define `[reference]` in `config.toml`, to estimate a reasonable
geographic reference point without manual intervention. It is "best effort": any failure
falls back to the default (Caracas) without blocking startup (see `geoloc.py`, `TECHNICAL-DESIGN.md`).

| Element | Value |
|---|---|
| Endpoint | `https://ipapi.co/json/` (HTTPS, no API key) |
| Method | `GET`, no parameters (the source IP is inferred by the service) |
| Timeout | 5 s |
| Frequency | **Once** per installation — the result is cached in `state.json` (`detected_location`) and is not repeated on subsequent startups unless the state is deleted or a manual `[reference]` is defined. |

### 6.1 Fields used from the response

| JSON field | Use |
|---|---|
| `latitude`, `longitude` | `ReferencePoint.lat` / `ReferencePoint.lon` (required; if missing or non-numeric, the response is discarded) |
| `city` | `ReferencePoint.name`; if missing, `country_name` is used; if that's also missing, a generic name |

### 6.2 Errors and resilience
| Situation | Handling |
|---|---|
| No network / timeout / HTTP error | Caught, a *warning* is logged, `None` is returned (fallback to default). |
| Status ≠ 200 | Same as above. |
| Invalid JSON or missing/out-of-range fields | Same as above; never raises an exception to the caller. |

---

## 7. Future evolution (not v1) — Central relay

Documented in `TECHNICAL-DESIGN.md` (ADR-008): a FastAPI relay could expose its own *fan-out*
WebSocket to many Vigía clients, reusing **the same internal contract** from §5 as the payload,
so that the migration doesn't break the data model.

## 8. Future evolution (not v1) — D-Bus contract (optional GNOME frontend)

Documented in `TECHNICAL-DESIGN.md` (ADR-010, detailed elaboration): the agent could expose a
service on the **session bus** so that a GNOME Shell extension (or other local frontend) can
subscribe to alerts and confirm acknowledgment, without duplicating the schema from §5.

| Element | Value |
|---|---|
| Bus | Session (`DBUS_SESSION_BUS_ADDRESS`), not the *system bus* |
| Service name | `org.vigia_eew.Agent` |
| Object path | `/org/vigia_eew/Agent` |
| Interface | `org.vigia_eew.Agent.Alerts1` (versioned) |

| Member | Signature | Payload |
|---|---|---|
| signal `NewAlert` | `(s)` | `SeismicEvent` JSON — same schema as §5 |
| signal `AlertUpdated` | `(s)` | `SeismicEvent` JSON, `action="update"` (RF-11) |
| method `Acknowledge` | `(s) -> (b)` | `id` of the event to acknowledge |
| method `GetActive` | `() -> (s)` | current `SeismicEvent` JSON, or `""` if there isn't one |
| method `Ping` | `() -> (s)` | agent version, e.g. `"1.0"` |

The signal payload is **the same JSON as the internal contract** (§5), serialized as-is
(`model_dump_json()`); no parallel D-Bus *struct* is defined. This contract is additive to the
Tk window (ADR-003): it does not replace it unless the GNOME extension is detected and active (see
`frontend = "auto"` selection in `TECHNICAL-DESIGN.md`). **Not implemented in v1.**
