# HU-002: Estado persistente entre reinicios

> **Cluster de origen:** Fase 1 + Fase 15 · **Commits:** 2 `[COMMITS: b5c5371, b0f832c]`
> **Período:** 2026-06-28 → 2026-07-17 · **Era:** Era 0 + Era 5

## Historia

**Como** usuario del agente `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** que reiniciar el agente no me repita alertas que ya reconocí
**Para** poder reiniciar o reinstalar sin que el sistema pierda credibilidad

## Contexto de la implementación original

`StateStore` `[VERIFY: src/vigia_eew/state.py:33]` persiste `alerted_ids`,
`recent_signatures`, los cursores de USGS/GEOFON y la ubicación detectada, en un JSON en
el directorio de datos del usuario `[VERIFY: src/vigia_eew/state.py:28]`. La escritura es
**atómica** (temp + `os.replace`) y un archivo corrupto se trata como "empezar de cero",
no como error — un agente de seguridad que se niega a arrancar porque su caché está dañada
eligió mal su modo de fallo.

`prune()` existía desde la fase 1 con test propio, pero **ninguna ruta lo llamaba**;
`b0f832c` lo cableó a `register()` `[VERIFY: src/vigia_eew/pipeline/dedup.py:64]`.

## Criterios de aceptación

### CA-002.1: Un estado nuevo arranca vacío
```gherkin
Dado que no existe archivo de estado
Cuando se carga el StateStore
Entonces el estado está vacío y no falla
```
*Fuente: test `[VERIFY: tests/test_state.py:16]`*

### CA-002.2: El estado sobrevive un ciclo de escritura y lectura
```gherkin
Dado un estado con ids alertados y firmas
Cuando se guarda y se vuelve a cargar desde disco
Entonces el contenido es idéntico
```
*Fuente: test `[VERIFY: tests/test_state.py:23]`*

### CA-002.3: Un evento ya alertado no se re-alerta tras reiniciar
```gherkin
Dado un evento registrado como alertado y persistido
Cuando el agente se reinicia y recibe el mismo evento
Entonces no se genera una alerta nueva
```
*Fuente: tests `[VERIFY: tests/test_state.py:39]` y end-to-end
`[VERIFY: tests/test_resilience.py:138]`*

### CA-002.4: El cursor solo avanza, nunca retrocede
```gherkin
Dado un cursor persistido en T
Cuando se intenta actualizarlo con un valor anterior a T
Entonces el cursor conserva T
```
*Fuente: test `[VERIFY: tests/test_state.py:52]` — un cursor que retrocede reprocesaría
historia ya vista*

### CA-002.5: Un archivo de estado corrupto no impide arrancar
```gherkin
Dado un state.json con contenido inválido
Cuando el agente arranca
Entonces parte de un estado vacío y continúa
```
*Fuente: test `[VERIFY: tests/test_state.py:86]`*

### CA-002.6: La escritura es atómica
```gherkin
Dado un guardado de estado
Cuando termina la escritura
Entonces queda un único archivo, sin temporales huérfanos
```
*Fuente: test `[VERIFY: tests/test_state.py:94]`*

### CA-002.7: Las entradas viejas se podan al registrar una alerta
```gherkin
Dado un estado con entradas de más de 24 h
Cuando se registra una alerta nueva
Entonces las entradas caducadas se eliminan antes de guardar
```
*Fuente: fix `[COMMITS: b0f832c]` — previene el crecimiento sin límite de `state.json`,
que existió durante 14 releases; tests `[VERIFY: tests/test_state.py:72]` (poda) y
`[VERIFY: tests/test_dedup.py:157]` (cableado)*

### CA-002.8: La ubicación detectada se cachea y se recupera
```gherkin
Dado que se detectó una ubicación por IP
Cuando el agente se reinicia
Entonces la usa desde caché sin volver a llamar al servicio
```
*Fuente: tests `[VERIFY: tests/test_state.py:109]`, `[VERIFY: tests/test_app.py:136]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-002.1 | CA-002.1 | feliz | Primer arranque | sin archivo | Estado vacío | `[VERIFY: tests/test_state.py:16]` |
| TC-002.2 | CA-002.2 | feliz | Round-trip | ids + firmas | Idéntico | `[VERIFY: tests/test_state.py:23]` |
| TC-002.3 | CA-002.3 | feliz | Reinicio con evento visto | mismo id | Sin alerta | `[VERIFY: tests/test_state.py:39]` |
| TC-002.4 | CA-002.4 | negativo | Cursor hacia atrás | T-1000 | Conserva T | `[VERIFY: tests/test_state.py:52]` |
| TC-002.5 | CA-002.5 | negativo | JSON corrupto | `"{{{"` | Arranca vacío | `[VERIFY: tests/test_state.py:86]` |
| TC-002.6 | CA-002.6 | borde | Escritura atómica | guardado | Un solo archivo | `[VERIFY: tests/test_state.py:94]` |
| TC-002.7 | CA-002.7 | borde | Entrada de 25 h | ts-25h | Podada | `[VERIFY: tests/test_state.py:72]` |
| TC-002.8 | CA-002.7 | feliz | Poda al registrar | register() | prune antes de save | `[VERIFY: tests/test_dedup.py:157]` |
| TC-002.9 | CA-002.7 | borde | Larga racha sin alertas nuevas | 0 registros en 48 h | Entradas viejas persisten (limitación aceptada, ADR-018) | escribir en v2 |
| TC-002.10 | CA-002.8 | feliz | Caché de ubicación | ubicación detectada | Sin llamada a la API | `[VERIFY: tests/test_app.py:136]` |

## Dependencias

- **Requiere**: HU-001 (modelos persistidos)
- **Habilita**: HU-006, HU-010, HU-016, HU-022

## Notas para la v2

TC-002.9 documenta la limitación aceptada en ADR-018: sin alertas nuevas no hay poda. Es
inocua (tampoco crece nada), pero conviene un test que la fije como comportamiento
esperado y no como sorpresa. Ver también la lección 2 de `03-EVOLUCION.md`: este es el
caso que demuestra que un test unitario verde no garantiza que la función se ejecute.
