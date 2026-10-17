# HU-001: Contrato de evento sísmico, configuración y estado persistente

> **Cluster de origen:** C-02 · **Commits:** 1 `[COMMITS: b5c5371]`
> **Período:** 2026-06-28 · **Era:** v0.1.0

## Historia

**Como** desarrollador del agente `[INFERIDO: los commits no nombran persona; se deduce de que la capacidad no es visible al usuario final]`
**Quiero** un contrato de datos único, una configuración validada y un estado que sobreviva al reinicio
**Para** que las cuatro fuentes converjan sin lógica específica por fuente y el usuario no vuelva a recibir alertas ya atendidas

## Contexto de la implementación original

Primera fase de producción del proyecto: 841 líneas que crean `models.py`, `config.py`, `state.py`,
`geo.py` y `logging_conf.py` junto con sus tests. `SeismicEvent` `[VERIFY: src/vigia_eew/models.py:51]`
es el único payload que cruza capas; `Settings` `[VERIFY: src/vigia_eew/config.py:142]` valida el
TOML con pydantic; `StateStore` `[VERIFY: src/vigia_eew/state.py:33]` escribe JSON atómico.

## Criterios de aceptación

### CA-001.1: Todo instante interno es UTC consciente de zona
```gherkin
Dado un evento sísmico con un datetime sin zona horaria
Cuando se construye el SeismicEvent
Entonces la construcción falla con error de validación
Y un datetime con offset distinto de UTC se convierte a UTC
```
*Fuente: tests `[VERIFY: tests/test_models.py:48]` (`test_naive_time_is_rejected`) y `[VERIFY: tests/test_models.py:53]` (`test_time_is_converted_to_utc`); código `[VERIFY: src/vigia_eew/models.py:25]`*

### CA-001.2: La severidad se deriva de la magnitud según umbrales configurables
```gherkin
Dado unos umbrales de severidad en config.toml
Cuando se clasifica un evento por su magnitud
Entonces la severidad resultante respeta esos umbrales y no los valores por defecto
```
*Fuente: tests `[VERIFY: tests/test_models.py:77]` y `[VERIFY: tests/test_normalize.py:131]`; código `[VERIFY: src/vigia_eew/models.py:38]`*

### CA-001.3: El estado sobrevive al reinicio sin re-alertar
```gherkin
Dado un evento ya alertado y persistido en state.json
Cuando el agente se reinicia y carga el estado
Entonces ese mismo evento no vuelve a alertarse
```
*Fuente: test `[VERIFY: tests/test_state.py:39]` (`test_no_realert_after_restart`)*

### CA-001.4: La escritura del estado es atómica y tolerante a corrupción
```gherkin
Dado un state.json corrupto o inexistente
Cuando el agente carga el estado
Entonces arranca con estado vacío en lugar de fallar
Y tras guardar queda exactamente un archivo, sin temporales huérfanos
```
*Fuente: tests `[VERIFY: tests/test_state.py:86]` y `[VERIFY: tests/test_state.py:94]`*

### CA-001.5: Los cursores solo avanzan
```gherkin
Dado un cursor USGS persistido en el instante T
Cuando se intenta actualizarlo con un instante anterior a T
Entonces el cursor conserva su valor
```
*Fuente: test `[VERIFY: tests/test_state.py:52]` (`test_cursor_only_advances`)*

### CA-001.6: Configuración inválida falla de forma explícita
```gherkin
Dado un config.toml con una sección de severidad inválida
Cuando se carga la configuración
Entonces la carga falla con un error de validación claro
Y una ruta de configuración explícita inexistente también falla
```
*Fuente: tests `[VERIFY: tests/test_config.py:122]` y `[VERIFY: tests/test_config.py:117]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-001.1 | CA-001.1 | feliz | datetime UTC válido | `2026-06-28T10:00:00+00:00` | evento construido | `[VERIFY: tests/test_models.py:36]` |
| TC-001.2 | CA-001.1 | borde | offset no UTC | `…+02:00` | convertido a UTC | `[VERIFY: tests/test_models.py:53]` |
| TC-001.3 | CA-001.1 | negativo | datetime naive | sin tz | ValidationError | `[VERIFY: tests/test_models.py:48]` |
| TC-001.4 | CA-001.2 | feliz | M6.1 con umbrales por defecto | mag 6.1 | severidad crítica | `[VERIFY: tests/test_models.py:77]` |
| TC-001.5 | CA-001.2 | borde | umbrales personalizados | config alterada | severidad según config | `[VERIFY: tests/test_normalize.py:131]` |
| TC-001.6 | CA-001.3 | feliz | reinicio con id alertado | state.json previo | sin re-alerta | `[VERIFY: tests/test_state.py:39]` |
| TC-001.7 | CA-001.4 | negativo | JSON corrupto | bytes inválidos | estado vacío, sin excepción | `[VERIFY: tests/test_state.py:86]` |
| TC-001.8 | CA-001.5 | negativo | cursor retrocedido | T-1h | cursor intacto | `[VERIFY: tests/test_state.py:52]` |
| TC-001.9 | CA-001.6 | negativo | severidad inválida | TOML malformado | ValidationError | `[VERIFY: tests/test_config.py:122]` |
| TC-001.10 | CA-001.1 | negativo | lat/lon fuera de rango | lat 120 | ValidationError | `[VERIFY: tests/test_models.py:62]` |

## Dependencias

- **Requiere**: ninguna (es la base)
- **Habilita**: HU-002, HU-003, HU-004, HU-008, HU-016

## Notas para la v2

`prune()` y `MAX_AGE` nacieron aquí con test propio pero sin ninguna ruta de ejecución que los
llamara; el defecto tardó 14 fases en corregirse (HU-016). En la v2, el acotamiento del estado es
parte de este contrato desde el principio, no un añadido posterior.
