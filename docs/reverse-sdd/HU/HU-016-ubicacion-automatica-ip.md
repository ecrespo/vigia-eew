# HU-016: Ubicación automática por IP

> **Cluster de origen:** Fase 9 (RF-33) · **Commits:** 1 `[COMMITS: c20a59b]`
> **Período:** 2026-07-04 · **Era:** Era 2 — Contexto del usuario

## Historia

**Como** usuario que instala el agente y no edita la configuración `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** que detecte dónde estoy
**Para** no quedarme con un filtro centrado en una ciudad que no es la mía, sin enterarme

## Contexto de la implementación original

Antes de esta HU, el punto de referencia era 100 % manual con Caracas por defecto: quien
no editaba `config.toml` obtenía un filtro geográfico centrado en un punto ajeno —
silenciosamente incorrecto, y equivocado en la dirección peligrosa (perder alertas
reales).

`Application._resolve_automatic_reference` `[VERIFY: src/vigia_eew/app.py:252]` detecta por
IP **exactamente una vez** y cachea en el estado. Si hay `[reference]` manual o caché, la
API **nunca** se llama. `detect_ip_location`
`[VERIFY: src/vigia_eew/geoloc.py:39]` nunca lanza: devuelve `None` y el arranque cae al
default sin bloquearse.

La decisión vive en `app.py` y no en `config.py` a propósito: `config.py` sigue siendo una
función pura de lectura y validación (HU-003).

## Criterios de aceptación

### CA-016.1: Sin referencia manual, se detecta por IP y se cachea
```gherkin
Dado un config sin sección [reference] y sin ubicación cacheada
Cuando arranca el agente
Entonces consulta el servicio de geolocalización y persiste el resultado
```
*Fuente: test `[VERIFY: tests/test_app.py:108]`*

### CA-016.2: Con referencia manual, nunca se consulta la API
```gherkin
Dado un config con [reference] definido
Cuando arranca el agente
Entonces no se llama al servicio de geolocalización
```
*Fuente: test `[VERIFY: tests/test_app.py:123]`*

### CA-016.3: Con ubicación cacheada, tampoco se consulta
```gherkin
Dado una ubicación previamente detectada y cacheada
Cuando arranca el agente
Entonces la usa sin llamar al servicio
```
*Fuente: test `[VERIFY: tests/test_app.py:136]` — la ubicación de una máquina no cambia
entre arranques; consultar cada vez ataría el arranque a la red para siempre*

### CA-016.4: Si la detección falla, se usa el default sin cachear el fallo
```gherkin
Dado que la geolocalización falla
Cuando arranca el agente
Entonces usa el punto por defecto, no bloquea el arranque
       y no cachea nada, para poder reintentar en el siguiente arranque
```
*Fuente: test `[VERIFY: tests/test_app.py:155]`*

### CA-016.5: Toda clase de fallo devuelve None, nunca una excepción
```gherkin
Dado un error de red, un status distinto de 200, un JSON inválido,
     campos faltantes o coordenadas fuera de rango
Cuando se intenta detectar la ubicación
Entonces devuelve None
```
*Fuente: tests `[VERIFY: tests/test_geoloc.py:48]`,
`[VERIFY: tests/test_geoloc.py:53]`, `[VERIFY: tests/test_geoloc.py:58]`,
`[VERIFY: tests/test_geoloc.py:63]`, `[VERIFY: tests/test_geoloc.py:68]` — mismo patrón
de aislamiento que `toast.py`: siempre hay un fallback*

### CA-016.6: Una respuesta válida se traduce a punto de referencia
```gherkin
Dado una respuesta correcta del servicio
Cuando se parsea
Entonces produce un punto de referencia con nombre, latitud y longitud
```
*Fuente: test `[VERIFY: tests/test_geoloc.py:37]`*

### CA-016.7: Sin ciudad en la respuesta, se usa un nombre genérico
```gherkin
Dado una respuesta sin campo de ciudad
Cuando se parsea
Entonces se usa un nombre genérico en vez de fallar
```
*Fuente: test `[VERIFY: tests/test_geoloc.py:73]`*

### CA-016.8: Un cliente inyectado no se cierra
```gherkin
Dado un cliente HTTP proporcionado por el llamador
Cuando termina la detección
Entonces el cliente no se cierra, porque su ciclo de vida es del llamador
```
*Fuente: test `[VERIFY: tests/test_geoloc.py:80]`*

### CA-016.9: `--simulate` nunca dispara la detección
```gherkin
Dado el modo simulación
Cuando arranca
Entonces no se consulta la geolocalización, haya o no referencia manual
```
*Fuente: test `[VERIFY: tests/test_app.py:96]` — RF-21 exige que la simulación funcione
sin red*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-016.1 | CA-016.1 | feliz | Sin referencia | config vacío | Detecta y cachea | `[VERIFY: tests/test_app.py:108]` |
| TC-016.2 | CA-016.2 | borde | Referencia manual | [reference] | Sin llamada | `[VERIFY: tests/test_app.py:123]` |
| TC-016.3 | CA-016.3 | borde | Caché presente | cacheado | Sin llamada | `[VERIFY: tests/test_app.py:136]` |
| TC-016.4 | CA-016.4 | negativo | Detección falla | timeout | Default, sin caché | `[VERIFY: tests/test_app.py:155]` |
| TC-016.5 | CA-016.5 | negativo | Error de red | ConnectError | None | `[VERIFY: tests/test_geoloc.py:48]` |
| TC-016.6 | CA-016.5 | negativo | Status 500 | 500 | None | `[VERIFY: tests/test_geoloc.py:53]` |
| TC-016.7 | CA-016.5 | negativo | JSON inválido | cuerpo roto | None | `[VERIFY: tests/test_geoloc.py:58]` |
| TC-016.8 | CA-016.5 | negativo | Coordenadas inválidas | lat=200 | None | `[VERIFY: tests/test_geoloc.py:68]` |
| TC-016.9 | CA-016.6 | feliz | Respuesta válida | JSON ok | ReferencePoint | `[VERIFY: tests/test_geoloc.py:37]` |
| TC-016.10 | CA-016.7 | borde | Sin ciudad | falta city | Nombre genérico | `[VERIFY: tests/test_geoloc.py:73]` |
| TC-016.11 | CA-016.8 | borde | Cliente inyectado | client externo | No se cierra | `[VERIFY: tests/test_geoloc.py:80]` |
| TC-016.12 | CA-016.9 | borde | Simulación | --simulate | Sin geoloc | `[VERIFY: tests/test_app.py:96]` |

## Dependencias

- **Requiere**: HU-002 (caché), HU-003 (`has_manual_reference`)
- **Habilita**: HU-009 (referencia del filtro), HU-020 (país del usuario)

## Notas para la v2

Esta es la **única excepción de privacidad documentada** del proyecto: la IP de origen
queda visible para un tercero (`ipapi.co`). Se dispara solo por *ausencia* de
configuración, nunca con datos aportados por el usuario, y se desactiva por completo
definiendo `[reference]`.

En la v2, mantener esa propiedad y hacerla explícita al usuario en el primer arranque
—un aviso en el `config.toml` sembrado— sería una mejora barata sobre el diseño actual.
Se rechazó la geolocalización nativa del SO (CoreLocation/GeoClue/Windows Location) por
requerir tres integraciones nativas y permisos del sistema; esa evaluación sigue vigente.
