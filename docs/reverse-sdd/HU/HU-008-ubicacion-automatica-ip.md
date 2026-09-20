# HU-008: No tener que averiguar mis coordenadas para que el filtro sirva

> **Cluster de origen:** C-10 · **Commits:** 1 `[COMMITS: c20a59b]`
> **Período:** 2026-07-04 · **Era:** v0.1.3

## Historia

**Como** usuario nuevo que instala el agente y no toca la configuración
**Quiero** que detecte dónde estoy sin que yo introduzca coordenadas
**Para** que el filtro por radio se centre en mi ubicación real y no en un valor por defecto ajeno

## Contexto de la implementación original

El problema que resuelve: RF-12 exigía un punto de referencia configurable, pero era 100 % manual
con Caracas por defecto — quien no configuraba nada quedaba con un filtro centrado en un punto que
no era el suyo, sin enterarse. `detect_ip_location`
`[VERIFY: src/vigia_eew/geoloc.py:39]` consulta el servicio **una sola vez**;
`_resolve_automatic_reference` `[VERIFY: src/vigia_eew/app.py:251]` decide cuándo hacerlo y
`cache_location` `[VERIFY: src/vigia_eew/state.py:120]` lo persiste.

La decisión vive en `app.py`, no en `config.py`: la carga de configuración sigue siendo una función
pura de lectura y validación TOML, sin red ni E/S de estado.

## Criterios de aceptación

### CA-008.1: Sin referencia manual, la ubicación se detecta una vez y se cachea
```gherkin
Dado un config.toml sin sección [reference] y sin ubicación cacheada
Cuando el agente se prepara para arrancar
Entonces consulta el servicio de geolocalización por IP una sola vez
Y persiste el resultado en el estado
Y en arranques posteriores usa la caché sin volver a llamar al servicio
```
*Fuente: tests `[VERIFY: tests/test_app.py:108]`, `[VERIFY: tests/test_app.py:136]`, `[VERIFY: tests/test_state.py:109]`*

### CA-008.2: Una referencia manual desactiva por completo la detección
```gherkin
Dado un config.toml con sección [reference] definida
Cuando el agente se prepara
Entonces no se llama al servicio de geolocalización
```
*Fuente: tests `[VERIFY: tests/test_app.py:123]`, `[VERIFY: tests/test_cli.py:100]`*

### CA-008.3: El fallo de detección no bloquea el arranque ni se cachea
```gherkin
Dado un servicio de geolocalización inalcanzable, lento o que responde algo inválido
Cuando el agente intenta detectar la ubicación
Entonces usa el punto por defecto y arranca igualmente
Y no persiste el fallo, de modo que puede reintentar en el siguiente arranque
```
*Fuente: tests `[VERIFY: tests/test_app.py:155]`, `[VERIFY: tests/test_geoloc.py:48]`, `[VERIFY: tests/test_geoloc.py:53]`, `[VERIFY: tests/test_geoloc.py:58]`*

### CA-008.4: Una respuesta con datos imposibles se rechaza
```gherkin
Dada una respuesta del servicio con latitud o longitud fuera de rango, o sin los campos requeridos
Cuando se parsea
Entonces se descarta y se trata como fallo de detección
```
*Fuente: tests `[VERIFY: tests/test_geoloc.py:68]`, `[VERIFY: tests/test_geoloc.py:63]`*

### CA-008.5: La simulación nunca resuelve ubicación
```gherkin
Dado el modo --simulate
Cuando se prepara la aplicación
Entonces no se llama al servicio de geolocalización, haya o no referencia manual
```
*Fuente: test `[VERIFY: tests/test_app.py:96]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-008.1 | CA-008.1 | feliz | primer arranque sin config | sin `[reference]` | detecta y cachea | `[VERIFY: tests/test_app.py:108]` |
| TC-008.2 | CA-008.1 | borde | segundo arranque | caché presente | no llama al servicio | `[VERIFY: tests/test_app.py:136]` |
| TC-008.3 | CA-008.2 | feliz | referencia manual | `[reference]` presente | sin llamada | `[VERIFY: tests/test_app.py:123]` |
| TC-008.4 | CA-008.3 | negativo | red caída | error de conexión | default, sin caché | `[VERIFY: tests/test_geoloc.py:48]` |
| TC-008.5 | CA-008.3 | negativo | HTTP 500 | status ≠ 200 | None | `[VERIFY: tests/test_geoloc.py:53]` |
| TC-008.6 | CA-008.4 | negativo | lat 999 | fuera de rango | None | `[VERIFY: tests/test_geoloc.py:68]` |
| TC-008.7 | CA-008.4 | borde | respuesta sin ciudad | falta `city` | nombre genérico | `[VERIFY: tests/test_geoloc.py:73]` |
| TC-008.8 | CA-008.5 | borde | `--simulate` | flag | sin geolocalización | `[VERIFY: tests/test_app.py:96]` |
| TC-008.9 | CA-008.1 | borde | cliente HTTP inyectado | cliente externo | no se cierra | `[VERIFY: tests/test_geoloc.py:80]` |

## Dependencias

- **Requiere**: HU-001 (estado y config), HU-005 (`Application`)
- **Habilita**: HU-012 (el país del usuario se deriva de esta referencia)

## Notas para la v2

La alternativa descartada fue geolocalización nativa del SO (CoreLocation / Windows Location API /
GeoClue): más precisa, pero tres integraciones nativas y permisos del sistema. Si la v2 acepta ese
coste, mejora la precisión del radio; si no, mantener la vía IP con este mismo diseño de
"una vez, cacheado, fail-safe".
