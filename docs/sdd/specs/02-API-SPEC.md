# API Spec — Vigía-eew v2

> Versión 1.0 · 2026-09-06 · Complementa, **no reemplaza**, `docs/API-SPEC.md`.

## 1. Qué contiene y qué no

Los contratos con EMSC, USGS, GEOFON y FUNVISIS **no cambian en la v2** y están especificados campo
a campo en [`docs/API-SPEC.md`](../../API-SPEC.md) §§2-5, con sus ejemplos de payload y su mapeo al
contrato interno. Repetirlos aquí crearía dos fuentes de verdad para el mismo contrato externo.

Este documento cubre **solo lo que la v2 añade o cambia**:

| § | Contrato | Estado |
|---|---|---|
| 2 | Interno `SeismicEvent` — campo de correlación | **cambio** (REQ-OBS-002) |
| 3 | Registro de fuentes `SourceSpec` | **nuevo** (REQ-ING-009) |
| 4 | Servicio de presentación D-Bus | **nuevo** (REQ-ALE-004) |
| 5 | Invariantes de transporte | **reforzado** (REQ-ING-008) |
| 6 | Contrato de hilos | **nuevo** (REQ-OPS-003) |

## 2. Contrato interno — extensión de correlación

`SeismicEvent` gana **un** campo. Todo lo demás se mantiene según `docs/API-SPEC.md` §3.

| Campo | Tipo | Obligatorio | Origen | Descripción |
|---|---|---|---|---|
| `correlation_id` | `str` (26 chars, ULID) | sí | generado en la ingesta | Identifica **el sismo**, no el mensaje: se conserva a través de la deduplicación entre fuentes |

**Reglas de propagación** (REQ-OBS-002):

1. CUANDO un ingestor emita un mensaje crudo, DEBERÁ asignarle un `correlation_id` nuevo.
2. CUANDO la deduplicación clasifique un evento como duplicado o actualización de otro ya alertado,
   el evento resultante DEBERÁ **heredar** el `correlation_id` del primero — no el suyo propio.
3. Toda entrada de registro de las cinco etapas (ingesta, normalización, filtro, dedup,
   presentación) DEBERÁ incluir `corr=<correlation_id>`.

*Consecuencia observable:* `grep 'corr=01J…' vigia-eew.log` devuelve el recorrido completo de un
sismo, incluidas las llegadas por fuentes distintas que se fusionaron.

**Formato:** ULID (26 caracteres, Crockford base32, ordenable por tiempo). Se elige sobre UUIDv4
porque el orden lexicográfico coincide con el temporal, lo que hace legible el log sin ordenar.

## 3. Registro de fuentes — `SourceSpec`

Contrato interno que hace declarativa la incorporación de fuentes (REQ-ING-009).

| Campo | Tipo | Descripción |
|---|---|---|
| `name` | `Source` (literal) | Identificador de la fuente en el contrato interno |
| `config_model` | `type[BaseModel]` | Clase de configuración de la fuente |
| `config_key` | `str` | Sección de `config.toml` que la configura |
| `build` | `Callable[..., Ingestor]` | Fábrica del ingestor, con sus dependencias inyectadas |
| `map_payload` | `Callable[[RawMessage], dict]` | Mapeo del payload crudo a los campos del contrato interno |
| `cursor_field` | `str \| None` | Campo del estado persistido, o `None` si la fuente no usa cursor |

**Invariantes:**

- EL SISTEMA DEBERÁ registrar exactamente una entrada por valor del literal `Source`, excluido
  `SIMULATED`.
- Añadir una fuente DEBERÁ tocar exactamente tres puntos: el módulo ingestor, su función de mapeo y
  su entrada en el registro. **Ni el ensamblador ni el normalizador se modifican.**
- Ningún módulo ingestor puede importar a otro (REQ-ING-010, verificado por import-linter).

## 4. Servicio de presentación D-Bus

Contrato para REQ-ALE-004. El diseño detallado está en el ADR-010 de
[`docs/TECHNICAL-DESIGN.md`](../../TECHNICAL-DESIGN.md) §11, redactado y **nunca implementado**;
aquí se fija su superficie como contrato verificable.

**Nombre de bus:** `ve.vigia.Eew1` · **Ruta:** `/ve/vigia/Eew1/Alert` ·
**Interfaz:** `ve.vigia.Eew1.Alert`

### Métodos

| Método | Firma | Semántica |
|---|---|---|
| `Present` | `(a{sv} alert) → (s handle)` | Presenta una alerta no descartable. Devuelve un manejador para actualizarla o cerrarla. Idempotente por `alert['id']`: una segunda llamada con el mismo id **actualiza** en vez de crear |
| `Update` | `(s handle, a{sv} alert) → ()` | Refresca la alerta en pantalla (REQ-ALE-006) |
| `Dismiss` | `(s handle) → ()` | Solo para uso interno del agente al terminar; **no** expone una vía de cierre al usuario que no sea el acuse |

### Señales

| Señal | Firma | Cuándo |
|---|---|---|
| `Acknowledged` | `(s handle)` | El usuario acusó explícitamente la alerta |

### Diccionario `alert`

`id` (s), `magnitude` (d), `place` (s), `distance_km` (d), `depth_km` (d), `time_local` (s),
`severity` (s: `info`\|`warning`\|`critical`), `correlation_id` (s).

### Caminos no felices (REQ-ALE-003, Art. 3)

| Condición | Comportamiento exigido |
|---|---|
| SI el servicio no está registrado en el bus | ENTONCES el agente DEBERÁ caer al frontend Tkinter y registrar un aviso nombrando la degradación |
| SI `Present` no responde en 2 s | ENTONCES el agente DEBERÁ caer al frontend Tkinter para esa alerta |
| SI el bus de sesión no está disponible | ENTONCES el agente DEBERÁ arrancar igualmente, sin este frontend |

**Ninguna de estas condiciones puede suprimir la alerta** — solo cambiar el medio por el que se
presenta.

## 5. Invariantes de transporte

| Endpoint | Esquema exigido | Excepción |
|---|---|---|
| EMSC WebSocket | `wss://` | — |
| USGS FDSN | `https://` | — |
| GEOFON FDSN | `https://` | — |
| Geolocalización por IP | `https://` | — |
| FUNVISIS `maravilla.json` | `http://` | **Excepción documentada** (PRD §11): el servicio no ofrece HTTPS válido; dato público, de solo lectura, sin credenciales ni datos de usuario |

**Criterio verificable (REQ-ING-008):** un test DEBERÁ afirmar el esquema de cada endpoint por
defecto. La excepción de FUNVISIS se declara en ese mismo test, de modo que retirarla o ampliarla
exija tocar la aserción.

## 6. Contrato de hilos

Superficie interna que la v2 hace explícita (REQ-OPS-003, Art. 6). Aplica solo al frontend gráfico;
el modo terminal corre sobre un único bucle de eventos y no tiene fronteras de hilo.

| Dato | Hilo propietario | Lectores | Mecanismo de cruce |
|---|---|---|---|
| Cola de alertas | Tk (principal) | Tk | Ninguno — nunca sale de su hilo |
| Eventos desde ingesta | asyncio | Tk | Cola thread-safe drenada en el tick de Tk |
| Bucle de eventos y supervisor | asyncio (escritura) | Tk (lectura en apagado y toast) | **Lock + evento de "runtime listo"** |
| Estado del agente (conexión, última alerta) | compartido | asyncio, Tk, bandeja | Lock (ya existente) |
| Callbacks del menú de bandeja | bandeja | — | Reprogramados al hilo de Tk cuando puedan tocar la UI |

**Invariante:** ningún campo mutable nuevo puede cruzar una frontera de hilo sin aparecer en esta
tabla. El Analyze verifica que la tabla y el código coincidan.
