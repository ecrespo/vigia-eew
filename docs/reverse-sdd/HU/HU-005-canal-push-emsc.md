# HU-005: Canal push EMSC en tiempo real

> **Cluster de origen:** Fase 2 · **Commits:** 1 `[COMMITS: fc0ca99]`
> **Período:** 2026-06-28 · **Era:** Era 0 — Fundación

## Historia

**Como** usuario en zona sísmica `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** enterarme del sismo con la menor latencia posible
**Para** disponer de los segundos que separan el aviso del movimiento

## Contexto de la implementación original

`WSIngestor` `[VERIFY: src/vigia_eew/ingest/ws_emsc.py:37]` mantiene la conexión al
WebSocket de EMSC con keepalive de 15 s y **trata la desconexión como operación normal**:
`run()` es un bucle perpetuo que solo sale por cancelación
`[VERIFY: src/vigia_eew/ingest/ws_emsc.py:75]`, reconectando con backoff exponencial y
jitter `[VERIFY: src/vigia_eew/backoff.py:18]`.

El jitter no es decorativo: sin él, todas las instancias del agente reconectarían en
lockstep tras una caída compartida y estamparían el endpoint.

`connect` y `sleep` se inyectan `[VERIFY: src/vigia_eew/ingest/ws_emsc.py:40]`, que es lo
que permite testear la reconexión sin red ni esperas reales.

## Criterios de aceptación

### CA-005.1: Un mensaje válido se convierte en RawMessage
```gherkin
Dado un mensaje JSON de EMSC con action y data
Cuando el ingestor lo parsea
Entonces produce un RawMessage con la fuente EMSC
```
*Fuente: test `[VERIFY: tests/test_ws_emsc.py:96]`*

### CA-005.2: Se preserva la acción `update`
```gherkin
Dado un mensaje EMSC con action="update"
Cuando se parsea
Entonces la acción se conserva para que el pipeline la distinga de un create
```
*Fuente: test `[VERIFY: tests/test_ws_emsc.py:105]` — habilita CA-010.3*

### CA-005.3: Se aceptan payloads en bytes
```gherkin
Dado un mensaje entregado como bytes en vez de str
Cuando se parsea
Entonces se procesa igual
```
*Fuente: test `[VERIFY: tests/test_ws_emsc.py:113]`*

### CA-005.4: Un mensaje inválido se descarta sin romper la conexión
```gherkin
Dado un mensaje con JSON inválido o sin campo data
Cuando se parsea
Entonces devuelve None y el bucle continúa
```
*Fuente: tests `[VERIFY: tests/test_ws_emsc.py:119]`, `[VERIFY: tests/test_ws_emsc.py:124]`*

### CA-005.5: Los eventos recibidos se encolan
```gherkin
Dado un WebSocket que entrega un mensaje válido
Cuando corre el ingestor
Entonces el RawMessage aparece en la cola compartida
```
*Fuente: test `[VERIFY: tests/test_ws_emsc.py:132]`*

### CA-005.6: El keepalive se pasa a la conexión
```gherkin
Dado el intervalo de keepalive configurado
Cuando se establece la conexión
Entonces se propaga como ping_interval al cliente WebSocket
```
*Fuente: test `[VERIFY: tests/test_ws_emsc.py:145]` — sin keepalive, una conexión muerta
parece viva indefinidamente*

### CA-005.7: Tras una caída, reconecta y sigue entregando
```gherkin
Dado que la conexión se cae
Cuando el bucle reintenta
Entonces se restablece y los mensajes siguientes se entregan
```
*Fuente: tests `[VERIFY: tests/test_ws_emsc.py:159]` y end-to-end con supervisor real
`[VERIFY: tests/test_resilience.py:186]`*

### CA-005.8: La espera entre reintentos crece
```gherkin
Dado varios fallos de conexión consecutivos
Cuando se calculan las esperas
Entonces crecen exponencialmente hasta un tope
```
*Fuente: tests `[VERIFY: tests/test_ws_emsc.py:178]`, `[VERIFY: tests/test_backoff.py:18]`*

### CA-005.9: El estado de conexión se refleja para la bandeja
```gherkin
Dado que la conexión se establece o se cae
Cuando cambia el estado
Entonces AgentState pasa a conectado o reconectando
```
*Fuente: tests `[VERIFY: tests/test_ws_emsc.py:193]`, `[VERIFY: tests/test_ws_emsc.py:209]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-005.1 | CA-005.1 | feliz | Mensaje válido | JSON EMSC | RawMessage | `[VERIFY: tests/test_ws_emsc.py:96]` |
| TC-005.2 | CA-005.2 | feliz | action=update | JSON update | Acción preservada | `[VERIFY: tests/test_ws_emsc.py:105]` |
| TC-005.3 | CA-005.3 | borde | Payload bytes | `b'{...}'` | Procesado | `[VERIFY: tests/test_ws_emsc.py:113]` |
| TC-005.4 | CA-005.4 | negativo | JSON inválido | `"{{"` | None, sigue vivo | `[VERIFY: tests/test_ws_emsc.py:119]` |
| TC-005.5 | CA-005.4 | negativo | Sin `data` | `{"action":"create"}` | None | `[VERIFY: tests/test_ws_emsc.py:124]` |
| TC-005.6 | CA-005.5 | feliz | Encolado | mensaje válido | En raw_queue | `[VERIFY: tests/test_ws_emsc.py:132]` |
| TC-005.7 | CA-005.6 | feliz | Keepalive | 15 s | ping_interval=15 | `[VERIFY: tests/test_ws_emsc.py:145]` |
| TC-005.8 | CA-005.7 | borde | Caída y reconexión | drop | Reentrega | `[VERIFY: tests/test_ws_emsc.py:159]` |
| TC-005.9 | CA-005.8 | borde | Backoff creciente | 3 fallos | Esperas crecientes | `[VERIFY: tests/test_ws_emsc.py:178]` |
| TC-005.10 | CA-005.9 | feliz | Estado conectado | conexión ok | AgentState conectado | `[VERIFY: tests/test_ws_emsc.py:193]` |
| TC-005.11 | CA-005.7 | negativo | Caída permanente del endpoint | fallo infinito | Reintenta sin morir ni saturar | `[VERIFY: tests/test_resilience.py:186]` |

## Dependencias

- **Requiere**: HU-001, HU-003
- **Habilita**: HU-008, HU-010, HU-017 (estado de la bandeja)

## Notas para la v2

Preservar la inyección de `connect`/`sleep`: es lo que hace que 11 tests cubran
reconexión y backoff sin red ni esperas. EMSC documenta pérdida de mensajes, así que este
canal **nunca** debe ser la única fuente — ver HU-006 y HU-022.
