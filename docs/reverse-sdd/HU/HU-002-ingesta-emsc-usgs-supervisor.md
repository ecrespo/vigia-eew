# HU-002: Ingesta de sismos en tiempo real con respaldo y auto-recuperación

> **Cluster de origen:** C-03 · **Commits:** 1 `[COMMITS: fc0ca99]`
> **Período:** 2026-06-28 · **Era:** v0.1.0

## Historia

**Como** usuario que vive en zona sísmica
**Quiero** que el agente reciba sismos con la menor latencia posible y no se pierda ninguno aunque falle la red
**Para** enterarme del temblor antes de sentirlo, y no quedarme sin aviso por una caída de conexión

## Contexto de la implementación original

1.011 líneas que crean el canal push, el de respaldo y el supervisor que los mantiene vivos.
`WSIngestor` `[VERIFY: src/vigia_eew/ingest/ws_emsc.py:37]` mantiene el WebSocket de EMSC con
keepalive y reconexión; `RESTReconciler` `[VERIFY: src/vigia_eew/ingest/rest_usgs.py:42]` consulta
USGS cada 60 s con cursor persistido; `Supervisor` `[VERIFY: src/vigia_eew/supervisor.py:27]`
reinicia cada tarea de forma aislada. El backoff es un helper puro compartido
`[VERIFY: src/vigia_eew/backoff.py:18]`.

## Criterios de aceptación

### CA-002.1: Los mensajes válidos de EMSC llegan a la cola
```gherkin
Dado un WebSocket de EMSC entregando un mensaje de sismo válido
Cuando el ingestor lo recibe
Entonces se encola un RawMessage con la fuente EMSC
Y un mensaje JSON inválido o sin datos se descarta sin romper el ingestor
```
*Fuente: tests `[VERIFY: tests/test_ws_emsc.py:132]`, `[VERIFY: tests/test_ws_emsc.py:119]`, `[VERIFY: tests/test_ws_emsc.py:124]`*

### CA-002.2: La caída del WebSocket se recupera con backoff creciente
```gherkin
Dado un WebSocket que se cierra inesperadamente
Cuando el ingestor detecta la caída
Entonces reconecta automáticamente
Y la espera entre reintentos crece de forma exponencial acotada al tope
```
*Fuente: tests `[VERIFY: tests/test_ws_emsc.py:159]`, `[VERIFY: tests/test_ws_emsc.py:178]`, `[VERIFY: tests/test_backoff.py:18]`*

### CA-002.3: USGS reconcilia sin competir con el push
```gherkin
Dado un cursor USGS persistido
Cuando se ejecuta un ciclo de sondeo
Entonces se emite un RawMessage por cada feature devuelta
Y el cursor solo avanza después de procesar la respuesta
Y una respuesta vacía no mueve el cursor
```
*Fuente: tests `[VERIFY: tests/test_rest_usgs.py:171]`, `[VERIFY: tests/test_rest_usgs.py:182]`, `[VERIFY: tests/test_rest_usgs.py:193]`*

### CA-002.4: Los errores de red nunca detienen la ingesta
```gherkin
Dado un endpoint REST que responde 429, 5xx, timeout o JSON inválido
Cuando el poller ejecuta su ciclo
Entonces registra el problema y continúa en el siguiente ciclo
Y ante un 429 respeta la cabecera Retry-After
```
*Fuente: tests `[VERIFY: tests/test_rest_usgs.py:203]`, `[VERIFY: tests/test_rest_usgs.py:212]`, `[VERIFY: tests/test_rest_usgs.py:220]`, `[VERIFY: tests/test_rest_usgs.py:228]`*

### CA-002.5: Una tarea que falla se reinicia sin arrastrar a las demás
```gherkin
Dada una tarea supervisada que lanza una excepción
Cuando el supervisor la detecta
Entonces la reinicia tras un backoff
Y el resto de tareas sigue ejecutándose sin interrupción
Y el proceso no termina
```
*Fuente: tests `[VERIFY: tests/test_supervisor.py:30]`, `[VERIFY: tests/test_supervisor.py:53]`; e2e `[VERIFY: tests/test_resilience.py:186]`*

### CA-002.6: La parada es limpia
```gherkin
Dada una petición de parada del supervisor
Cuando se procesa
Entonces todas las tareas vivas se cancelan y el proceso termina sin tareas huérfanas
```
*Fuente: test `[VERIFY: tests/test_supervisor.py:81]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-002.1 | CA-002.1 | feliz | mensaje EMSC válido | JSON con `data` | RawMessage encolado | `[VERIFY: tests/test_ws_emsc.py:132]` |
| TC-002.2 | CA-002.1 | borde | payload en bytes | bytes UTF-8 | parseado igual | `[VERIFY: tests/test_ws_emsc.py:113]` |
| TC-002.3 | CA-002.1 | negativo | JSON inválido | `"{"` | None, sin excepción | `[VERIFY: tests/test_ws_emsc.py:119]` |
| TC-002.4 | CA-002.2 | feliz | caída y reconexión | cierre del socket | reconecta | `[VERIFY: tests/test_ws_emsc.py:159]` |
| TC-002.5 | CA-002.2 | borde | muchos reintentos | 10 fallos | espera saturada al tope | `[VERIFY: tests/test_backoff.py:18]` |
| TC-002.6 | CA-002.3 | feliz | 3 features | GeoJSON | 3 RawMessage | `[VERIFY: tests/test_rest_usgs.py:171]` |
| TC-002.7 | CA-002.3 | borde | respuesta vacía | `features: []` | cursor sin mover | `[VERIFY: tests/test_rest_usgs.py:193]` |
| TC-002.8 | CA-002.4 | negativo | HTTP 429 | `Retry-After: 30` | espera 30 s | `[VERIFY: tests/test_rest_usgs.py:203]` |
| TC-002.9 | CA-002.5 | negativo | tarea que revienta | excepción | reinicio con backoff | `[VERIFY: tests/test_supervisor.py:30]` |
| TC-002.10 | CA-002.5 | borde | 1 de 3 tareas falla | mixto | las otras 2 siguen | `[VERIFY: tests/test_supervisor.py:53]` |
| TC-002.11 | CA-002.6 | feliz | stop solicitado | señal | cancelación limpia | `[VERIFY: tests/test_supervisor.py:81]` |

## Dependencias

- **Requiere**: HU-001 (contrato, estado, config)
- **Habilita**: HU-003, HU-014, HU-015, HU-016

## Notas para la v2

`RESTReconciler` y `GEOFONPoller` (HU-015) resolvieron el mismo problema FDSN con dos parsers. Si
la v2 contempla una quinta fuente de esa familia, conviene una abstracción común parametrizada por
formato; con solo dos, la indirección no se paga.
