# HU-020: Filtro de notificación por país

> **Cluster de origen:** Fase 12 (RF-37) · **Commits:** 1 `[COMMITS: a3a4a1a]`
> **Período:** 2026-07-04 · **Era:** Era 3 — Precisión de notificación

## Historia

**Como** usuario cerca de una frontera o de la costa `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** no ser despertado por sismos que ocurren claramente en otro país
**Para** que el radio no me traiga alertas que no me afectan

## Contexto de la implementación original

El filtro por radio no distingue países: un sismo a 80 km puede estar en Colombia,
Trinidad o una isla del Caribe.

La semántica es **block-list, no allow-list**
`[VERIFY: src/vigia_eew/pipeline/filter.py:61]`: se descarta solo lo que está
*positivamente dentro de otro país*; lo oceánico, offshore o de país indeterminado **se
conserva**. La lectura ingenua ("solo avísame de sismos en mi país") habría suprimido
justo los más peligrosos, porque los sismos más severos de Venezuela son offshore y no
caen en ningún polígono terrestre.

`country_of` `[VERIFY: src/vigia_eew/geocode.py:96]` hace punto-en-polígono **offline**
contra un Natural Earth 1:110m empaquetado, con ray casting en Python puro, pre-chequeo de
bounding box y soporte de agujeros — sin dependencia geoespacial y sin red por evento.

El país del usuario se deriva del punto de referencia ya resuelto
`[VERIFY: src/vigia_eew/app.py:130]`, así que funciona igual con referencia manual o
detectada por IP.

## Criterios de aceptación

### CA-020.1: Se descarta un sismo positivamente dentro de otro país
```gherkin
Dado el filtro activo y un país de usuario determinado
Cuando llega un evento dentro de las fronteras de otro país
Entonces se descarta
```
*Fuente: tests `[VERIFY: tests/test_filter.py:67]`,
`[VERIFY: tests/test_app.py:331]`*

### CA-020.2: Se conserva un sismo del propio país
```gherkin
Dado el filtro activo
Cuando el evento cae dentro del país del usuario
Entonces se acepta
```
*Fuente: test `[VERIFY: tests/test_filter.py:72]`*

### CA-020.3: Se conservan los eventos offshore o de país indeterminado
```gherkin
Dado el filtro activo
Cuando el evento no cae dentro de ningún polígono de país
Entonces se acepta
```
*Fuente: test `[VERIFY: tests/test_filter.py:77]` — es **el criterio central de esta HU**:
los sismos más peligrosos de Venezuela ocurren mar adentro*

### CA-020.4: Desactivado, no suprime nada
```gherkin
Dado country_filter en false
Cuando llega un evento de otro país
Entonces se acepta
```
*Fuente: tests `[VERIFY: tests/test_filter.py:83]`,
`[VERIFY: tests/test_app.py:323]` — off por defecto, para no alterar el comportamiento
existente hasta que se active explícitamente*

### CA-020.5: Sin país de usuario resoluble, el filtro queda inerte (fail-safe)
```gherkin
Dado el filtro activo pero sin poder determinar el país del usuario
Cuando llega cualquier evento
Entonces el filtro no suprime nada
```
*Fuente: tests `[VERIFY: tests/test_filter.py:88]`,
`[VERIFY: tests/test_app.py:342]` — herramienta de seguridad: ante la duda, no suprimir*

### CA-020.6: El filtro de país nunca relaja radio ni magnitud
```gherkin
Dado un evento del mismo país pero fuera del radio
Cuando se evalúa el filtro
Entonces se descarta igualmente
```
*Fuente: test `[VERIFY: tests/test_filter.py:94]`*

### CA-020.7: El país del usuario se deriva o se configura
```gherkin
Dado country = "auto" o un código ISO explícito
Cuando se resuelve el país del usuario
Entonces se deriva del punto de referencia, o se usa el configurado
```
*Fuente: tests `[VERIFY: tests/test_app.py:310]`,
`[VERIFY: tests/test_app.py:315]`*

### CA-020.8: El punto-en-polígono resuelve correctamente los casos geométricos
```gherkin
Dado un punto dentro de un polígono, dentro de un agujero,
     fuera de todos, o dentro de un multipolígono
Cuando se consulta el país
Entonces devuelve el código ISO correcto, o None cuando corresponde
```
*Fuente: tests `[VERIFY: tests/test_geocode.py:41]`,
`[VERIFY: tests/test_geocode.py:46]`, `[VERIFY: tests/test_geocode.py:51]`,
`[VERIFY: tests/test_geocode.py:56]`, `[VERIFY: tests/test_geocode.py:61]`*

### CA-020.9: El asset empaquetado ubica países reales
```gherkin
Dado el countries.geojson incluido en el paquete
Cuando se consultan coordenadas de Venezuela, Colombia y océano abierto
Entonces devuelve VE, CO y None respectivamente
```
*Fuente: tests `[VERIFY: tests/test_geocode.py:69]`,
`[VERIFY: tests/test_geocode.py:73]`, `[VERIFY: tests/test_geocode.py:77]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-020.1 | CA-020.1 | feliz | Otro país | punto en CO | Descarta | `[VERIFY: tests/test_filter.py:67]` |
| TC-020.2 | CA-020.2 | feliz | Mismo país | punto en VE | Acepta | `[VERIFY: tests/test_filter.py:72]` |
| TC-020.3 | CA-020.3 | borde | Offshore | mar Caribe | Acepta | `[VERIFY: tests/test_filter.py:77]` |
| TC-020.4 | CA-020.4 | negativo | Desactivado | filter=false | Acepta | `[VERIFY: tests/test_filter.py:83]` |
| TC-020.5 | CA-020.5 | negativo | Sin país de usuario | irresoluble | Inerte | `[VERIFY: tests/test_filter.py:88]` |
| TC-020.6 | CA-020.6 | borde | Mismo país, lejos | VE a 900 km | Descarta | `[VERIFY: tests/test_filter.py:94]` |
| TC-020.7 | CA-020.7 | feliz | country auto | referencia VE | "VE" | `[VERIFY: tests/test_app.py:315]` |
| TC-020.8 | CA-020.7 | borde | country explícito | "VE" | Usa el configurado | `[VERIFY: tests/test_app.py:310]` |
| TC-020.9 | CA-020.8 | feliz | Dentro de polígono | punto interior | ISO | `[VERIFY: tests/test_geocode.py:41]` |
| TC-020.10 | CA-020.8 | borde | Dentro de un agujero | enclave | None | `[VERIFY: tests/test_geocode.py:46]` |
| TC-020.11 | CA-020.8 | borde | Multipolígono | isla | ISO | `[VERIFY: tests/test_geocode.py:56]` |
| TC-020.12 | CA-020.9 | feliz | Asset real | Caracas | "VE" | `[VERIFY: tests/test_geocode.py:69]` |
| TC-020.13 | CA-020.9 | negativo | Océano abierto | Atlántico | None | `[VERIFY: tests/test_geocode.py:77]` |
| TC-020.14 | CA-020.1 | borde | **Frontera exacta**: punto a pocos km de la línea VE/CO | coordenada fronteriza | Resultado estable y documentado (1:110m tiene ±decenas de km) | **escribir en v2** |

## Dependencias

- **Requiere**: HU-009, HU-016 (punto de referencia)
- **Habilita**: precisión de notificación

## Notas para la v2

El compromiso aceptado: las fronteras 1:110m son **groseras cerca de los límites**
(±decenas de km). Es tolerable para un filtro best-effort y desactivado por defecto, con
ruta de mejora al dataset 1:50m si hiciera falta. TC-020.14 documenta que ese margen no
tiene test que lo fije.

La decisión a preservar literalmente es la semántica block-list: es contraintuitiva, está
bien fundamentada y **invertirla rompería la cobertura de los sismos más peligrosos**.
