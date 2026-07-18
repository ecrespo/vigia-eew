# ARCHITECTURE — Vigía-eew

| Field | Value |
|---|---|
| Document | System architecture and diagrams |
| Version | 1.0 (draft for review) |
| Status | 🟡 Pending approval |
| Related | `docs/PRD.md`, `docs/API-SPEC.md`, `docs/TECHNICAL-DESIGN.md`, `docs/DATA-MODEL.md`, `docs/IMPLEMENTATION-PLAN.md` |

> Diagrams are in **Mermaid** (renderable text on GitHub and most Markdown viewers).

---

## 1. Overview

Vigía is a **single asyncio process per machine** with no single point of failure (RNF-02). It
receives earthquakes via **push** (WebSocket EMSC, primary channel) and reconciles them with
**three low-frequency REST backups**: USGS and GEOFON (independent global networks, each
polling every 60 s with a persisted cursor) and FUNVISIS (Venezuela-only local coverage,
60 s polling, in-memory seen-set). A *pipeline* normalizes, filters by zone, and deduplicates
them across all four sources; new and relevant events trigger an **undismissable desktop
alert** (overlay window + toast + sound). Critical state is **persisted** to survive restarts.

## 2. Components

| Component | Role | RF |
|---|---|---|
| **WSIngestor (EMSC)** | WebSocket connection, 15 s keepalive, backoff reconnection, emits raw messages | RF-01..RF-04 |
| **RESTReconciler (USGS)** | 60 s polling with persisted cursor; safety net | RF-05, RF-06 |
| **FUNVISISPoller** | 60 s polling of `maravilla.json`; Venezuela-only local coverage; in-memory seen-set (no cursor) | RF-38 |
| **GEOFONPoller** | 60 s polling of `fdsnws-event` (text format); independent global-network redundancy; persisted cursor | RF-39 |
| **Normalizer** | Raw→`SeismicEvent`; haversine; severity | RF-07, RF-08, RF-13 |
| **GeoFilter** | Discards events outside radius, below minimum magnitude, or from a previous local day (RF-40, default-on) | RF-12, RF-40 |
| **Deduplicator** | Inter-source heuristic; persisted ids; handles `update` | RF-09..RF-11 |
| **Notifier (toast)** | Native informational toast (`desktop-notifier`) | RF-14 |
| **AlertWindow (overlay)** | Topmost Tkinter window, with focus, undismissable | RF-15..RF-19 |
| **AlertQueue + bridge** | Event queue; asyncio↔Tk bridge | RF-20 |
| **Sound** | Audio by severity | RF-17 |
| **StateStore** | Atomic JSON persistence (ids, cursor) | RF-06, RF-10 |
| **Settings** | Loads/validates `config.toml` (pydantic) | RF-24 |
| **Supervisor** | Orchestrates asyncio tasks; restarts on failure | RNF-03, RNF-04 |
| **Autostart** | systemd / LaunchAgent / scheduled task | RF-22, RF-23 |
| **CLI (`vigia-eew`)** | Startup, `--simulate`, autostart | RF-21, RF-26 |

## 3. Architecture diagram — data flow

```mermaid
flowchart LR
    subgraph Fuentes["External sources"]
        EMSC["EMSC WebSocket<br/>(primary push)"]
        USGS["USGS FDSN REST<br/>(60 s backup)"]
        FUNVISIS["FUNVISIS maravilla.json<br/>(60 s, Venezuela-only)"]
        GEOFON["GEOFON fdsnws-event<br/>(60 s, text format)"]
    end

    subgraph Ingesta["Ingestion layer (asyncio)"]
        WS["WSIngestor<br/>keepalive + reconnection"]
        REST["RESTReconciler<br/>persisted cursor"]
        FUNV["FUNVISISPoller<br/>in-memory seen-set"]
        GEO["GEOFONPoller<br/>persisted cursor"]
    end

    Q(["raw_queue<br/>(asyncio.Queue)"])

    subgraph Pipeline["Pipeline"]
        NORM["Normalizer<br/>haversine + severity"]
        FILT["GeoFilter<br/>radius + min magnitude"]
        DEDUP["Deduplicator<br/>heuristic + ids"]
    end

    subgraph Estado["Persistence"]
        STATE[("StateStore<br/>state.json<br/>ids + cursor")]
    end

    subgraph Notif["Notification"]
        AQ(["AlertQueue<br/>+ Tk bridge"])
        TOAST["Notifier (toast)"]
        WIN["AlertWindow<br/>topmost · sound · ACKNOWLEDGED"]
    end

    CFG["Settings<br/>config.toml"]

    EMSC -->|create/update| WS
    USGS -->|GeoJSON| REST
    FUNVISIS -->|GeoJSON| FUNV
    GEOFON -->|text| GEO
    WS --> Q
    REST --> Q
    FUNV --> Q
    GEO --> Q
    Q --> NORM --> FILT --> DEDUP
    DEDUP -->|new + relevant| AQ
    AQ --> TOAST
    AQ --> WIN
    DEDUP <-->|alerted ids| STATE
    REST <-->|cursor| STATE
    GEO <-->|cursor| STATE
    CFG -.config.-> NORM
    CFG -.config.-> FILT
    CFG -.config.-> DEDUP
    CFG -.config.-> WIN
```

## 4. Sequence diagram — from EMSC to the alert window

```mermaid
sequenceDiagram
    autonumber
    participant EMSC as EMSC WebSocket
    participant WS as WSIngestor
    participant PIPE as Pipeline (normalize/filter/dedup)
    participant ST as StateStore
    participant UI as AlertQueue + AlertWindow
    participant USR as User

    EMSC->>WS: message {action:"create", data: Feature}
    WS->>PIPE: raw message (raw_queue)
    PIPE->>PIPE: normalizes (haversine, severity)
    PIPE->>PIPE: filters (radius, min magnitude)
    PIPE->>ST: id already alerted? duplicate?
    ST-->>PIPE: no (new event)
    PIPE->>ST: registers alerted id
    PIPE->>UI: enqueues SeismicEvent
    UI->>UI: shows topmost window + takes focus + sound
    UI-->>USR: MAGNITUDE, place, distance, depth, local time, source
    Note over EMSC,UI: If an {action:"update"} arrives for the same unid,<br/>the displayed event is updated WITHOUT a new alert (RF-11)
    USR->>UI: presses "ACKNOWLEDGED"
    UI->>ST: registers acknowledgment (audit)
    UI->>UI: closes window and shows the next one in the queue
```

## 5. State diagram — WebSocket connection

```mermaid
stateDiagram-v2
    [*] --> Connecting
    Connecting --> Connected: handshake OK
    Connecting --> Backoff: connection error

    Connected --> Ping: every ~15 s
    Ping --> Connected: pong received
    Ping --> Down: ping_timeout (no pong)

    Connected --> Receiving: incoming message
    Receiving --> Connected: processed

    Connected --> Down: socket close/EOF
    Down --> Backoff: schedule retry

    Backoff --> Connecting: exponential wait + jitter (max backoff_max_s)

    Connected --> Closing: SIGINT/SIGTERM
    Closing --> [*]
```

## 6. What happens if… (resilience scenarios)

| Scenario | Expected behavior | Mechanism / RF |
|---|---|---|
| **The WS goes down** | Close/ping_timeout is detected → `Down` state → exponential `Backoff` with jitter → perpetual reconnection. The process **does not die**. | RF-03, RNF-03; §5 |
| **The WS silently stops receiving** | The **keepalive (15 s ping)** detects the loss via `ping_timeout` and forces reconnection. | RF-02 |
| **REST fails (429/5xx/timeout)** | `Retry-After` is honored (429); the cycle is skipped and retried after 60 s; the **cursor is kept**; no abort. | RF-05; Technical Design §8 |
| **FUNVISIS or GEOFON is unreachable/changes format** | That poller's cycle is skipped and retried after 60 s (own timeout/backoff); the other three sources are unaffected; the process **does not die**. | RF-38, RF-39 |
| **An `update` arrives** | Same `unid` already seen → the displayed/queued event is **updated** (e.g. magnitude) **without** triggering a new alert. | RF-11, CU-3 |
| **Two sources report the same earthquake** | The heuristic (≤100 km, ≤90 s, ≤0.5 mag) recognizes it as a duplicate → **a single** alert. | RF-09, CU-4 |
| **The agent restarts with pending alerts** | `StateStore` remembers `alerted_ids` → already-acknowledged ones **are not re-alerted**; `usgs_cursor`/`geofon_cursor` avoid reprocessing history. | RF-06, RF-10, CU-10 |
| **A source reports an earthquake from a previous day** (stale REST backlog, replayed signature, clock skew) | `GeoFilter`'s freshness check discards it before it reaches `Deduplicator` — no alert, regardless of source. | RF-40 |
| **The agent was off for days; the persisted USGS/GEOFON cursor is stale** | The first poll after restart floors `starttime` at local midnight instead of the stale cursor's date, bounding the backlog fetched (the freshness filter above still guarantees nothing old gets alerted even without this). | RF-41 |
| **Invalid JSON / unexpected schema** | pydantic validation discards the item and logs it; the flow continues. | RNF-03 |
| **Total network loss** | Both ingestion paths keep retrying; once the network returns, USGS **reconciles** what was missed during the outage. | RF-05, OBJ-3 |
| **OS "do not disturb"** | The toast may be silenced, but the **topmost, focused overlay window** guarantees the alert. | RF-15, RF-16, RNF-05 |
| **UI fails** | Isolated from the pipeline (decoupled bridge); ingestion keeps running; showing the alert is retried. | ADR-006 |
| **The agent runs for a long time with many alerts** | `Deduplicator.register()` prunes `alerted_ids`/`recent_signatures` older than 24 h before every `save()`, so `state.json` stays bounded instead of growing forever. | RF-42 |

## 7. Deployment

Each machine runs its own agent (no SPOF). OS-specific autostart (systemd `--user`, LaunchAgent,
scheduled task) keeps the process alive after login.

```mermaid
flowchart TB
    subgraph PCs["N independent machines (no single point of failure)"]
        A["Vigía Agent<br/>(Linux · systemd --user)"]
        B["Vigía Agent<br/>(Windows · scheduled task)"]
        C["Vigía Agent<br/>(macOS · LaunchAgent)"]
    end
    EMSC["EMSC WS"] --> A & B & C
    USGS["USGS FDSN"] --> A & B & C
    FUNVISIS["FUNVISIS"] --> A & B & C
    GEOFON["GEOFON"] --> A & B & C
```

## 8. Future evolution — central relay (not v1)

ADR-008 documents the migration to a **FastAPI relay** that consumes EMSC/USGS once and does
*fan-out* over WebSocket to many Vigía clients, **reusing the internal contract** (`SeismicEvent`)
as the payload so as not to break the data model.

```mermaid
flowchart LR
    EMSC["EMSC WS"] --> RELAY["FastAPI Relay<br/>(central dedup)"]
    USGS["USGS FDSN"] --> RELAY
    RELAY -->|fan-out WS<br/>SeismicEvent| C1["Vigía client 1"]
    RELAY -->|fan-out WS| C2["Vigía client 2"]
    RELAY -->|fan-out WS| C3["Vigía client N"]
```
