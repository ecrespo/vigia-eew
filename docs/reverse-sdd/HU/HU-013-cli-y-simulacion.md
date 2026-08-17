# HU-013: CLI, ensamblaje del agente y modo simulación

> **Cluster de origen:** Fase 5 · **Commits:** 1 `[COMMITS: 4fb49d0]`
> **Período:** 2026-06-28 · **Era:** Era 0 — Fundación

## Historia

**Como** usuario que acaba de instalar el agente `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** poder comprobar que la alerta realmente aparece en mi máquina
**Para** confiar en que funcionará cuando ocurra un sismo de verdad

## Contexto de la implementación original

`main` `[VERIFY: src/vigia_eew/cli.py:56]` es el punto de entrada de consola declarado en
`pyproject.toml` `[VERIFY: pyproject.toml:50]`; `Application`
`[VERIFY: src/vigia_eew/app.py:54]` ensambla todo y expone tres modos: `execute()` (agente
completo), `run_tui()` (HU-019) y `simulate()`.

**`--simulate` nunca toca la red** `[VERIFY: src/vigia_eew/app.py:360]`: inyecta un evento
fijo (M6.1 La Guaira) `[VERIFY: src/vigia_eew/simulation.py:24]` sin arrancar el
supervisor ni resolver ubicación por IP. Esa restricción es deliberada — el modo existe
para verificar que la alerta aparece, y fallaría justo en la situación en que alguien lo
está probando (sin conectividad, recién instalado).

`--check-config` valida y sale sin construir la aplicación
`[VERIFY: tests/test_cli.py:81]`.

## Criterios de aceptación

### CA-013.1: Sin flags, arranca el agente completo
```gherkin
Dado la invocación sin flags
Cuando corre el CLI
Entonces se ejecuta el agente completo
```
*Fuente: test `[VERIFY: tests/test_cli.py:59]`*

### CA-013.2: `--simulate` inyecta un evento sin red
```gherkin
Dado la invocación con --simulate
Cuando corre el CLI
Entonces se muestra la alerta simulada sin contactar ninguna fuente
```
*Fuente: tests `[VERIFY: tests/test_cli.py:53]`,
`[VERIFY: tests/test_app.py:96]` (no llama a geoloc)*

### CA-013.3: El evento simulado es coherente y crítico
```gherkin
Dado el evento de simulación
Cuando se construye
Entonces es M6.1 en La Guaira, severidad critical, con tiempo tz-aware
       y distancia calculada desde la referencia
```
*Fuente: tests `[VERIFY: tests/test_simulation.py:11]`,
`[VERIFY: tests/test_simulation.py:20]`, `[VERIFY: tests/test_simulation.py:25]`,
`[VERIFY: tests/test_simulation.py:37]`*

### CA-013.4: La distancia simulada varía con la referencia
```gherkin
Dado una referencia lejana
Cuando se construye el evento simulado
Entonces la distancia crece en consecuencia
```
*Fuente: test `[VERIFY: tests/test_simulation.py:31]`*

### CA-013.5: `--tui` selecciona el frontend de terminal
```gherkin
Dado --tui, con o sin --simulate
Cuando corre el CLI
Entonces se lanza el dashboard de terminal en el modo correspondiente
```
*Fuente: tests `[VERIFY: tests/test_cli.py:65]`, `[VERIFY: tests/test_cli.py:73]`*

### CA-013.6: `--check-config` valida y sale sin efectos
```gherkin
Dado --check-config
Cuando corre el CLI
Entonces valida la configuración, no construye la aplicación
       y no siembra config.toml
```
*Fuente: tests `[VERIFY: tests/test_cli.py:81]`, `[VERIFY: tests/test_cli.py:130]`*

### CA-013.7: Una ruta de config inexistente falla claramente
```gherkin
Dado --config con una ruta que no existe
Cuando corre el CLI
Entonces falla con un error explícito
```
*Fuente: test `[VERIFY: tests/test_cli.py:88]`*

### CA-013.8: La ruta de config se propaga a la aplicación
```gherkin
Dado --config con una ruta válida
Cuando se construye la aplicación
Entonces recibe esa ruta, y no la ruta por defecto
```
*Fuente: test `[VERIFY: tests/test_cli.py:108]` — necesario para que "editar
configuración" de la bandeja abra el archivo realmente en uso (HU-017)*

### CA-013.9: Se detecta si la referencia es manual
```gherkin
Dado un config con o sin [reference]
Cuando arranca el CLI
Entonces informa a la aplicación si la referencia es manual
```
*Fuente: tests `[VERIFY: tests/test_cli.py:93]`, `[VERIFY: tests/test_cli.py:100]`*

### CA-013.10: Los flags de autoarranque delegan al instalador
```gherkin
Dado --install-autostart o --uninstall-autostart
Cuando corre el CLI
Entonces invoca la instalación o desinstalación y sale
```
*Fuente: tests `[VERIFY: tests/test_cli.py:154]`, `[VERIFY: tests/test_cli.py:162]`*

### CA-013.11: `--version` sale limpiamente
```gherkin
Dado --version
Cuando corre el CLI
Entonces imprime la versión y termina con código 0
```
*Fuente: test `[VERIFY: tests/test_cli.py:136]`*

### CA-013.12: El supervisor se arma con las fuentes habilitadas
```gherkin
Dado una configuración con una o varias fuentes deshabilitadas
Cuando se construye el supervisor
Entonces solo se registran las tareas de las fuentes activas
```
*Fuente: tests `[VERIFY: tests/test_app.py:46]`, `[VERIFY: tests/test_app.py:52]`,
`[VERIFY: tests/test_app.py:58]`, `[VERIFY: tests/test_app.py:64]`,
`[VERIFY: tests/test_app.py:70]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-013.1 | CA-013.1 | feliz | Sin flags | — | execute() | `[VERIFY: tests/test_cli.py:59]` |
| TC-013.2 | CA-013.2 | feliz | Simulación | --simulate | Alerta sin red | `[VERIFY: tests/test_cli.py:53]` |
| TC-013.3 | CA-013.2 | borde | Simulación sin conectividad | sin red | Funciona igual | `[VERIFY: tests/test_app.py:96]` |
| TC-013.4 | CA-013.3 | feliz | Evento simulado | — | M6.1 La Guaira, critical | `[VERIFY: tests/test_simulation.py:11]` |
| TC-013.5 | CA-013.4 | borde | Referencia lejana | Madrid | Distancia grande | `[VERIFY: tests/test_simulation.py:31]` |
| TC-013.6 | CA-013.5 | feliz | TUI | --tui | run_tui | `[VERIFY: tests/test_cli.py:65]` |
| TC-013.7 | CA-013.5 | feliz | TUI + simulación | ambos | run_tui(simulate) | `[VERIFY: tests/test_cli.py:73]` |
| TC-013.8 | CA-013.6 | feliz | Validar config | --check-config | Sin app, sin seed | `[VERIFY: tests/test_cli.py:81]` |
| TC-013.9 | CA-013.7 | negativo | Config inexistente | ruta falsa | Error claro | `[VERIFY: tests/test_cli.py:88]` |
| TC-013.10 | CA-013.8 | feliz | Propagación de ruta | --config X | App recibe X | `[VERIFY: tests/test_cli.py:108]` |
| TC-013.11 | CA-013.10 | feliz | Instalar autoarranque | flag | Invoca instalador | `[VERIFY: tests/test_cli.py:154]` |
| TC-013.12 | CA-013.11 | feliz | Versión | --version | Exit 0 | `[VERIFY: tests/test_cli.py:136]` |
| TC-013.13 | CA-013.12 | borde | Solo EMSC habilitado | resto off | Una sola tarea | `[VERIFY: tests/test_app.py:52]` |

## Dependencias

- **Requiere**: HU-003, HU-007, HU-011
- **Habilita**: HU-014, HU-017, HU-019

## Notas para la v2

`--simulate` sin red es una decisión a conservar literalmente: es la única forma que tiene
un usuario de comprobar la promesa del producto en su propia máquina antes de necesitarla.
Conviene además que la v2 lo use en el propio instalador, como paso de verificación
post-instalación.
