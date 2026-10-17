# HU-022: Fuente global independiente GEOFON

> **Cluster de origen:** Fase 14 (RF-39) · **Commits:** 2 `[COMMITS: ade1199, 8e0064a]`
> **Período:** 2026-07-06 · **Era:** Era 4 — Redundancia de fuentes

## Historia

**Como** usuario que depende del agente como herramienta de seguridad `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** una cuarta red global totalmente independiente
**Para** que un punto ciego compartido entre EMSC y USGS no me deje sin aviso

## Contexto de la implementación original

EMSC y USGS son ambas autoritativas, pero pueden fallar **a la vez**: una caída de mensaje
en el WS coincidiendo con un retraso de reporte de USGS. GEOFON (GFZ Potsdam) añade
redundancia sin introducir una clase nueva de modo de fallo, porque se consulta igual que
USGS.

`GEOFONPoller` `[VERIFY: src/vigia_eew/ingest/rest_geofon.py:52]` es arquitectónicamente
**hermano de USGS, no de FUNVISIS**: bucle con cursor persistido y `starttime`, no seen-set.

**Parsea texto pipe-delimitado, no GeoJSON** `[VERIFY: src/vigia_eew/ingest/rest_geofon.py:83]`.
El soporte GeoJSON de GEOFON no pudo confirmarse en la verificación; pedir un formato que
podría diferir en silencio es peor que parsear explícitamente el que está documentado y
comprobado. QuakeML está disponible en el mismo endpoint y se descartó deliberadamente
para no añadir un parser XML.

`8e0064a` corrigió el endpoint a HTTPS poco después del lanzamiento inicial.

## Criterios de aceptación

### CA-022.1: La consulta usa los parámetros fijos y el formato texto
```gherkin
Dado un ciclo de poll
Cuando se construyen los parámetros
Entonces incluye format=text y los parámetros FDSN esperados
```
*Fuente: test `[VERIFY: tests/test_rest_geofon.py:89]`*

### CA-022.2: El endpoint se consulta por HTTPS
```gherkin
Dado la configuración por defecto de la fuente
Cuando se realiza la consulta
Entonces la URL usa HTTPS
```
*Fuente: fix `[COMMITS: 8e0064a]` — el lanzamiento inicial usaba HTTP plano*

### CA-022.3: Cada fila válida produce un RawMessage
```gherkin
Dado un cuerpo pipe-delimitado con N filas de datos
Cuando se procesa
Entonces se emiten N RawMessage con fuente GEOFON
```
*Fuente: test `[VERIFY: tests/test_rest_geofon.py:165]`*

### CA-022.4: Las filas que no son terremotos se descartan
```gherkin
Dado una fila cuyo EventType nombra explícitamente un evento no sísmico
Cuando se procesa
Entonces se descarta
```
*Fuente: test `[VERIFY: tests/test_rest_geofon.py:179]`, código
`[VERIFY: src/vigia_eew/ingest/rest_geofon.py:180]` — GEOFON cataloga también explosiones
y voladuras*

### CA-022.5: Una fila malformada no aborta el lote
```gherkin
Dado un cuerpo con una fila corrupta entre filas válidas
Cuando se procesa
Entonces la corrupta se descarta y las válidas se emiten
```
*Fuente: test `[VERIFY: tests/test_rest_geofon.py:189]`*

### CA-022.6: Un cuerpo sin cabecera se ignora
```gherkin
Dado una respuesta sin la fila de cabecera esperada
Cuando se procesa
Entonces se ignora sin romper
```
*Fuente: test `[VERIFY: tests/test_rest_geofon.py:257]`*

### CA-022.7: El cursor avanza, se persiste y no retrocede con respuestas vacías
```gherkin
Dado respuestas con y sin eventos
Cuando terminan los polls
Entonces el cursor avanza solo cuando hay eventos nuevos
```
*Fuente: tests `[VERIFY: tests/test_rest_geofon.py:203]`,
`[VERIFY: tests/test_rest_geofon.py:213]`*

### CA-022.8: Sin cursor o con cursor rancio, se acota al día local
```gherkin
Dado ausencia de cursor, o un cursor anterior a la medianoche local
Cuando se construyen los parámetros
Entonces starttime se fija en la medianoche local
```
*Fuente: tests `[VERIFY: tests/test_rest_geofon.py:109]`,
`[VERIFY: tests/test_rest_geofon.py:132]`*

### CA-022.9: Un cursor fresco se respeta sin modificar
```gherkin
Dado un cursor del día en curso
Cuando se construyen los parámetros
Entonces se usa tal cual
```
*Fuente: test `[VERIFY: tests/test_rest_geofon.py:120]`*

### CA-022.10: Una zona horaria inválida degrada sin romper
```gherkin
Dado un timezone inválido
Cuando se calcula el piso
Entonces se usa el cursor crudo, u se omite starttime si no hay cursor
```
*Fuente: tests `[VERIFY: tests/test_rest_geofon.py:144]`,
`[VERIFY: tests/test_rest_geofon.py:154]`*

### CA-022.11: Los errores HTTP no rompen el bucle
```gherkin
Dado un 204, un 429 con Retry-After, un 5xx o un timeout
Cuando ocurre durante un poll
Entonces se maneja apropiadamente y el bucle sigue
```
*Fuente: tests `[VERIFY: tests/test_rest_geofon.py:223]` (204 no es error),
`[VERIFY: tests/test_rest_geofon.py:232]`, `[VERIFY: tests/test_rest_geofon.py:241]`,
`[VERIFY: tests/test_rest_geofon.py:249]`*

### CA-022.12: Un evento de GEOFON ya reportado por otra fuente se deduplica
```gherkin
Dado un evento ya alertado por EMSC o USGS
Cuando GEOFON reporta el mismo sismo dentro de los umbrales
Entonces no se alerta de nuevo
```
*Fuente: test `[VERIFY: tests/test_dedup.py:86]` — la heurística no cambió al pasar de
tres a cuatro fuentes, porque ya era agnóstica al número de fuentes*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-022.1 | CA-022.1 | feliz | Parámetros | — | format=text | `[VERIFY: tests/test_rest_geofon.py:89]` |
| TC-022.2 | CA-022.2 | borde | HTTPS | URL por defecto | Esquema https | **escribir en v2** |
| TC-022.3 | CA-022.3 | feliz | 3 filas | cuerpo pipe | 3 RawMessage | `[VERIFY: tests/test_rest_geofon.py:165]` |
| TC-022.4 | CA-022.4 | negativo | Voladura | EventType=blast | Descartada | `[VERIFY: tests/test_rest_geofon.py:179]` |
| TC-022.5 | CA-022.5 | negativo | Fila corrupta | mixto | Resto emitido | `[VERIFY: tests/test_rest_geofon.py:189]` |
| TC-022.6 | CA-022.6 | negativo | Sin cabecera | cuerpo raro | Ignorado | `[VERIFY: tests/test_rest_geofon.py:257]` |
| TC-022.7 | CA-022.7 | feliz | Cursor avanza | eventos nuevos | Persistido | `[VERIFY: tests/test_rest_geofon.py:203]` |
| TC-022.8 | CA-022.7 | borde | Respuesta vacía | sin filas | Cursor intacto | `[VERIFY: tests/test_rest_geofon.py:213]` |
| TC-022.9 | CA-022.8 | borde | Sin cursor | fresh install | Medianoche local | `[VERIFY: tests/test_rest_geofon.py:109]` |
| TC-022.10 | CA-022.8 | borde | Cursor rancio | 5 días | Medianoche local | `[VERIFY: tests/test_rest_geofon.py:132]` |
| TC-022.11 | CA-022.9 | feliz | Cursor fresco | hoy | Sin cambios | `[VERIFY: tests/test_rest_geofon.py:120]` |
| TC-022.12 | CA-022.10 | negativo | TZ inválida | Bad/Zone | Degrada | `[VERIFY: tests/test_rest_geofon.py:144]` |
| TC-022.13 | CA-022.11 | borde | 204 | sin contenido | No es error | `[VERIFY: tests/test_rest_geofon.py:223]` |
| TC-022.14 | CA-022.11 | negativo | 429 | Retry-After | Respeta espera | `[VERIFY: tests/test_rest_geofon.py:232]` |
| TC-022.15 | CA-022.12 | feliz | Duplicado inter-fuente | tras EMSC | Sin re-alerta | `[VERIFY: tests/test_dedup.py:86]` |
| TC-022.16 | CA-022.1 | negativo | **Cambio de formato**: GEOFON altera columnas del texto | cuerpo con columnas distintas | Detección explícita, no descarte silencioso | **escribir en v2** |

## Dependencias

- **Requiere**: HU-002 (cursor), HU-007, HU-008, HU-010
- **Habilita**: redundancia global de cuatro fuentes

## Notas para la v2

Con 17 tests, esta es la fuente mejor cubierta del repo — y la más reciente, lo que sugiere
que el equipo aprendió de las anteriores.

Dos acciones para la v2:

1. **Unificar con USGS.** ADR-016 difirió la abstracción FDSN común "hasta que haya una
   tercera fuente". La v2 arranca con dos ya escritas y estructura casi idéntica (cursor,
   piso, `Retry-After`, bucle); solo difiere el parser del cuerpo. Ver DT-2.
2. **TC-022.16**: el formato texto pipe **no es un contrato versionado**. Si GEOFON
   reordena o renombra columnas, hoy las filas se descartarían silenciosamente como
   malformadas y el usuario perdería una fuente sin enterarse. Un test de contrato contra
   una respuesta real grabada, más una alarma si el ratio de filas descartadas se dispara,
   convertiría un fallo silencioso en uno visible (RR-7).
