# HU-001: Contrato interno único de evento sísmico

> **Cluster de origen:** Fase 1 · **Commits:** 1 `[COMMITS: b5c5371]`
> **Período:** 2026-06-28 · **Era:** Era 0 — Fundación

## Historia

**Como** desarrollador del agente `[INFERIDO: los commits no nombran persona]`
**Quiero** que todas las fuentes converjan en un único modelo de evento validado
**Para** que filtro, dedup y presentación no conozcan las particularidades de cada red

## Contexto de la implementación original

`SeismicEvent` `[VERIFY: src/vigia_eew/models.py:51]` es el único payload que cruza capas.
Los formatos crudos mueren en el normalizador; agregar una fuente es un ejercicio de
mapeo más un literal en `source`. El modelo **hace cumplir** sus invariantes en vez de
confiar en la convención: `_require_utc` rechaza datetimes *naive*
`[VERIFY: src/vigia_eew/models.py:25]` y la severidad se deriva siempre
`[VERIFY: src/vigia_eew/models.py:38]`.

## Criterios de aceptación

### CA-001.1: Un evento válido se construye con sus campos obligatorios
```gherkin
Dado un payload con id, fuente, tiempo UTC, lat, lon y magnitud válidos
Cuando se construye un SeismicEvent
Entonces el objeto se crea y conserva todos los campos
```
*Fuente: test `[VERIFY: tests/test_models.py:36]`*

### CA-001.2: Un datetime naive se rechaza
```gherkin
Dado un tiempo de origen sin zona horaria
Cuando se construye un SeismicEvent
Entonces la validación falla con error
```
*Fuente: test `[VERIFY: tests/test_models.py:48]` — invariante crítica: mezclar naive y
aware en la aritmética de ventanas de dedup da resultados incorrectos en silencio*

### CA-001.3: Un datetime con otra zona se convierte a UTC
```gherkin
Dado un tiempo tz-aware en una zona distinta de UTC
Cuando se construye un SeismicEvent
Entonces el tiempo queda normalizado a UTC
```
*Fuente: test `[VERIFY: tests/test_models.py:53]`*

### CA-001.4: `magtype` se normaliza a minúsculas
```gherkin
Dado un magtype reportado como "MW"
Cuando se construye el evento
Entonces magtype queda como "mw"
```
*Fuente: test `[VERIFY: tests/test_models.py:42]` — fuentes distintas usan distinta
capitalización para el mismo tipo de magnitud*

### CA-001.5: Coordenadas fuera de rango se rechazan
```gherkin
Dado un lat fuera de [-90, 90] o un lon fuera de [-180, 180]
Cuando se construye el evento
Entonces la validación falla
```
*Fuente: test `[VERIFY: tests/test_models.py:62]`*

### CA-001.6: La severidad se deriva de la magnitud según umbrales configurables
```gherkin
Dado un evento de magnitud M y unos umbrales de severidad
Cuando se clasifica la severidad
Entonces devuelve info (<4), warning (4–5.5) o critical (5.5+) según los umbrales
```
*Fuente: test `[VERIFY: tests/test_models.py:77]`, código
`[VERIFY: src/vigia_eew/models.py:38]`*

### CA-001.7: La firma del evento se deriva de sus propios campos
```gherkin
Dado un SeismicEvent
Cuando se pide su signature()
Entonces la firma refleja lat, lon, tiempo y magnitud del evento
```
*Fuente: test `[VERIFY: tests/test_models.py:67]` — habilita HU-010*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-001.1 | CA-001.1 | feliz | Evento completo válido | id, EMSC, UTC, 10.6/-66.9, M5.0 | Objeto creado | `[VERIFY: tests/test_models.py:36]` |
| TC-001.2 | CA-001.2 | negativo | Tiempo naive | `datetime(2026,1,1)` sin tz | ValidationError | `[VERIFY: tests/test_models.py:48]` |
| TC-001.3 | CA-001.3 | borde | Tiempo en `America/Caracas` | UTC-4 | Convertido a UTC | `[VERIFY: tests/test_models.py:53]` |
| TC-001.4 | CA-001.4 | borde | magtype mayúsculas | `"MW"` | `"mw"` | `[VERIFY: tests/test_models.py:42]` |
| TC-001.5 | CA-001.5 | negativo | lat 91 | lat=91 | ValidationError | `[VERIFY: tests/test_models.py:62]` |
| TC-001.6 | CA-001.6 | feliz | Tres magnitudes representativas | 3.0 / 4.5 / 6.1 | info / warning / critical | `[VERIFY: tests/test_models.py:77]` |
| TC-001.7 | CA-001.6 | borde | Magnitud exactamente en el umbral | 4.0 y 5.5 | Lado alto del umbral | escribir en v2 |
| TC-001.8 | CA-001.7 | feliz | Firma de un evento | evento válido | Campos coinciden | `[VERIFY: tests/test_models.py:67]` |

## Dependencias

- **Requiere**: ninguna — es la base del sistema
- **Habilita**: HU-008, HU-009, HU-010, HU-011, HU-012

## Notas para la v2

Mantener sin cambios: es la decisión estructural que permitió pasar de 2 a 4 fuentes sin
tocar el pipeline. El único hueco es CA-001.7 (TC-001.7): no hay test del comportamiento
**exactamente en el umbral** de severidad, y es justo donde un off-by-one cambiaría el
color y el perfil de sonido de una alerta real.
