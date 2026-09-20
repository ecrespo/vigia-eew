# HU-012: No recibir avisos de sismos de otros países

> **Cluster de origen:** C-14 · **Commits:** 1 `[COMMITS: a3a4a1a]`
> **Período:** 2026-07-04 · **Era:** v0.2.1

## Historia

**Como** usuario que vive cerca de una frontera o de la costa
**Quiero** poder descartar los sismos que ocurren claramente dentro de otro país
**Para** que el radio no me despierte por un temblor que no me afecta, sin perder los que sí

## Contexto de la implementación original

El filtro por radio no distingue países: a 80 km puede haber Colombia, Trinidad o una isla del
Caribe. La solución es **opt-in** (`[filter] country_filter`, por defecto `false`) y su semántica
es **lista de bloqueo**: se descarta solo lo que está *positivamente dentro de otro país*
`[VERIFY: src/vigia_eew/pipeline/filter.py:60]`.

Esa asimetría es deliberada: los sismos más peligrosos de Venezuela son *offshore* y quedan fuera
de todo polígono terrestre; una regla de lista blanca los descartaría justamente a ellos.
`country_of` `[VERIFY: src/vigia_eew/geocode.py:96]` resuelve el país sin red ni dependencia
geoespacial, con *ray casting* puro sobre un GeoJSON reducido de Natural Earth 1:110m generado en
el repo `[VERIFY: packaging/build_countries_geojson.py:1]`.

## Criterios de aceptación

### CA-012.1: Se descarta lo que está dentro de otro país
```gherkin
Dado el filtro de país activo y un país de usuario conocido
Cuando llega un evento cuyas coordenadas caen dentro de otro país
Entonces se descarta
Y un evento dentro del país del usuario se mantiene
```
*Fuente: tests `[VERIFY: tests/test_filter.py:67]`, `[VERIFY: tests/test_filter.py:72]`*

### CA-012.2: Lo indeterminado y lo marino se conserva
```gherkin
Dado el filtro de país activo
Cuando llega un evento cuyo país no puede determinarse, por ejemplo mar adentro
Entonces se mantiene, sujeto solo a radio y magnitud
```
*Fuente: test `[VERIFY: tests/test_filter.py:77]`; código `[VERIFY: src/vigia_eew/pipeline/filter.py:60]`*

### CA-012.3: El filtro es fail-safe e inerte si no puede evaluarse
```gherkin
Dado el filtro de país activo pero sin país de usuario resoluble
Cuando se evalúan los eventos
Entonces el filtro no suprime nada
Y con el filtro desactivado, un evento de otro país se conserva
```
*Fuente: tests `[VERIFY: tests/test_filter.py:88]`, `[VERIFY: tests/test_filter.py:83]`, `[VERIFY: tests/test_app.py:170]`*

### CA-012.4: El filtro de país nunca amplía lo que el radio ya descartó
```gherkin
Dado un evento del mismo país del usuario pero fuera del radio configurado
Cuando se evalúa el filtro
Entonces se descarta igualmente
```
*Fuente: test `[VERIFY: tests/test_filter.py:94]`*

### CA-012.5: La resolución de país es correcta, offline y sin dependencias
```gherkin
Dado el conjunto de polígonos empaquetado
Cuando se consulta un punto
Entonces devuelve el ISO del país si está dentro de un polígono, incluido el caso multipolígono
Y devuelve nulo si el punto cae en un hueco del polígono o en mar abierto
```
*Fuente: tests `[VERIFY: tests/test_geocode.py:41]`, `[VERIFY: tests/test_geocode.py:46]`, `[VERIFY: tests/test_geocode.py:56]`, `[VERIFY: tests/test_geocode.py:69]`, `[VERIFY: tests/test_geocode.py:77]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-012.1 | CA-012.1 | feliz | sismo en Colombia, usuario VE | coords CO | descartado | `[VERIFY: tests/test_filter.py:67]` |
| TC-012.2 | CA-012.1 | feliz | sismo en Venezuela | coords VE | conservado | `[VERIFY: tests/test_filter.py:72]` |
| TC-012.3 | CA-012.2 | borde | costa venezolana, offshore | mar | conservado | `[VERIFY: tests/test_filter.py:77]` |
| TC-012.4 | CA-012.3 | negativo | sin país de usuario | referencia indeterminable | filtro inerte | `[VERIFY: tests/test_filter.py:88]` |
| TC-012.5 | CA-012.3 | borde | filtro desactivado | `country_filter=false` | conservado | `[VERIFY: tests/test_filter.py:83]` |
| TC-012.6 | CA-012.4 | negativo | mismo país, 900 km | fuera de radio | descartado | `[VERIFY: tests/test_filter.py:94]` |
| TC-012.7 | CA-012.5 | feliz | punto en Venezuela | asset real | `VE` | `[VERIFY: tests/test_geocode.py:69]` |
| TC-012.8 | CA-012.5 | borde | punto en un hueco | polígono con agujero | None | `[VERIFY: tests/test_geocode.py:46]` |
| TC-012.9 | CA-012.5 | negativo | océano abierto | coords marinas | None | `[VERIFY: tests/test_geocode.py:77]` |

## Dependencias

- **Requiere**: HU-003 (filtro), HU-008 (el país del usuario se deriva del punto de referencia)
- **Habilita**: ninguna

## Notas para la v2

El conjunto 1:110m es tosco cerca de fronteras (decenas de km de error). Está aceptado porque el
filtro es best-effort y viene desactivado. Si la v2 lo activa por defecto, hay que subir a 1:50m y
declarar el margen de error en la documentación de usuario.
