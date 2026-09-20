# HU-004: Observabilidad — logging estructurado y auditable

> **Cluster de origen:** Fase 1 · **Commits:** 1 `[COMMITS: b5c5371]`
> **Período:** 2026-06-28 · **Era:** Era 0 — Fundación

## Historia

**Como** usuario o soporte que investiga por qué el agente no alertó un sismo `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** un registro estructurado de conexiones, polls, filtrados, alertas y reconocimientos
**Para** poder reconstruir qué pasó sin instrumentar el proceso en vivo

## Contexto de la implementación original

`configure_logging` `[VERIFY: src/vigia_eew/logging_conf.py:36]` monta salida a consola y
a archivo rotativo, con un formateador que emite timestamps en **UTC**
`[VERIFY: src/vigia_eew/logging_conf.py:23]` — coherente con la invariante de datos de
HU-001, para que los logs se puedan correlacionar con los tiempos de los eventos sin
conversión mental. La ruta del archivo se resuelve por SO
`[VERIFY: src/vigia_eew/logging_conf.py:29]`.

El estilo es clave=valor en todo el código (`ip_location_detected name=%s`
`[VERIFY: src/vigia_eew/app.py:266]`, `funvisis_seeded count=%d`
`[VERIFY: src/vigia_eew/ingest/rest_funvisis.py:102]`), lo que hace los logs grepeables
sin parser.

## Criterios de aceptación

### CA-004.1: Los timestamps del log están en UTC
```gherkin
Dado un registro emitido en cualquier zona del sistema
Cuando se formatea la línea de log
Entonces el timestamp está en UTC
```
*Fuente: código `[VERIFY: src/vigia_eew/logging_conf.py:23]` — decisión deliberada para
correlacionar con `time_utc` de los eventos*

### CA-004.2: El log va a consola y a archivo rotativo
```gherkin
Dado el arranque del agente
Cuando se configura el logging
Entonces se registran ambos handlers y el archivo rota por tamaño
```
*Fuente: código `[VERIFY: src/vigia_eew/logging_conf.py:36]`*

### CA-004.3: La ruta del log se resuelve por sistema operativo
```gherkin
Dado un sistema operativo cualquiera de los soportados
Cuando se pide la ruta por defecto del log
Entonces apunta al directorio de datos del usuario de ese SO
```
*Fuente: código `[VERIFY: src/vigia_eew/logging_conf.py:29]`*

### CA-004.4: Los reconocimientos de alerta quedan registrados
```gherkin
Dado que el usuario reconoce una alerta
Cuando se procesa el acknowledge
Entonces queda traza en el log y en el estado persistido
```
*Fuente: código `[VERIFY: src/vigia_eew/state.py:89]`, test
`[VERIFY: tests/test_state.py:62]` — es la traza de auditoría del objetivo del producto:
poder demostrar qué vio el usuario y cuándo*

### CA-004.5: Los eventos operativos relevantes se registran
```gherkin
Dado el ciclo normal del agente
Cuando ocurre una conexión, reconexión, poll, filtrado o alerta
Entonces cada uno emite una línea clave=valor identificable
```
*Fuente: código `[VERIFY: src/vigia_eew/ingest/rest_funvisis.py:102]`,
`[VERIFY: src/vigia_eew/app.py:266]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-004.1 | CA-004.1 | feliz | Log emitido en TZ no-UTC | TZ=America/Caracas | Timestamp UTC | **escribir en v2** |
| TC-004.2 | CA-004.2 | feliz | Configuración de handlers | config default | Consola + archivo | **escribir en v2** |
| TC-004.3 | CA-004.2 | borde | Rotación al superar el tamaño | archivo grande | Rota sin perder líneas | **escribir en v2** |
| TC-004.4 | CA-004.3 | feliz | Ruta por SO | Linux/macOS/Windows | Directorio de datos correcto | **escribir en v2** |
| TC-004.5 | CA-004.4 | feliz | Reconocimiento | acknowledge | Marcado en estado | `[VERIFY: tests/test_state.py:62]` |
| TC-004.6 | CA-004.2 | negativo | Directorio de log no escribible | permiso denegado | El agente arranca igual | **escribir en v2** |

## Dependencias

- **Requiere**: HU-003 (sección `[logging]` de la configuración)
- **Habilita**: soporte y diagnóstico de todas las demás

## Notas para la v2

**Esta es la HU con menor cobertura de todo el kit**: no existe `tests/test_logging_conf.py`.
El módulo se ejercita indirectamente al arrancar la app, pero ninguna de sus decisiones
—UTC, rotación, ruta por SO, tolerancia a un directorio no escribible— tiene test propio.

TC-004.6 es el más importante de la lista: si `configure_logging` lanzara ante un
directorio no escribible, tumbaría el arranque del agente por un fallo puramente
accesorio, violando el patrón de aislamiento de fallos que el resto del sistema respeta.
No hay evidencia de que ese caso esté cubierto ni manejado.
