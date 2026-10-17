# HU-005: Arrancar el agente y poder probarlo sin esperar un terremoto

> **Cluster de origen:** C-06 · **Commits:** 1 `[COMMITS: 4fb49d0]`
> **Período:** 2026-06-28 · **Era:** v0.1.0

## Historia

**Como** usuario que acaba de instalar el agente
**Quiero** arrancarlo con un comando y poder ver una alerta de prueba sin red
**Para** comprobar que el sonido, la ventana y la notificación funcionan en mi máquina antes de confiar en ellos

## Contexto de la implementación original

853 líneas que unen todo lo anterior. `Application`
`[VERIFY: src/vigia_eew/app.py:54]` es la raíz de composición; `Processor`
`[VERIFY: src/vigia_eew/pipeline/processor.py:32]` conecta la cola con el controlador; `main`
`[VERIFY: src/vigia_eew/cli.py:56]` interpreta los flags. `simulate()`
`[VERIFY: src/vigia_eew/app.py:359]` inyecta un evento fijo (M6.1 La Guaira)
`[VERIFY: src/vigia_eew/simulation.py:24]` **sin tocar la red**.

## Criterios de aceptación

### CA-005.1: Sin flags, el agente ejecuta el modo normal
```gherkin
Dado el comando vigia-eew sin argumentos
Cuando se invoca
Entonces se ejecuta el agente completo
Y con --simulate se ejecuta la simulación en su lugar
```
*Fuente: tests `[VERIFY: tests/test_cli.py:59]`, `[VERIFY: tests/test_cli.py:53]`*

### CA-005.2: La simulación no requiere red
```gherkin
Dado el modo --simulate
Cuando se ejecuta
Entonces se muestra una alerta con el evento simulado M6.1 de La Guaira
Y no se resuelve la ubicación por IP ni se abre ninguna conexión a las fuentes
```
*Fuente: tests `[VERIFY: tests/test_simulation.py:11]`, `[VERIFY: tests/test_app.py:96]`; e2e `[VERIFY: tests/test_resilience.py:94]`*

### CA-005.3: `--check-config` valida y sale sin efectos
```gherkin
Dado el flag --check-config
Cuando se ejecuta
Entonces se valida la configuración y el proceso termina
Y no se construye la aplicación ni se siembra ningún archivo
```
*Fuente: tests `[VERIFY: tests/test_cli.py:81]`, `[VERIFY: tests/test_cli.py:130]`*

### CA-005.4: Una ruta de configuración inexistente falla claramente
```gherkin
Dado --config apuntando a un archivo que no existe
Cuando se invoca el CLI
Entonces el proceso termina con error explícito y no arranca el agente
```
*Fuente: test `[VERIFY: tests/test_cli.py:88]`*

### CA-005.5: El pipeline solo alerta de lo relevante y nuevo
```gherkin
Dado un evento relevante que nunca fue alertado
Cuando el procesador lo trata
Entonces se dispara una alerta
Y un evento fuera de radio, uno duplicado o un RawMessage inválido no producen alerta
Y un update refresca sin alertar de nuevo
```
*Fuente: tests `[VERIFY: tests/test_processor.py:63]`, `[VERIFY: tests/test_processor.py:70]`, `[VERIFY: tests/test_processor.py:77]`, `[VERIFY: tests/test_processor.py:84]`, `[VERIFY: tests/test_processor.py:92]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-005.1 | CA-005.1 | feliz | sin argumentos | `vigia-eew` | `execute()` invocado | `[VERIFY: tests/test_cli.py:59]` |
| TC-005.2 | CA-005.2 | feliz | simulación | `--simulate` | alerta M6.1 La Guaira | `[VERIFY: tests/test_simulation.py:11]` |
| TC-005.3 | CA-005.2 | borde | simulación sin red | sin conectividad | funciona igual | `[VERIFY: tests/test_app.py:96]` |
| TC-005.4 | CA-005.3 | feliz | validar config | `--check-config` | sale sin construir app | `[VERIFY: tests/test_cli.py:81]` |
| TC-005.5 | CA-005.4 | negativo | ruta inválida | `--config /no/existe` | error explícito | `[VERIFY: tests/test_cli.py:88]` |
| TC-005.6 | CA-005.5 | feliz | evento relevante | M5 a 50 km | alerta | `[VERIFY: tests/test_processor.py:63]` |
| TC-005.7 | CA-005.5 | negativo | RawMessage inválido | payload roto | sin alerta ni excepción | `[VERIFY: tests/test_processor.py:77]` |
| TC-005.8 | CA-005.1 | borde | `--version` | flag | salida limpia código 0 | `[VERIFY: tests/test_cli.py:136]` |

## Dependencias

- **Requiere**: HU-001, HU-002, HU-003, HU-004
- **Habilita**: HU-006, HU-007, HU-011, HU-013

## Notas para la v2

`app.py`, `config.py` y `cli.py` fueron tocados por casi todas las features posteriores (10, 10 y
9 veces). Es el coste esperado de una raíz de composición explícita, pero la v2 puede reducirlo con
un registro declarativo de fuentes y flags en lugar de tres puntos de edición manual por feature.
