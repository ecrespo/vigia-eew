# HU-013: Tener un config.toml que editar desde el primer arranque

> **Cluster de origen:** C-15 · **Commits:** 1 `[COMMITS: a06f7a1]`
> **Período:** 2026-07-05 · **Era:** v0.3.0

## Historia

**Como** usuario que acaba de instalar el agente
**Quiero** que se cree un config.toml comentado en la ruta correcta de mi sistema
**Para** poder ajustar radio, magnitud y referencia sin buscar dónde va el archivo ni cómo se escribe

## Contexto de la implementación original

`seed_config_if_missing` `[VERIFY: src/vigia_eew/config.py:176]` copia la plantilla empaquetada
`[VERIFY: src/vigia_eew/config.py:162]` a la ruta por SO `[VERIFY: src/vigia_eew/config.py:157]`
en el primer arranque. La operación es **best effort**: un fallo de escritura no impide arrancar.
El commit también corrige la ruta que abre la acción "editar configuración" de la bandeja
`[VERIFY: src/vigia_eew/tray.py:52]`, que hasta entonces podía no coincidir con el archivo en uso.

## Criterios de aceptación

### CA-013.1: El primer arranque crea la configuración
```gherkin
Dado un sistema sin config.toml en la ruta por defecto
Cuando se arranca el agente sin --config
Entonces se crea el archivo, incluidos los directorios padre, a partir de la plantilla empaquetada
```
*Fuente: tests `[VERIFY: tests/test_config.py:142]`, `[VERIFY: tests/test_config.py:159]`, `[VERIFY: tests/test_cli.py:116]`*

### CA-013.2: Nunca se sobrescribe una configuración existente
```gherkin
Dado un config.toml ya presente
Cuando se ejecuta la siembra
Entonces el archivo se conserva intacto
```
*Fuente: tests `[VERIFY: tests/test_config.py:151]`, `[VERIFY: tests/test_tray.py:51]`*

### CA-013.3: Una ruta explícita desactiva la siembra
```gherkin
Dado el flag --config con una ruta concreta
Cuando arranca el agente
Entonces no se siembra la configuración por defecto
Y con --check-config tampoco se siembra
```
*Fuente: tests `[VERIFY: tests/test_cli.py:122]`, `[VERIFY: tests/test_cli.py:130]`*

### CA-013.4: Un fallo al sembrar no impide arrancar
```gherkin
Dado un sistema de archivos que rechaza la escritura
Cuando se intenta sembrar la configuración
Entonces el error se registra y el agente continúa con los valores por defecto
```
*Fuente: test `[VERIFY: tests/test_config.py:167]`*

### CA-013.5: La plantilla empaquetada es válida y deja la referencia comentada
```gherkin
Dada la plantilla incluida en el paquete
Cuando se parsea como TOML
Entonces es válida
Y su sección [reference] está comentada, de modo que un usuario que no la edite active la detección automática
```
*Fuente: tests `[VERIFY: tests/test_config.py:127]`, `[VERIFY: tests/test_config.py:135]`; relación con HU-008*

### CA-013.6: Se sabe si la referencia es manual antes de arrancar
```gherkin
Dado un config.toml con o sin sección [reference]
Cuando el CLI evalúa la configuración
Entonces informa correctamente si la referencia es manual
Y una ruta explícita inexistente no se considera referencia manual
```
*Fuente: tests `[VERIFY: tests/test_config.py:180]`, `[VERIFY: tests/test_config.py:186]`, `[VERIFY: tests/test_config.py:175]`, `[VERIFY: tests/test_config.py:192]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-013.1 | CA-013.1 | feliz | primer arranque | sin archivo | config creado | `[VERIFY: tests/test_config.py:142]` |
| TC-013.2 | CA-013.1 | borde | directorio padre ausente | ruta profunda | se crean los padres | `[VERIFY: tests/test_config.py:142]` |
| TC-013.3 | CA-013.2 | borde | config existente | archivo con cambios | sin sobrescribir | `[VERIFY: tests/test_config.py:151]` |
| TC-013.4 | CA-013.3 | borde | `--config` explícito | ruta dada | sin siembra | `[VERIFY: tests/test_cli.py:122]` |
| TC-013.5 | CA-013.4 | negativo | FS de solo lectura | OSError | arranque igualmente | `[VERIFY: tests/test_config.py:167]` |
| TC-013.6 | CA-013.5 | feliz | plantilla empaquetada | parseo TOML | válida | `[VERIFY: tests/test_config.py:127]` |
| TC-013.7 | CA-013.5 | borde | sección reference | plantilla | comentada | `[VERIFY: tests/test_config.py:135]` |
| TC-013.8 | CA-013.6 | negativo | ruta explícita inexistente | `--config /no/existe` | no es manual | `[VERIFY: tests/test_config.py:175]` |

## Dependencias

- **Requiere**: HU-001 (config), HU-005 (CLI)
- **Habilita**: HU-008 (la plantilla con `[reference]` comentada es lo que activa la detección por IP)

## Notas para la v2

La siembra y la lectura conviven en `config.py`, que por lo demás es una función pura de
lectura/validación. En la v2 conviene separar "materializar la configuración inicial" (efecto de
disco) de "cargar y validar" (puro), como ya se hizo con la resolución de ubicación en `app.py`.
