# HU-006: Reconciliación USGS con cursor persistido

> **Cluster de origen:** Fase 2 · **Commits:** 1 `[COMMITS: fc0ca99]`
> **Período:** 2026-06-28 · **Era:** Era 0 — Fundación

## Historia

**Como** usuario que confía en el agente como herramienta de seguridad `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** que un mensaje perdido por el WebSocket no signifique un sismo no avisado
**Para** que la promesa de "cero eventos perdidos" no dependa de un canal que documenta pérdidas

## Contexto de la implementación original

`RESTReconciler` `[VERIFY: src/vigia_eew/ingest/rest_usgs.py:42]` consulta el endpoint
FDSN de USGS cada 60 s con un **cursor persistido**, de modo que cada poll solo pide lo
posterior al anterior `[VERIFY: src/vigia_eew/ingest/rest_usgs.py:70]`. Es respaldo, no
competencia: baja frecuencia, carga liviana.

USGS no ofrece WebSocket público; su mecanismo push (PDL) es un componente JVM pesado que
contradiría la premisa de "un proceso liviano autohospedado". El costo aceptado es una
ventana de recuperación de hasta ~60 s.

El cliente HTTP y el `sleep` se inyectan `[VERIFY: src/vigia_eew/ingest/rest_usgs.py:45]`.

## Criterios de aceptación

### CA-006.1: La consulta lleva los parámetros FDSN fijos
```gherkin
Dado un ciclo de poll
Cuando se construyen los parámetros de consulta
Entonces incluyen formato, orden y límites esperados por el contrato FDSN
```
*Fuente: test `[VERIFY: tests/test_rest_usgs.py:93]`*

### CA-006.2: Cada Feature se emite como un RawMessage
```gherkin
Dado una respuesta GeoJSON con N features
Cuando se procesa
Entonces se encolan N RawMessage con fuente USGS
```
*Fuente: test `[VERIFY: tests/test_rest_usgs.py:171]`*

### CA-006.3: El cursor avanza y se persiste
```gherkin
Dado una respuesta con eventos más recientes que el cursor
Cuando termina el poll
Entonces el cursor avanza al máximo tiempo visto y se guarda
```
*Fuente: test `[VERIFY: tests/test_rest_usgs.py:182]`*

### CA-006.4: Una respuesta vacía no mueve el cursor
```gherkin
Dado una respuesta sin features
Cuando termina el poll
Entonces el cursor conserva su valor anterior
```
*Fuente: test `[VERIFY: tests/test_rest_usgs.py:193]`*

### CA-006.5: Un 429 respeta `Retry-After` y conserva el cursor
```gherkin
Dado que USGS responde 429 con cabecera Retry-After
Cuando se procesa la respuesta
Entonces se espera lo indicado y el cursor no se altera
```
*Fuente: test `[VERIFY: tests/test_rest_usgs.py:203]` — perder el cursor ante un rate
limit provocaría re-consultar historia ya vista en el ciclo siguiente*

### CA-006.6: Errores 5xx, timeouts y JSON inválido no rompen el bucle
```gherkin
Dado un fallo de servidor, un timeout o un cuerpo no parseable
Cuando ocurre durante un poll
Entonces se registra y el siguiente ciclo se ejecuta normalmente
```
*Fuente: tests `[VERIFY: tests/test_rest_usgs.py:212]`,
`[VERIFY: tests/test_rest_usgs.py:220]`, `[VERIFY: tests/test_rest_usgs.py:228]`*

### CA-006.7: Sin cursor, la consulta se acota al día local
```gherkin
Dado una instalación nueva sin cursor
Cuando se construyen los parámetros
Entonces starttime se fija en la medianoche local, no en el origen de los tiempos
```
*Fuente: tests `[VERIFY: tests/test_rest_usgs.py:111]`,
`[VERIFY: tests/test_rest_usgs.py:135]` (cursor rancio) — evita traer días de backlog
tras una instalación nueva o una salida prolongada*

### CA-006.8: Un cursor fresco se respeta sin modificar
```gherkin
Dado un cursor del día en curso
Cuando se construyen los parámetros
Entonces se usa tal cual, sin aplicar el piso
```
*Fuente: test `[VERIFY: tests/test_rest_usgs.py:121]`*

### CA-006.9: Una zona horaria inválida degrada sin romper
```gherkin
Dado un timezone inválido en configuración
Cuando se calcula el piso de la consulta
Entonces se usa el cursor crudo, o se omite starttime si no hay cursor
```
*Fuente: tests `[VERIFY: tests/test_rest_usgs.py:149]`,
`[VERIFY: tests/test_rest_usgs.py:160]`*

### CA-006.10: El bucle poll-espera es perpetuo
```gherkin
Dado el ingestor corriendo
Cuando termina un poll
Entonces espera el intervalo configurado y vuelve a consultar, hasta ser cancelado
```
*Fuente: test `[VERIFY: tests/test_rest_usgs.py:249]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-006.1 | CA-006.1 | feliz | Parámetros fijos | — | Contrato FDSN | `[VERIFY: tests/test_rest_usgs.py:93]` |
| TC-006.2 | CA-006.2 | feliz | 3 features | GeoJSON | 3 RawMessage | `[VERIFY: tests/test_rest_usgs.py:171]` |
| TC-006.3 | CA-006.3 | feliz | Eventos nuevos | t>cursor | Cursor avanza | `[VERIFY: tests/test_rest_usgs.py:182]` |
| TC-006.4 | CA-006.4 | borde | Sin features | `[]` | Cursor intacto | `[VERIFY: tests/test_rest_usgs.py:193]` |
| TC-006.5 | CA-006.5 | negativo | 429 | Retry-After: 30 | Espera 30 s, cursor intacto | `[VERIFY: tests/test_rest_usgs.py:203]` |
| TC-006.6 | CA-006.6 | negativo | 500 | 5xx | Reintenta | `[VERIFY: tests/test_rest_usgs.py:212]` |
| TC-006.7 | CA-006.6 | negativo | Timeout | — | Reintenta | `[VERIFY: tests/test_rest_usgs.py:220]` |
| TC-006.8 | CA-006.6 | negativo | JSON inválido | cuerpo roto | No rompe | `[VERIFY: tests/test_rest_usgs.py:228]` |
| TC-006.9 | CA-006.7 | borde | Sin cursor | fresh install | Piso medianoche local | `[VERIFY: tests/test_rest_usgs.py:111]` |
| TC-006.10 | CA-006.7 | borde | Cursor de hace 5 días | rancio | Piso medianoche local | `[VERIFY: tests/test_rest_usgs.py:135]` |
| TC-006.11 | CA-006.8 | feliz | Cursor de hoy | fresco | Sin cambios | `[VERIFY: tests/test_rest_usgs.py:121]` |
| TC-006.12 | CA-006.9 | negativo | TZ inválida | `"Bad/Zone"` | Degrada, no rompe | `[VERIFY: tests/test_rest_usgs.py:149]` |
| TC-006.13 | CA-006.10 | feliz | Bucle | corriendo | Poll + espera | `[VERIFY: tests/test_rest_usgs.py:249]` |

## Dependencias

- **Requiere**: HU-001, HU-002 (cursor), HU-003
- **Habilita**: HU-008, HU-010

## Notas para la v2

Este módulo y `GEOFONPoller` (HU-022) comparten estructura casi completa —cursor, piso de
consulta, `Retry-After`, bucle— y difieren solo en el formato del cuerpo. ADR-016 difirió
la abstracción común "hasta una tercera fuente FDSN". La v2 llega con dos ya escritas: es
el momento de unificarlas parametrizando el parser. Ver DT-2 en `01-ARQUITECTURA.md`.
