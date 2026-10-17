# HU-003: Un solo aviso por terremoto, y solo si me afecta

> **Cluster de origen:** C-04 · **Commits:** 1 `[COMMITS: b40c20b]`
> **Período:** 2026-06-28 · **Era:** v0.1.0

## Historia

**Como** usuario del agente
**Quiero** recibir un único aviso por terremoto, aunque varias redes lo reporten, y solo si ocurre cerca y con magnitud relevante
**Para** no acostumbrarme a ignorar avisos por repetidos o irrelevantes

## Contexto de la implementación original

570 líneas que crean la cadena normalizar → filtrar → deduplicar. `Normalizer`
`[VERIFY: src/vigia_eew/pipeline/normalize.py:38]` traduce cada payload al contrato interno y
deriva distancia y severidad; `GeoFilter.accepts` `[VERIFY: src/vigia_eew/pipeline/filter.py:52]`
decide relevancia; `Deduplicator.classify` `[VERIFY: src/vigia_eew/pipeline/dedup.py:45]` resuelve
identidad entre fuentes con una heurística de distancia, tiempo y magnitud
`[VERIFY: src/vigia_eew/pipeline/dedup.py:70]`.

## Criterios de aceptación

### CA-003.1: Los campos derivados se calculan, nunca se copian de la fuente
```gherkin
Dado un evento de cualquier fuente y un punto de referencia configurado
Cuando se normaliza
Entonces la distancia se calcula por haversine desde la referencia
Y la severidad se deriva de la magnitud según los umbrales configurados
```
*Fuente: tests `[VERIFY: tests/test_normalize.py:119]`, `[VERIFY: tests/test_normalize.py:126]`; código `[VERIFY: src/vigia_eew/geo.py:16]`*

### CA-003.2: Un payload incompleto o inválido se descarta sin romper el pipeline
```gherkin
Dado un payload sin los campos requeridos, con instante inválido o de fuente desconocida
Cuando se normaliza
Entonces se devuelve None y el pipeline continúa
```
*Fuente: tests `[VERIFY: tests/test_normalize.py:139]`, `[VERIFY: tests/test_normalize.py:144]`, `[VERIFY: tests/test_normalize.py:149]`*

### CA-003.3: Solo pasan los eventos dentro del radio y sobre la magnitud mínima
```gherkin
Dado un radio y una magnitud mínima configurados
Cuando llega un evento fuera del radio o por debajo de la magnitud
Entonces se descarta
Y los límites son inclusivos: un evento exactamente en el radio o en la magnitud mínima se acepta
```
*Fuente: tests `[VERIFY: tests/test_filter.py:36]`, `[VERIFY: tests/test_filter.py:40]`, `[VERIFY: tests/test_filter.py:44]`, `[VERIFY: tests/test_filter.py:48]`, `[VERIFY: tests/test_filter.py:52]`*

### CA-003.4: El mismo terremoto reportado por dos redes produce una sola alerta
```gherkin
Dado un evento ya alertado por una fuente
Cuando otra fuente reporta un evento a menos de 100 km, 90 s y 0,5 de magnitud de diferencia
Entonces se clasifica como duplicado y no se alerta
Y si cualquiera de los tres umbrales se supera, se trata como evento nuevo
```
*Fuente: tests `[VERIFY: tests/test_dedup.py:75]`, `[VERIFY: tests/test_dedup.py:106]`, `[VERIFY: tests/test_dedup.py:113]`, `[VERIFY: tests/test_dedup.py:123]`*

### CA-003.5: Un `update` de EMSC refresca la alerta en curso, no crea otra
```gherkin
Dado un evento ya alertado
Cuando EMSC envía un update con el mismo id
Entonces se clasifica como update
Y si el id nunca fue alertado, el update se trata como evento nuevo
```
*Fuente: tests `[VERIFY: tests/test_dedup.py:60]`, `[VERIFY: tests/test_dedup.py:66]`*

### CA-003.6: Lo alertado se persiste, y sobrevive al reinicio
```gherkin
Dado un evento que acaba de alertarse
Cuando se registra
Entonces su id y su firma quedan persistidos
Y tras reiniciar el agente ese evento sigue considerándose ya alertado
```
*Fuente: tests `[VERIFY: tests/test_dedup.py:133]`, `[VERIFY: tests/test_dedup.py:143]`; e2e `[VERIFY: tests/test_resilience.py:138]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-003.1 | CA-003.1 | feliz | evento EMSC normal | payload EMSC | SeismicEvent con distancia y severidad | `[VERIFY: tests/test_normalize.py:72]` |
| TC-003.2 | CA-003.1 | borde | magtype en mayúsculas | `MW` | normalizado a minúsculas | `[VERIFY: tests/test_normalize.py:86]` |
| TC-003.3 | CA-003.2 | negativo | fuente desconocida | source `"XXX"` | None | `[VERIFY: tests/test_normalize.py:149]` |
| TC-003.4 | CA-003.3 | feliz | dentro de radio y magnitud | 50 km / M5 | aceptado | `[VERIFY: tests/test_filter.py:36]` |
| TC-003.5 | CA-003.3 | borde | exactamente en el radio | radio exacto | aceptado | `[VERIFY: tests/test_filter.py:48]` |
| TC-003.6 | CA-003.3 | negativo | fuera de radio | 900 km | descartado | `[VERIFY: tests/test_filter.py:40]` |
| TC-003.7 | CA-003.4 | feliz | duplicado cruzado | EMSC + USGS mismo sismo | una sola alerta | `[VERIFY: tests/test_resilience.py:107]` |
| TC-003.8 | CA-003.4 | borde | 95 km / 85 s / 0,4 mag | dentro de umbrales | duplicado | `[VERIFY: tests/test_dedup.py:75]` |
| TC-003.9 | CA-003.4 | negativo | 300 km de distancia | fuera de umbral | evento nuevo | `[VERIFY: tests/test_dedup.py:106]` |
| TC-003.10 | CA-003.5 | feliz | update de id alertado | action `update` | clasificado update | `[VERIFY: tests/test_dedup.py:60]` |
| TC-003.11 | CA-003.5 | negativo | update de id desconocido | action `update` | tratado como nuevo | `[VERIFY: tests/test_dedup.py:66]` |
| TC-003.12 | CA-003.6 | feliz | reinicio tras alerta | state.json | sin re-alerta | `[VERIFY: tests/test_dedup.py:143]` |

## Dependencias

- **Requiere**: HU-001, HU-002
- **Habilita**: HU-004, HU-012, HU-016

## Notas para la v2

La heurística de dedup puede fusionar sismos distintos durante un enjambre. Los umbrales ya son
configurables; la v2 debería además registrar por qué se fusionó (qué firma coincidió) para poder
diagnosticar falsos positivos sin reproducir el enjambre.
