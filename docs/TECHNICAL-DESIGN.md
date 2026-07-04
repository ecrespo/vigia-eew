# Technical Design — Vigía-eew

| Campo | Valor |
|---|---|
| Documento | Diseño técnico y decisiones de arquitectura (ADRs) |
| Versión | 1.0 (borrador para revisión) |
| Estado | 🟡 Pendiente de aprobación |
| Relacionado | `PRD.md`, `API-SPEC.md`, `DATA-MODEL.md`, `ARCHITECTURE.md`, `IMPLEMENTATION-PLAN.md` |

---

## 1. Resumen

Vigía es un **único proceso asyncio** de larga vida por máquina. Una **vía primaria de push**
(WebSocket EMSC) y una **red de seguridad de bajo peso** (polling USGS cada 60 s) alimentan una
**cola interna**. Un *pipeline* normaliza → filtra → deduplica y, cuando un evento es nuevo y
relevante, lo entrega a la **capa de notificación**, que muestra una **ventana de alerta
no descartable** además de un toast nativo. El estado crítico (ids alertados, cursor USGS) se
**persiste** para sobrevivir reinicios.

Principios rectores: **push primero** (RF-01), **nunca morir** por fallos transitorios (RNF-03),
**no descartable** (RF-19/RNF-05) y **trazabilidad** RF→código (RNF-08).

## 2. Arquitectura lógica (capas)

```
Fuentes externas ──▶ Ingestión ──▶ Cola asyncio ──▶ Normalización ──▶ Filtro ──▶ Dedup ──▶ Notificación
                                                                                  │
                                                                        Persistencia (estado)
```

| Capa | Componente | Responsabilidad | RF |
|---|---|---|---|
| Ingestión | `WSIngestor` (EMSC) | Conexión WS, keepalive, reconexión, emitir crudos | RF-01..RF-04 |
| Ingestión | `RESTReconciler` (USGS) | Polling 60 s, cursor, emitir crudos | RF-05, RF-06 |
| Normalización | `Normalizer` | Crudo→evento normalizado, distancia, severidad | RF-07, RF-08, RF-13 |
| Filtro | `GeoFilter` | Radio + magnitud mínima | RF-12 |
| Dedup | `Deduplicator` | Heurística inter-fuente; updates; ids persistidos | RF-09..RF-11 |
| Notificación | `Notifier` (toast) + `AlertWindow` (overlay) + `AlertQueue` | Toast + ventana + cola + sonido | RF-14..RF-21 |
| Persistencia | `StateStore` | ids alertados + cursor en disco | RF-06, RF-10 |
| Config | `Settings` (pydantic) | Cargar/validar `config.toml` | RF-24 |
| Plataforma | `autostart/` | systemd/LaunchAgent/tarea programada | RF-22, RF-23 |
| CLI | `cli` (`vigia-eew`) | Arranque, `--simulate`, autostart | RF-21, RF-26 |

## 3. Modelo de concurrencia (asyncio) — RNF-04

Tareas `asyncio` coordinadas por un orquestador (`Supervisor`):

- **T1 `ws_task`**: mantiene el WS vivo (keepalive + reconexión), publica crudos en `raw_queue`.
- **T2 `rest_task`**: bucle de 60 s; publica crudos en `raw_queue`.
- **T3 `pipeline_task`**: consume `raw_queue` → normaliza → filtra → dedup → si procede, `alert_queue`.
- **T4 capa UI**: la GUI (Tkinter) corre en el **hilo principal**; un *bridge* thread-safe pasa
  eventos desde `alert_queue` (asyncio) a la UI (ver ADR-006).

Resiliencia: cada *task* va envuelta en un guard que captura excepciones, las registra y **reinicia
la task con backoff** sin tumbar el proceso (patrón "supervisor que reincia hijos"). Cierre limpio
con `asyncio` + señales (SIGINT/SIGTERM).

```
Supervisor
 ├─ ws_task ──────┐
 ├─ rest_task ────┼──▶ raw_queue ──▶ pipeline_task ──▶ alert_queue ──▶ UI bridge ──▶ AlertWindow
 └─ watchdog      ┘
```

## 4. Estrategia tiempo real: push-primario / polling-respaldo

- **Primario (push)**: el WS entrega eventos con latencia mínima (RF-01). Keepalive 15 s (RF-02)
  y reconexión perpetua con backoff (RF-03) garantizan continuidad.
- **Respaldo (polling)**: USGS cada 60 s (RF-05) **solo** recupera lo que el WS perdió y cubre
  pequeños locales. No compite con el push: baja frecuencia, bajo peso.
- **Por qué no polling principal**: latencia alta y carga innecesaria; el WS ya entrega push real.
- **Por qué USGS por polling y no WS**: USGS no ofrece WebSocket público simple (su push es PDL,
  pesado/Java) → polling con cursor es la opción de bajo costo (ADR-002).

## 5. Deduplicación y manejo de `update`

### 5.1 Reglas (RF-09..RF-11)
1. **Dedup intra-fuente por id**: si el `id`/`unid` ya está en `ids_alertados`, no re-alertar.
2. **`update` de EMSC**: mismo `unid` ya visto → **actualizar** el evento (p. ej. magnitud) en la
   ventana si está en pantalla/cola; **no** generar alerta nueva (RF-11).
3. **Dedup inter-fuente (heurística)**: dos eventos de fuentes distintas son el mismo sismo si
   **Δdistancia ≤ 100 km** y **Δtiempo ≤ 90 s** y **Δmagnitud ≤ 0.5** (RF-09). Se mantiene una
   ventana temporal de eventos recientes para comparar.
4. **Persistencia**: `ids_alertados` y las "firmas" recientes se guardan para no repetir tras
   reinicios (RF-10).

### 5.2 Pseudocódigo
```python
def es_duplicado(ev, recientes, ids_alertados):
    if ev.id in ids_alertados:
        return True                      # ya alertado (mismo id)
    for r in recientes:                  # heurística inter-fuente
        if (haversine(ev, r) <= 100 and
            abs(ev.hora - r.hora) <= 90 and
            abs(ev.mag - r.mag) <= 0.5):
            return True
    return False
```

## 6. Filtrado y severidad

- **Filtro** (RF-12): descartar si `distancia_km > radio` o `magnitud < magnitud_minima`.
- **Severidad** (RF-13): umbrales configurables; por defecto `<4 info`, `4–5.5 atencion`, `5.5+ critico`.
  Cada nivel define **color** y **perfil de sonido** de la alerta.

## 7. Persistencia de estado — RF-06, RF-10

- Formato: **JSON** en directorio de datos del usuario (`platformdirs`): p. ej.
  `~/.local/share/vigia-eew/state.json` (Linux), `%LOCALAPPDATA%` (Windows), `~/Library/Application Support` (macOS).
- Contenido: `cursor_usgs` (epoch ms), `ids_alertados` (con poda por antigüedad), `firmas_recientes`.
- Escritura **atómica** (escribir a temp + `os.replace`) para no corromper ante caída.
- Esquema en `DATA-MODEL.md`.

## 8. Manejo de errores y reconexión — RNF-03

| Fallo | Estrategia |
|---|---|
| WS cerrado / ping_timeout | Reconexión perpetua con **backoff exponencial + jitter** (p. ej. 1,2,4,8…≤60 s). |
| USGS 429 | Respetar `Retry-After`; saltar ciclo; mantener cursor. |
| USGS 5xx / timeout | Log de advertencia; reintento en el siguiente ciclo. |
| JSON inválido / esquema | Validar con pydantic; descartar el item; continuar. |
| Pérdida de red total | Ambas ingestas reintentan; el proceso sigue vivo; al volver la red, USGS reconcilia. |
| Excepción en una task | El `Supervisor` la captura, registra y reinicia esa task con backoff. |
| Fallo de la UI | Aislado del pipeline; la ingestión sigue; se reintenta mostrar. |

## 9. Logging y observabilidad — RNF-07

- Logging **estructurado** (clave=valor / JSON opcional) a **consola** y **archivo rotativo**
  (`logging.handlers.RotatingFileHandler`).
- Eventos registrados: conexión/desconexión WS, reconexiones y backoff, polls USGS (conteo,
  cursor), eventos filtrados, alertas mostradas y **reconocimientos** (auditoría, OBJ-1).

## 10. Seguridad y privacidad — RNF-09
- Sin claves de API; solo lectura de fuentes públicas; sin envío de datos del usuario a terceros.
- Validación estricta de entrada (pydantic) para mensajes externos.

---

## 11. Decisiones de diseño (ADRs)

> Formato corto: contexto → decisión → alternativas descartadas → consecuencias.

### ADR-001 — Push WebSocket como vía primaria (no polling)
- **Contexto**: se necesita latencia mínima (OBJ-2) y no perder eventos (OBJ-3).
- **Decisión**: WebSocket EMSC como **primario** (RF-01); polling USGS solo como **respaldo** (RF-05).
- **Alternativas descartadas**: *(a)* solo polling → latencia alta y carga; *(b)* solo WS → el WS
  documenta pérdida de mensajes; sin red de seguridad se perderían eventos.
- **Consecuencias**: doble fuente → necesidad de **dedup inter-fuente** (ADR-004).

### ADR-002 — USGS por polling con cursor (no PDL)
- **Contexto**: USGS no ofrece WS público simple; su push (PDL) es pesado/Java.
- **Decisión**: polling FDSN cada 60 s con **cursor persistido** (RF-05, RF-06).
- **Alternativas descartadas**: integrar PDL (complejidad/JVM, contra "auto-alojado y ligero").
- **Consecuencias**: ventana de hasta ~60 s para recuperar lo perdido por el WS (aceptable como respaldo).

### ADR-003 — Tkinter por defecto para la alerta (no PyQt/PySide)
- **Contexto**: alerta multiplataforma *topmost* con foco, sin dependencias pesadas (RNF-06).
- **Decisión**: **Tkinter** (incluido en CPython, cero dependencias extra). Cumple `-topmost`,
  `overrideredirect`, `attributes('-fullscreen')`, `focus_force`, `lift`.
- **Alternativas descartadas**: PyQt/PySide (mejor estética/teclado, pero +50–100 MB, licencias,
  empaquetado más complejo). Se reconsiderará **solo** si Tkinter no logra el "siempre al frente"
  fiable en algún SO. *Disparador de reevaluación*: si en macOS no se puede forzar foco de forma
  fiable, o en **GNOME/Wayland** donde el compositor restringe topmost/foco (decisión en **ADR-010**).
- **Consecuencias**: UI más austera; el sonido se maneja por capa aparte (ADR-005).

### ADR-004 — Dedup heurística por (distancia, tiempo, magnitud)
- **Contexto**: EMSC y USGS asignan ids distintos al mismo sismo.
- **Decisión**: mismo sismo si ≤100 km, ≤90 s, ≤0.5 mag (RF-09) + dedup por id intra-fuente + manejo de `update` (RF-11).
- **Alternativas descartadas**: confiar en un id común (no existe entre fuentes); *match* exacto (frágil).
- **Consecuencias**: posibles falsos positivos/negativos en enjambres; umbrales **configurables**.

### ADR-005 — Sonido desacoplado y multiplataforma
- **Contexto**: el sonido debe escalar con severidad y funcionar en 3 SO (RF-17).
- **Decisión**: capa de audio propia; estrategia por SO (reproducción de WAV empaquetado; *fallback*
  a *bell* del sistema). Selección de assets por severidad.
- **Alternativas descartadas**: depender solo del sonido del toast (silenciable por "No molestar").
- **Consecuencias**: incluir assets de audio en el paquete; ruta de assets resuelta en runtime.

### ADR-006 — Puente asyncio↔Tkinter (UI en hilo principal)
- **Contexto**: Tkinter exige hilo principal; la ingestión vive en asyncio.
- **Decisión**: ejecutar el *event loop* de Tkinter en el hilo principal y el bucle asyncio en un
  hilo de trabajo; pasar eventos con una cola thread-safe + `widget.after()` para *poll* de la cola.
- **Alternativas descartadas**: correr asyncio en el hilo principal y Tk en otro (Tk no es thread-safe).
- **Consecuencias**: un punto de integración bien acotado; cierre coordinado de ambos bucles.

### ADR-007 — Config en `config.toml` (pydantic) + gestor `uv`/hatchling
- **Contexto**: config estructurada (severidades anidadas) y *tooling* moderno.
- **Decisión**: **`config.toml`** leído con `tomllib` (stdlib 3.11+) y validado por **pydantic**
  (RF-24); proyecto gestionado con **uv**; build con **hatchling** (RF-27).
- **Alternativas descartadas**: `.env` (incómodo para estructuras anidadas); setuptools (más verboso).
- **Consecuencias**: `tomllib` es solo lectura (la escritura de config no es necesaria en v1).

### ADR-008 — Sin relay central en v1 (cada máquina, su agente)
- **Contexto**: evitar punto único de fallo (RNF-02); simplicidad de v1.
- **Decisión**: cada máquina corre su propio agente. Se **documenta** la migración a un relay
  FastAPI con *fan-out* WS reutilizando el contrato interno (API Spec §4).
- **Alternativas descartadas**: relay central en v1 (SPOF, más operación).
- **Consecuencias**: N conexiones a EMSC (aceptable); evolución no rompe el modelo de datos.

### ADR-009 — `websockets` + `httpx` (no Tornado)
- **Contexto**: el ejemplo oficial de EMSC usa Tornado; el stack objetivo es asyncio moderno.
- **Decisión**: **`websockets`** para WS (keepalive nativo `ping_interval`) y **`httpx`** async para REST.
- **Alternativas descartadas**: Tornado (framework completo innecesario), `aiohttp` (válido; `httpx` por ergonomía/timeouts).
- **Consecuencias**: dependencias mínimas y idiomáticas con asyncio.

### ADR-010 — Frontend de presentación desacoplado por D-Bus + extensión GNOME Shell opcional
- **Contexto**: la garantía central "imposible de ignorar" (OBJ-1, RF-15/16/19) depende de
  *topmost* + robo de foco + sin decoración. Bajo **Wayland** (default de GNOME hoy), una app
  X11/XWayland como **Tkinter** **no puede** forzar de forma fiable `-topmost`, `focus_force` ni
  `overrideredirect`: el compositor controla apilamiento y foco. Es el *disparador de
  reevaluación* anticipado en el ADR-003. El núcleo (ingestión/pipeline/estado) es Python y
  multiplataforma (RNF-06) y no queremos perderlo.
- **Decisión**: separar **presentación** de **núcleo**. El agente Python sigue siendo la única
  fuente de verdad (ingestión → pipeline → `SeismicEvent` normalizado) y publica las alertas por
  un **canal D-Bus** opcional; los frontends de presentación se **suscriben**.
  - Frontend **por defecto**: la ventana **Tkinter** (ADR-003), empaquetada y multiplataforma.
  - Frontend **opcional en GNOME**: una **extensión de GNOME Shell** (GJS) que escucha el canal
    D-Bus y muestra un `ModalDialog` con *grab* real de pantalla/teclado — la forma **más fiable**
    de "imposible de ignorar" en GNOME/Wayland, al vivir dentro del compositor.
  - El reconocimiento (RECONOCIDO) fluye **de vuelta** al agente por D-Bus, de modo que el estado
    y la auditoría (`reconocido_utc`, RF-10) permanecen en el núcleo Python.
  - **v1: no implementado**; se documenta como evolución. Tkinter sigue siendo el default en los 3 SO.
- **Alternativas descartadas**:
  - *Reescribir toda la app como extensión GNOME (GJS)*: pierde portabilidad (RNF-06), el núcleo
    Python y mete el agente dentro del proceso del shell (riesgo para 24/7, RNF-02/03).
  - *Forzar más el topmost de Tkinter en Wayland*: no es fiable; el compositor manda.
  - *Depender solo del toast crítico (`desktop-notifier`)*: silenciable por "No molestar" (RF-19).
- **Consecuencias**:
  - Hay que definir un **contrato D-Bus** mínimo (reutilizando el `SeismicEvent` interno, igual que
    el relay del ADR-008): el agente emite `Alerta(evento)` y el frontend invoca `Reconocer(id)`.
    El diseño detallado de este puente queda pendiente (ítem de evolución).
  - El `ControladorAlertas` gana un segundo "backend" de salida (publicar a D-Bus) junto a la
    ventana Tk; la selección es por plataforma/configuración.
  - La distribución suma un artefacto opcional (extensión vía extensions.gnome.org o empaquetada),
    independiente del paquete Python.

#### Diseño detallado del contrato D-Bus (elaboración de ADR-010 — solo diseño, no implementado)

> Profundiza la "Opción 3" pendiente del ADR-010. No cambia la decisión, la hace codificable.

**Bus y nombres** (convención D-Bus reverse-DNS, sesión de usuario — no *system bus*, no root):
- Bus: **session bus** (`DBUS_SESSION_BUS_ADDRESS`), coherente con "sin privilegios" (RNF-09).
- Nombre de servicio: `org.vigia_eew.Agente`.
- Ruta de objeto: `/org/vigia_eew/Agente`.
- Interfaz **versionada** (permite romper sin ambigüedad): `org.vigia_eew.Agente.Alertas1`.

**Superficie de la interfaz `Alertas1`**

| Miembro | Tipo | Dirección | Payload | Equivalente interno |
|---|---|---|---|---|
| señal `AlertaNueva` | `(s)` | agente → frontend(s) | `SeismicEvent` como JSON (mismo esquema de API-SPEC §3) | `ControladorAlertas._mostrar` |
| señal `AlertaActualizada` | `(s)` | agente → frontend(s) | `SeismicEvent` JSON, `accion="update"` (RF-11) | `ControladorAlertas._actualizar` |
| método `Reconocer` | `(s) -> (b)` | frontend → agente | `id` del evento | `AlertQueue.reconocer` → `ControladorAlertas._reconocido` |
| método `ObtenerActiva` | `() -> (s)` | frontend → agente | `"" ` si no hay alerta en curso, o el `SeismicEvent` JSON actual | estado interno de `ControladorAlertas` |
| método `Ping` | `() -> (s)` | frontend → agente | versión del agente (`"1.0"`) | detección de disponibilidad del agente |

Se reutiliza literalmente el **contrato interno** (`SeismicEvent`, API-SPEC §3) serializado con
`model_dump_json()`: un solo `string` como argumento evita definir una *struct* D-Bus paralela y
mantiene un único punto de verdad para el esquema (igual criterio que el relay del ADR-008).

**Encaje con `ControladorAlertas` (segundo backend de salida)**

`ControladorAlertas` hoy invoca directamente `crear_ventana` (Tk), `reproducir_sonido` y
`enviar_toast` como *callbacks* inyectables. El puente D-Bus se modela como un **cuarto callback
del mismo tipo** (`publicar_dbus: Callable[[SeismicEvent], None] | None`), llamado desde `_mostrar`
y `_actualizar` junto a los existentes — **no** reemplaza a Tk, se suma:

```
_mostrar(ev)      → crear_ventana(...) + reproducir_sonido(...) + enviar_toast(...) + publicar_dbus(ev)
_actualizar(ev)   → ventana.actualizar(...)                                          + publicar_dbus(ev)
Reconocer(id) (entrante) → self._cola.reconocer(...)   # mismo camino que "RECONOCIDO" de la ventana Tk
```

El servicio D-Bus (`org.vigia_eew.Agente`) corre en el mismo proceso asyncio del agente (librería
`dbus-fast`, ya presente como dependencia transitiva de `desktop-notifier`); `Reconocer` recibido
por D-Bus se despacha al hilo/loop correcto igual que hoy se despacha el clic "RECONOCIDO" de la
ventana Tk (mismo puente asyncio↔UI de ADR-006, no uno nuevo).

**Selección de frontend por plataforma/config (RF-22 no aplica; es config de presentación)**

- Config nueva (v1 del diseño, futura en `config.toml`): `[notificacion] frontend = "tk" | "auto"`.
  Default **`"tk"`** en los 3 SO (comportamiento actual, sin cambios).
- Con `"auto"` en Linux: el agente detecta GNOME + Wayland (`XDG_CURRENT_DESKTOP` contiene
  `"GNOME"`, `XDG_SESSION_TYPE == "wayland"`) **y** que la extensión esté activa, consultando
  `org.freedesktop.DBus.NameHasOwner` sobre un nombre bien conocido que publicaría la extensión
  (p. ej. `org.gnome.Shell.Extensions.VigiaEew`). Si ambas condiciones se cumplen, la ventana Tk
  se **omite** para esa alerta (evita dos overlays no descartables compitiendo por foco) y solo se
  emite la señal D-Bus; en cualquier otro caso (extensión ausente, otro SO, X11), Tk sigue siendo
  el único frontend, igual que hoy.
- El toast (`desktop-notifier`) y el sonido (`sound.py`) **no** se ven afectados por esta selección:
  siguen disparándose siempre, son canales redundantes independientes (RF-14, RF-17).

**Aislamiento de fallos (RNF-03 — nunca morir por esto)**

Publicar en D-Bus (o que nadie escuche) **nunca** debe impedir mostrar la ventana Tk: mismo patrón
que `toast.py` (fallo aislado, log de advertencia, la alerta sigue mostrándose). Si `"auto"`
detecta la extensión pero la señal falla al emitirse (bus caído, extensión se cerró entre la
detección y el envío), el agente debe **repetir el fallback a Tk** para esa alerta puntual, no
asumir que quedó mostrada.

**Qué falta para pasar de diseño a código** (fuera de alcance mientras no se pida explícitamente):
implementar el servicio D-Bus (`dbus-fast` `ServiceInterface`), el `publicar_dbus` callback y su
cableado en `app.py`/`config.py`, la detección `"auto"`, y — en el otro extremo, fuera del paquete
Python — la extensión GNOME Shell (GJS) que consume la señal y llama `Reconocer`.

## 12. Trazabilidad

Cada ADR y componente referencia RF del `PRD.md`. La matriz completa RF→módulo está en
`IMPLEMENTATION-PLAN.md`. Las estructuras concretas, en `DATA-MODEL.md`. Los contratos externos,
en `API-SPEC.md`. Las vistas y diagramas, en `ARCHITECTURE.md`.
