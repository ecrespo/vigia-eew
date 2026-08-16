# HU-008: Normalización multi-fuente

> **Cluster de origen:** Fase 3 · **Commits:** 1 `[COMMITS: b40c20b]`
> **Período:** 2026-06-28 · **Era:** Era 0 — Fundación

## Historia

**Como** desarrollador que agrega una fuente sísmica nueva `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** que el único trabajo sea mapear su formato al contrato interno
**Para** no tocar filtro, dedup ni presentación cada vez que aparece una red más

## Contexto de la implementación original

`Normalizer` `[VERIFY: src/vigia_eew/pipeline/normalize.py:38]` tiene un `_map_*` por
fuente —EMSC `[VERIFY: src/vigia_eew/pipeline/normalize.py:76]`, USGS
`[VERIFY: src/vigia_eew/pipeline/normalize.py:92]`, FUNVISIS
`[VERIFY: src/vigia_eew/pipeline/normalize.py:109]`, GEOFON
`[VERIFY: src/vigia_eew/pipeline/normalize.py:131]`— que convergen en `_build`
`[VERIFY: src/vigia_eew/pipeline/normalize.py:150]`, donde se calculan **siempre** la
distancia (haversine) y la severidad. Que sean derivadas y no leídas de la fuente es lo
que hace comparables eventos de redes distintas.

La predicción de la arquitectura se cumplió: FUNVISIS y GEOFON se sumaron después
añadiendo solo su `_map_*`.

## Criterios de aceptación

### CA-008.1: Cada fuente se mapea al contrato interno
```gherkin
Dado un payload crudo de EMSC, USGS, FUNVISIS o GEOFON
Cuando se normaliza
Entonces produce un SeismicEvent con la fuente correspondiente
```
*Fuente: tests `[VERIFY: tests/test_normalize.py:72]` (EMSC),
`[VERIFY: tests/test_normalize.py:100]` (USGS),
`[VERIFY: tests/test_normalize.py:182]` (FUNVISIS),
`[VERIFY: tests/test_normalize.py:229]` (GEOFON)*

### CA-008.2: La distancia se calcula por haversine desde el punto de referencia
```gherkin
Dado un evento y un punto de referencia
Cuando se normaliza
Entonces distance_km es la distancia haversine entre ambos
```
*Fuente: tests `[VERIFY: tests/test_normalize.py:119]`,
`[VERIFY: tests/test_geo.py:12]`*

### CA-008.3: La severidad se deriva de la magnitud y respeta los umbrales configurados
```gherkin
Dado un evento de magnitud M y unos umbrales configurados
Cuando se normaliza
Entonces la severidad corresponde a esos umbrales, no a los valores por defecto
```
*Fuente: tests `[VERIFY: tests/test_normalize.py:126]`,
`[VERIFY: tests/test_normalize.py:131]`*

### CA-008.4: La hora local de FUNVISIS se convierte a UTC
```gherkin
Dado un evento de FUNVISIS con hora en zona de Venezuela
Cuando se normaliza
Entonces time_utc queda en UTC
```
*Fuente: test `[VERIFY: tests/test_normalize.py:196]` — FUNVISIS publica en hora local;
tratarla como UTC desplazaría el evento 4 horas y rompería el dedup con otras fuentes*

### CA-008.5: La acción `update` de EMSC se preserva
```gherkin
Dado un mensaje EMSC de tipo update
Cuando se normaliza
Entonces la acción llega intacta al deduplicador
```
*Fuente: test `[VERIFY: tests/test_normalize.py:91]`*

### CA-008.6: `magtype` se normaliza a minúsculas
```gherkin
Dado un magtype en mayúsculas desde EMSC
Cuando se normaliza
Entonces queda en minúsculas
```
*Fuente: test `[VERIFY: tests/test_normalize.py:86]`*

### CA-008.7: Un payload incompleto o malformado devuelve None sin lanzar
```gherkin
Dado un payload sin campos obligatorios, con tiempo inválido,
     con profundidad o magnitud no numérica, o de fuente desconocida
Cuando se normaliza
Entonces devuelve None y el pipeline continúa con el siguiente mensaje
```
*Fuente: tests `[VERIFY: tests/test_normalize.py:139]`,
`[VERIFY: tests/test_normalize.py:144]`, `[VERIFY: tests/test_normalize.py:149]`,
`[VERIFY: tests/test_normalize.py:206]`, `[VERIFY: tests/test_normalize.py:244]`,
`[VERIFY: tests/test_normalize.py:248]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-008.1 | CA-008.1 | feliz | EMSC | payload EMSC | SeismicEvent EMSC | `[VERIFY: tests/test_normalize.py:72]` |
| TC-008.2 | CA-008.1 | feliz | USGS | Feature GeoJSON | SeismicEvent USGS | `[VERIFY: tests/test_normalize.py:100]` |
| TC-008.3 | CA-008.1 | feliz | FUNVISIS | JSON maravilla | SeismicEvent FUNVISIS | `[VERIFY: tests/test_normalize.py:182]` |
| TC-008.4 | CA-008.1 | feliz | GEOFON | fila pipe | SeismicEvent GEOFON | `[VERIFY: tests/test_normalize.py:229]` |
| TC-008.5 | CA-008.2 | feliz | Distancia | Caracas→La Guaira | ~25 km | `[VERIFY: tests/test_normalize.py:119]` |
| TC-008.6 | CA-008.3 | feliz | Severidad por magnitud | 3/4.5/6.1 | info/warning/critical | `[VERIFY: tests/test_normalize.py:126]` |
| TC-008.7 | CA-008.3 | borde | Umbrales personalizados | config alterna | Respeta config | `[VERIFY: tests/test_normalize.py:131]` |
| TC-008.8 | CA-008.4 | borde | Hora local VET | UTC-4 | Convertida a UTC | `[VERIFY: tests/test_normalize.py:196]` |
| TC-008.9 | CA-008.5 | feliz | update EMSC | action=update | Preservada | `[VERIFY: tests/test_normalize.py:91]` |
| TC-008.10 | CA-008.6 | borde | magtype "MW" | mayúsculas | "mw" | `[VERIFY: tests/test_normalize.py:86]` |
| TC-008.11 | CA-008.7 | negativo | Sin campos | `{}` | None | `[VERIFY: tests/test_normalize.py:139]` |
| TC-008.12 | CA-008.7 | negativo | Tiempo inválido | `"ayer"` | None | `[VERIFY: tests/test_normalize.py:144]` |
| TC-008.13 | CA-008.7 | negativo | Fuente desconocida | `"XYZ"` | None | `[VERIFY: tests/test_normalize.py:149]` |
| TC-008.14 | CA-008.7 | negativo | Profundidad malformada FUNVISIS | `"abc"` | None | `[VERIFY: tests/test_normalize.py:206]` |
| TC-008.15 | CA-008.7 | negativo | Magnitud malformada GEOFON | `"--"` | None | `[VERIFY: tests/test_normalize.py:244]` |

## Dependencias

- **Requiere**: HU-001, HU-005, HU-006
- **Habilita**: HU-009, HU-010, HU-021, HU-022

## Notas para la v2

El diseño se validó en la práctica: dos fuentes nuevas (FUNVISIS, GEOFON) entraron
tocando solo su `_map_*`. Mantener la regla de que **distancia y severidad son siempre
derivadas** — es lo que permite comparar eventos entre redes que reportan con criterios
distintos.
