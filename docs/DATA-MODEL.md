# Data Model — Vigía-eew

| Field | Value |
|---|---|
| Document | Data model: normalized event, persisted state, and configuration |
| Version | 1.0 (draft for review) |
| Status | 🟡 Pending approval |
| Related | `API-SPEC.md` (source mapping), `PRD.md` (RF-07, RF-06, RF-10, RF-24, RF-38, RF-39), `TECHNICAL-DESIGN.md` |

> All structures are validated with **pydantic** (v2). The types here are the binding contract
> for the code. Persistence in **JSON**; configuration in **`config.toml`**.

---

## 1. Entity: Normalized seismic event (`SeismicEvent`)

Internal contract that flows between layers (RF-07). Produced by `Normalizer`, consumed by
`GeoFilter`, `Deduplicator`, and the notification layer.

| Field | Type | Required | Description | Origin |
|---|---|---|---|---|
| `id` | `str` | yes | Stable per-source identifier (`unid` EMSC / `id` USGS / `id` FUNVISIS / `EventID` GEOFON) | source |
| `source` | `Literal["EMSC","USGS","FUNVISIS","GEOFON","SIMULATED"]` | yes | Event origin | system |
| `magnitude` | `float` | yes | Magnitude | source |
| `mag_type` | `str` | yes | Magnitude type (`mw`,`mb`,`ml`…), normalized to lowercase | source |
| `place` | `str \| None` | no | Textual description (USGS `place`) | source |
| `region` | `str \| None` | no | Flynn region (EMSC `flynn_region`) or derived | source |
| `lat` | `float` (−90..90) | yes | Epicenter latitude | source |
| `lon` | `float` (−180..180) | yes | Epicenter longitude | source |
| `depth_km` | `float` (≥0) | yes | Depth | source |
| `time_utc` | `datetime` (tz-aware UTC) | yes | Origin time | source |
| `lastupdate_utc` | `datetime \| None` | no | Last update/revision | source |
| `distance_km` | `float` (≥0) | yes | Distance to the reference point (haversine) | derived |
| `severity` | `Literal["info","warning","critical"]` | yes | Level based on magnitude (config) | derived |
| `action` | `Literal["create","update"]` | yes | Message type (default `create`) | source/system |

### 1.1 Pydantic definition (reference)
```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class SeismicEvent(BaseModel):
    id: str
    source: Literal["EMSC", "USGS", "FUNVISIS", "GEOFON", "SIMULATED"]
    magnitude: float
    mag_type: str
    place: str | None = None
    region: str | None = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    depth_km: float = Field(ge=0)
    time_utc: datetime                       # always tz-aware UTC
    lastupdate_utc: datetime | None = None
    distance_km: float = Field(ge=0)
    severity: Literal["info", "warning", "critical"]
    action: Literal["create", "update"] = "create"
```

### 1.2 Rules and invariants
- `time_utc`/`lastupdate_utc` are **always UTC tz-aware**. Conversion to `America/Caracas` happens
  only in presentation (RF-18, RNF-12), never in the model.
- `distance_km` and `severity` are **derived** (they do not come from the source).
- `mag_type` is always normalized to lowercase (reconciles EMSC `magtype` vs USGS `magType`).
- USGS delivers `time`/`updated` in **epoch ms** → convert; EMSC in **ISO-8601** → parse.

### 1.3 Severity (derivation) — RF-13
Configurable thresholds; by default:

| Severity | Magnitude range | Color | Sound |
|---|---|---|---|
| `info` | `< 4.0` | blue/gray | soft, single chime |
| `warning` | `4.0 – 5.5` | amber | medium, repeated |
| `critical` | `≥ 5.5` | red | loud, insistent |

---

## 2. Persisted state (`AppState`) — RF-06, RF-10

Survives restarts; avoids re-alerting and enables reconciliation (RF-10, RF-06). Saved as **JSON**
with atomic writes.

| Field | Type | Description |
|---|---|---|
| `version` | `int` | State schema version (future migrations) |
| `cursor_usgs_ms` | `int \| None` | Epoch ms of the most recent processed USGS event (cursor RF-06) |
| `alerted_ids` | `list[AlertedId]` | Already-alerted ids (with age-based pruning) |
| `recent_signatures` | `list[EventSignature]` | Signatures for cross-source dedup (time window) |
| `detected_location` | `DetectedLocation \| None` | Location detected via IP, cached after the first successful detection (RF-33); `None` if never detected or if the user configures a manual `[reference]` |

```python
class AlertedId(BaseModel):
    id: str
    source: str
    time_utc: datetime
    acknowledged_utc: datetime | None = None    # acknowledge audit trail

class EventSignature(BaseModel):
    lat: float
    lon: float
    time_utc: datetime
    magnitude: float

class DetectedLocation(BaseModel):
    name: str
    lat: float
    lon: float
    detected_utc: datetime

class AppState(BaseModel):
    version: int = 1
    cursor_usgs_ms: int | None = None
    alerted_ids: list[AlertedId] = []
    recent_signatures: list[EventSignature] = []
    detected_location: DetectedLocation | None = None
```

### 2.1 Location (cross-platform, via `platformdirs`)
| OS | Path |
|---|---|
| Linux | `~/.local/share/vigia-eew/state.json` |
| Windows | `%LOCALAPPDATA%\vigia-eew\state.json` |
| macOS | `~/Library/Application Support/vigia-eew/state.json` |

### 2.2 Pruning policy
- `alerted_ids` and `recent_signatures` are pruned by age (e.g. > 24 h) to bound size.
- **Atomic** write: temporary file + `os.replace` (avoids corruption on crash).

---

## 3. Configuration (`config.toml` → `Settings`) — RF-24

Read with `tomllib` (stdlib 3.11+) and validated with **pydantic**. Sensible *defaults* centered on
Caracas.

### 3.1 Example `config.toml`
```toml
[reference]
name = "Caracas"
lat = 10.4806
lon = -66.9036

[filter]
radius_km = 300.0
min_magnitude = 2.5

[sources.emsc]
enabled = true
url = "wss://www.seismicportal.eu/standing_order/websocket"
ping_interval_s = 15
ping_timeout_s = 20
backoff_max_s = 60

[sources.usgs]
enabled = true
url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
poll_interval_s = 60
timeout_s = 15

[sources.funvisis]
enabled = true
url = "http://www.funvisis.gob.ve/maravilla.json"
poll_interval_s = 60
timeout_s = 15

[sources.geofon]
enabled = true
url = "http://geofon.gfz.de/fdsnws/event/1/query"
poll_interval_s = 60
timeout_s = 15

[dedup]
distance_km = 100.0
window_s = 90
magnitude_delta = 0.5

[severity]
# upper bound of each level; anything above is "critical"
info_max = 4.0
warning_max = 5.5

[notification]
fullscreen = false
timezone = "America/Caracas"
sound = true

[logging]
level = "INFO"
file = "vigia-eew.log"
max_bytes = 1048576
backups = 3
```

### 3.2 Pydantic definition (reference)
```python
from pydantic import BaseModel, Field

class ReferencePoint(BaseModel):
    name: str = "Caracas"
    lat: float = Field(10.4806, ge=-90, le=90)
    lon: float = Field(-66.9036, ge=-180, le=180)

class Filter(BaseModel):
    radius_km: float = Field(300.0, gt=0)
    min_magnitude: float = Field(2.5, ge=0)

class EMSCSource(BaseModel):
    enabled: bool = True
    url: str = "wss://www.seismicportal.eu/standing_order/websocket"
    ping_interval_s: int = 15
    ping_timeout_s: int = 20
    backoff_max_s: int = 60

class USGSSource(BaseModel):
    enabled: bool = True
    url: str = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    poll_interval_s: int = 60
    timeout_s: int = 15

class FUNVISISSource(BaseModel):
    enabled: bool = True
    url: str = "http://www.funvisis.gob.ve/maravilla.json"
    poll_interval_s: int = 60
    timeout_s: int = 15

class GEOFONSource(BaseModel):
    enabled: bool = True
    url: str = "http://geofon.gfz.de/fdsnws/event/1/query"
    poll_interval_s: int = 60
    timeout_s: int = 15

class Dedup(BaseModel):
    distance_km: float = 100.0
    window_s: int = 90
    magnitude_delta: float = 0.5

class Severity(BaseModel):
    info_max: float = 4.0
    warning_max: float = 5.5

class Notification(BaseModel):
    fullscreen: bool = False
    timezone: str = "America/Caracas"
    sound: bool = True

class LoggingCfg(BaseModel):
    level: str = "INFO"
    file: str = "vigia-eew.log"
    max_bytes: int = 1_048_576
    backups: int = 3

class Settings(BaseModel):
    reference: ReferencePoint = ReferencePoint()
    filter: Filter = Filter()
    sources_emsc: EMSCSource = EMSCSource()
    sources_usgs: USGSSource = USGSSource()
    sources_funvisis: FUNVISISSource = FUNVISISSource()
    sources_geofon: GEOFONSource = GEOFONSource()
    dedup: Dedup = Dedup()
    severity: Severity = Severity()
    notification: Notification = Notification()
    logging: LoggingCfg = LoggingCfg()
```

### 3.3 Config path resolution
1. CLI flag `--config <path>` (highest priority).
2. `config.toml` in the user's config directory (`platformdirs`).
3. Embedded *defaults* if no file exists (the agent starts up with no prior configuration).

---

## 4. Simulated event (`--simulate`) — RF-21

Injects a `SeismicEvent` with `source="SIMULATED"` to validate notification without a real
earthquake. Default values (configurable via flags):

```python
SeismicEvent(
    id="SIM-0001",
    source="SIMULATED",
    magnitude=6.1,
    mag_type="mw",
    place="near La Guaira, Venezuela",
    region="NEAR COAST OF VENEZUELA",
    lat=10.60, lon=-66.93,
    depth_km=10.0,
    time_utc="<now UTC>",
    distance_km="<calculated>",
    severity="critical",
    action="create",
)
```

## 5. Type and unit dictionary

| Concept | Unit | Notes |
|---|---|---|
| Magnitude | `mag_type` scale | dedup comparisons use absolute Δ |
| Distance | km | haversine; Earth radius 6371 km |
| Depth | km | ≥ 0 |
| Internal time | UTC tz-aware | conversion to local time only in UI |
| USGS cursor | epoch ms | same unit as `properties.time/updated` |

## 6. Traceability

`SeismicEvent` ⇄ RF-07/RF-08/RF-13 · `AppState` ⇄ RF-06/RF-10 · `Settings` ⇄ RF-24/RF-12 ·
`DetectedLocation` ⇄ RF-33 · `FUNVISISSource` ⇄ RF-38 · `GEOFONSource` ⇄ RF-39.
Per-source field mapping in `API-SPEC.md §5.1`.
