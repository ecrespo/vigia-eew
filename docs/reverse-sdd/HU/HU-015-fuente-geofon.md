# HU-015: No quedarme ciego si las dos redes principales fallan a la vez

> **Cluster de origen:** C-17 · **Commits:** 2 `[COMMITS: ade1199, 8e0064a]`
> **Período:** 2026-07-06 · **Era:** v0.5.0

## Historia

**Como** usuario que depende del agente como único aviso
**Quiero** que consulte también una red sísmica global independiente
**Para** que un fallo simultáneo de EMSC y USGS no me deje sin alerta

## Contexto de la implementación original

EMSC y USGS pueden compartir puntos ciegos: un mensaje perdido del WebSocket coincidiendo con un
retraso de reporte de USGS deja al agente sin el evento. `GEOFONPoller`
`[VERIFY: src/vigia_eew/ingest/rest_geofon.py:52]` consulta el servicio `fdsnws-event` de GFZ
Potsdam cada 60 s con **cursor propio** `[VERIFY: src/vigia_eew/ingest/rest_geofon.py:80]` —
arquitectónicamente es "el hermano de USGS", no el de FUNVISIS.

**Formato texto, no GeoJSON**: el soporte GeoJSON de GEOFON no pudo confirmarse en verificación en
vivo; su respuesta documentada y confirmada es una tabla delimitada por barras
`[VERIFY: src/vigia_eew/ingest/rest_geofon.py:133]`. QuakeML/XML se descartó para no añadir una
dependencia de parseo XML. El segundo commit del cluster corrige el endpoint a HTTPS.

## Criterios de aceptación

### CA-015.1: Se emite un evento por fila válida de la tabla
```gherkin
Dada una respuesta en formato texto delimitado por barras
Cuando se procesa
Entonces se emite un RawMessage por cada fila de sismo
Y el cursor avanza y se persiste solo tras procesar la respuesta
Y una respuesta vacía no mueve el cursor
```
*Fuente: tests `[VERIFY: tests/test_rest_geofon.py:165]`, `[VERIFY: tests/test_rest_geofon.py:203]`, `[VERIFY: tests/test_rest_geofon.py:213]`*

### CA-015.2: Las filas que no son sismos se ignoran
```gherkin
Dada una respuesta que incluye filas de tipos de evento distintos de terremoto
Cuando se procesa
Entonces esas filas se omiten sin generar eventos
```
*Fuente: test `[VERIFY: tests/test_rest_geofon.py:179]`; código `[VERIFY: src/vigia_eew/ingest/rest_geofon.py:179]`*

### CA-015.3: Una fila malformada no aborta el lote
```gherkin
Dada una respuesta con una fila corrupta entre filas válidas
Cuando se procesa
Entonces la fila corrupta se descarta y las válidas se emiten igualmente
Y un cuerpo sin cabecera se ignora por completo
```
*Fuente: tests `[VERIFY: tests/test_rest_geofon.py:189]`, `[VERIFY: tests/test_rest_geofon.py:257]`, `[VERIFY: tests/test_normalize.py:244]`*

### CA-015.4: Las respuestas de error se toleran, incluida la ausencia de contenido
```gherkin
Dado un endpoint que responde 204, 429, 5xx o agota el tiempo de espera
Cuando el poller ejecuta su ciclo
Entonces el 204 no se considera error
Y ante 429 se respeta Retry-After
Y en los demás casos se registra y se continúa
```
*Fuente: tests `[VERIFY: tests/test_rest_geofon.py:223]`, `[VERIFY: tests/test_rest_geofon.py:232]`, `[VERIFY: tests/test_rest_geofon.py:241]`, `[VERIFY: tests/test_rest_geofon.py:249]`*

### CA-015.5: El tráfico va cifrado
```gherkin
Dado el endpoint de GEOFON configurado por defecto
Cuando se realiza la consulta
Entonces se usa HTTPS
```
*Fuente: fix `[COMMITS: 8e0064a]` — el endpoint se introdujo en HTTP y se corrigió a HTTPS el mismo día. **Sin test automatizado que fije el esquema.***

### CA-015.6: La cuarta fuente no cambia la heurística de deduplicación
```gherkin
Dado un sismo ya alertado por EMSC, USGS o FUNVISIS
Cuando GEOFON reporta el mismo sismo dentro de los umbrales
Entonces se considera duplicado y no se alerta
Y un sismo que solo reporta GEOFON sí genera alerta
```
*Fuente: tests `[VERIFY: tests/test_dedup.py:86]`, `[VERIFY: tests/test_dedup.py:100]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-015.1 | CA-015.1 | feliz | 3 filas válidas | texto pipe | 3 RawMessage | `[VERIFY: tests/test_rest_geofon.py:165]` |
| TC-015.2 | CA-015.1 | borde | respuesta vacía | sin filas | cursor sin mover | `[VERIFY: tests/test_rest_geofon.py:213]` |
| TC-015.3 | CA-015.2 | borde | fila de otro tipo | evento no sísmico | omitida | `[VERIFY: tests/test_rest_geofon.py:179]` |
| TC-015.4 | CA-015.3 | negativo | fila corrupta | campos faltantes | resto emitido | `[VERIFY: tests/test_rest_geofon.py:189]` |
| TC-015.5 | CA-015.3 | negativo | sin cabecera | cuerpo suelto | ignorado | `[VERIFY: tests/test_rest_geofon.py:257]` |
| TC-015.6 | CA-015.4 | borde | HTTP 204 | sin contenido | no es error | `[VERIFY: tests/test_rest_geofon.py:223]` |
| TC-015.7 | CA-015.4 | negativo | HTTP 429 | Retry-After | espera indicada | `[VERIFY: tests/test_rest_geofon.py:232]` |
| TC-015.8 | CA-015.5 | negativo | esquema del endpoint | config por defecto | debe ser `https://` | No — **hueco P1**, fue un fix real |
| TC-015.9 | CA-015.6 | feliz | duplicado de fuente previa | mismo sismo | sin segunda alerta | `[VERIFY: tests/test_dedup.py:86]` |
| TC-015.10 | CA-015.6 | borde | solo GEOFON lo reporta | evento único | alerta emitida | `[VERIFY: tests/test_dedup.py:100]` |

## Dependencias

- **Requiere**: HU-002 (patrón de reconciliación con cursor), HU-003 (dedup)
- **Habilita**: HU-016 (el piso de `starttime` aplica a esta fuente y a USGS)

## Notas para la v2

Se descartó explícitamente compartir una clase genérica de poller FDSN parametrizada por formato
entre USGS y GEOFON: con dos fuentes la indirección no compensa. Si la v2 añade una quinta fuente
de esa familia, es el momento de unificar. Y conviene un test que fije el esquema HTTPS del
endpoint (TC-015.8), ya que su ausencia permitió el fix `8e0064a`.
