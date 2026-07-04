# ARCHITECTURE — Vigía-eew

| Campo | Valor |
|---|---|
| Documento | Arquitectura del sistema y diagramas |
| Versión | 1.0 (borrador para revisión) |
| Estado | 🟡 Pendiente de aprobación |
| Relacionado | `docs/PRD.md`, `docs/API-SPEC.md`, `docs/TECHNICAL-DESIGN.md`, `docs/DATA-MODEL.md`, `docs/IMPLEMENTATION-PLAN.md` |

> Los diagramas están en **Mermaid** (texto renderizable en GitHub y la mayoría de visores Markdown).

---

## 1. Visión general

Vigía es un **proceso asyncio único por máquina** sin punto único de fallo (RNF-02). Recibe sismos
por **push** (WebSocket EMSC, vía primaria) y los reconcilia con un **respaldo de baja frecuencia**
(polling USGS cada 60 s). Un *pipeline* los normaliza, filtra por zona y deduplica; los eventos
nuevos y relevantes disparan una **alerta de escritorio no descartable** (ventana superpuesta +
toast + sonido). El estado crítico se **persiste** para sobrevivir reinicios.

## 2. Componentes

| Componente | Rol | RF |
|---|---|---|
| **WSIngestor (EMSC)** | Conexión WebSocket, keepalive 15 s, reconexión con backoff, emite crudos | RF-01..RF-04 |
| **RESTReconciler (USGS)** | Polling 60 s con cursor persistido; red de seguridad | RF-05, RF-06 |
| **Normalizer** | Crudo→`SeismicEvent`; haversine; severidad | RF-07, RF-08, RF-13 |
| **GeoFilter** | Descarta fuera de radio o bajo magnitud mínima | RF-12 |
| **Deduplicator** | Heurística inter-fuente; ids persistidos; maneja `update` | RF-09..RF-11 |
| **Notifier (toast)** | Toast nativo informativo (`desktop-notifier`) | RF-14 |
| **AlertWindow (overlay)** | Ventana Tkinter topmost, con foco, no descartable | RF-15..RF-19 |
| **AlertQueue + bridge** | Cola de eventos; puente asyncio↔Tk | RF-20 |
| **Sound** | Audio por severidad | RF-17 |
| **StateStore** | Persistencia JSON atómica (ids, cursor) | RF-06, RF-10 |
| **Settings** | Carga/valida `config.toml` (pydantic) | RF-24 |
| **Supervisor** | Orquesta tasks asyncio; reinicia ante fallo | RNF-03, RNF-04 |
| **Autostart** | systemd / LaunchAgent / tarea programada | RF-22, RF-23 |
| **CLI (`vigia-eew`)** | Arranque, `--simulate`, autostart | RF-21, RF-26 |

## 3. Diagrama de arquitectura — flujo de datos

```mermaid
flowchart LR
    subgraph Fuentes["Fuentes externas"]
        EMSC["EMSC WebSocket<br/>(push primario)"]
        USGS["USGS FDSN REST<br/>(respaldo 60 s)"]
    end

    subgraph Ingesta["Capa de ingestión (asyncio)"]
        WS["WSIngestor<br/>keepalive + reconexión"]
        REST["RESTReconciler<br/>cursor persistido"]
    end

    Q(["raw_queue<br/>(asyncio.Queue)"])

    subgraph Pipeline["Pipeline"]
        NORM["Normalizer<br/>haversine + severidad"]
        FILT["GeoFilter<br/>radio + mag mínima"]
        DEDUP["Deduplicator<br/>heurística + ids"]
    end

    subgraph Estado["Persistencia"]
        STATE[("StateStore<br/>state.json<br/>ids + cursor")]
    end

    subgraph Notif["Notificación"]
        AQ(["AlertQueue<br/>+ bridge Tk"])
        TOAST["Notifier (toast)"]
        WIN["AlertWindow<br/>topmost · sonido · RECONOCIDO"]
    end

    CFG["Settings<br/>config.toml"]

    EMSC -->|create/update| WS
    USGS -->|GeoJSON| REST
    WS --> Q
    REST --> Q
    Q --> NORM --> FILT --> DEDUP
    DEDUP -->|nuevo + relevante| AQ
    AQ --> TOAST
    AQ --> WIN
    DEDUP <-->|ids alertados| STATE
    REST <-->|cursor| STATE
    CFG -.config.-> NORM
    CFG -.config.-> FILT
    CFG -.config.-> DEDUP
    CFG -.config.-> WIN
```

## 4. Diagrama de secuencia — de EMSC a la ventana de alerta

```mermaid
sequenceDiagram
    autonumber
    participant EMSC as EMSC WebSocket
    participant WS as WSIngestor
    participant PIPE as Pipeline (norm/filtro/dedup)
    participant ST as StateStore
    participant UI as AlertQueue + AlertWindow
    participant USR as Usuario

    EMSC->>WS: mensaje {action:"create", data: Feature}
    WS->>PIPE: crudo (raw_queue)
    PIPE->>PIPE: normaliza (haversine, severidad)
    PIPE->>PIPE: filtra (radio, mag mínima)
    PIPE->>ST: ¿id ya alertado? ¿duplicado?
    ST-->>PIPE: no (evento nuevo)
    PIPE->>ST: registra id alertado
    PIPE->>UI: encola SeismicEvent
    UI->>UI: muestra ventana topmost + toma foco + sonido
    UI-->>USR: MAGNITUD, lugar, distancia, profundidad, hora local, fuente
    Note over EMSC,UI: Si llega {action:"update"} del mismo unid,<br/>se actualiza el evento mostrado SIN nueva alerta (RF-11)
    USR->>UI: pulsa "RECONOCIDO"
    UI->>ST: registra reconocimiento (auditoría)
    UI->>UI: cierra ventana y muestra el siguiente en cola
```

## 5. Diagrama de estados — conexión WebSocket

```mermaid
stateDiagram-v2
    [*] --> Conectando
    Conectando --> Conectado: handshake OK
    Conectando --> Backoff: error de conexión

    Conectado --> Ping: cada ~15 s
    Ping --> Conectado: pong recibido
    Ping --> Caido: ping_timeout (sin pong)

    Conectado --> Recibiendo: mensaje entrante
    Recibiendo --> Conectado: procesado

    Conectado --> Caido: cierre/EOF del socket
    Caido --> Backoff: programar reintento

    Backoff --> Conectando: espera exponencial + jitter (máx backoff_max_s)

    Conectado --> Cerrando: SIGINT/SIGTERM
    Cerrando --> [*]
```

## 6. Qué pasa si… (escenarios de resiliencia)

| Escenario | Comportamiento esperado | Mecanismo / RF |
|---|---|---|
| **El WS cae** | Se detecta cierre/ping_timeout → estado `Caido` → `Backoff` exponencial con jitter → reconexión perpetua. El proceso **no muere**. | RF-03, RNF-03; §5 |
| **El WS deja de recibir en silencio** | El **keepalive (ping 15 s)** detecta la pérdida vía `ping_timeout` y fuerza reconexión. | RF-02 |
| **REST falla (429/5xx/timeout)** | Se respeta `Retry-After` (429); se salta el ciclo y se reintenta a los 60 s; el **cursor se mantiene**; sin abortar. | RF-05; Technical Design §8 |
| **Llega un `update`** | Mismo `unid` ya visto → se **actualiza** el evento mostrado/encolado (p. ej. magnitud) **sin** disparar alerta nueva. | RF-11, CU-3 |
| **Dos fuentes reportan el mismo sismo** | La heurística (≤100 km, ≤90 s, ≤0.5 mag) lo reconoce como duplicado → **una sola** alerta. | RF-09, CU-4 |
| **El agente reinicia con alertas pendientes** | `StateStore` recuerda `ids_alertados` → los ya reconocidos **no se vuelven a alertar**; el `cursor_usgs` evita reprocesar histórico. | RF-06, RF-10, CU-10 |
| **JSON inválido / esquema inesperado** | Validación pydantic descarta el item y registra; el flujo continúa. | RNF-03 |
| **Pérdida total de red** | Ambas ingestas reintentan; al volver la red, USGS **reconcilia** lo perdido durante la caída. | RF-05, OBJ-3 |
| **"No molestar" del SO** | El toast puede silenciarse, pero la **ventana superpuesta topmost con foco** garantiza la alerta. | RF-15, RF-16, RNF-05 |
| **Falla la UI** | Aislada del pipeline (puente desacoplado); la ingestión sigue; se reintenta mostrar. | ADR-006 |

## 7. Despliegue

Cada máquina ejecuta su propio agente (sin SPOF). El autoarranque por SO (systemd `--user`,
LaunchAgent, tarea programada) mantiene el proceso vivo tras el inicio de sesión.

```mermaid
flowchart TB
    subgraph PCs["N máquinas independientes (sin punto único de fallo)"]
        A["Agente Vigía<br/>(Linux · systemd --user)"]
        B["Agente Vigía<br/>(Windows · tarea programada)"]
        C["Agente Vigía<br/>(macOS · LaunchAgent)"]
    end
    EMSC["EMSC WS"] --> A & B & C
    USGS["USGS FDSN"] --> A & B & C
```

## 8. Evolución futura — relay central (no v1)

Se documenta (ADR-008) la migración a un **relay FastAPI** que consuma EMSC/USGS una sola vez y haga
*fan-out* por WebSocket a muchos clientes Vigía, **reutilizando el contrato interno** (`SeismicEvent`)
como payload para no romper el modelo de datos.

```mermaid
flowchart LR
    EMSC["EMSC WS"] --> RELAY["Relay FastAPI<br/>(dedup central)"]
    USGS["USGS FDSN"] --> RELAY
    RELAY -->|fan-out WS<br/>SeismicEvent| C1["Vigía cliente 1"]
    RELAY -->|fan-out WS| C2["Vigía cliente 2"]
    RELAY -->|fan-out WS| C3["Vigía cliente N"]
```
