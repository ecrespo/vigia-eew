# HU-014: Autoarranque multiplataforma

> **Cluster de origen:** Fase 6 · **Commits:** 1 `[COMMITS: 5b79ff1]`
> **Período:** 2026-07-03 · **Era:** Era 0 — Fundación

## Historia

**Como** usuario que quiere estar protegido siempre `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** que el agente arranque solo al iniciar sesión
**Para** no depender de acordarme de lanzarlo

## Contexto de la implementación original

`create_installer` `[VERIFY: src/vigia_eew/autostart/__init__.py:54]` elige el mecanismo
**nativo** de cada sistema tras una interfaz común
`[VERIFY: src/vigia_eew/autostart/__init__.py:28]`: systemd `--user` en Linux
`[VERIFY: src/vigia_eew/autostart/linux_systemd.py:57]`, LaunchAgent en macOS
`[VERIFY: src/vigia_eew/autostart/macos_launchagent.py:45]` y tarea programada en Windows
`[VERIFY: src/vigia_eew/autostart/windows_task.py:55]`.

Escribir un supervisor propio multiplataforma habría duplicado lo que los tres sistemas ya
hacen bien, y además necesitaría algo que lo arrancara a él.

El patrón de testeo clave: cada instalador separa **generar** su artefacto (unit, plist,
línea de `schtasks`) de **ejecutar** el comando del sistema. Lo generado es una función
pura testeable en cualquier plataforma; solo la ejecución necesita el SO real.

## Criterios de aceptación

### CA-014.1: Se elige el instalador correcto por sistema operativo
```gherkin
Dado un sistema operativo concreto
Cuando se crea el instalador
Entonces se obtiene el de systemd, LaunchAgent o schtasks según corresponda
```
*Fuente: tests `[VERIFY: tests/test_autostart.py:29]`,
`[VERIFY: tests/test_autostart.py:33]`, `[VERIFY: tests/test_autostart.py:37]`,
`[VERIFY: tests/test_autostart.py:41]`*

### CA-014.2: Un sistema no soportado falla con claridad
```gherkin
Dado un sistema operativo no contemplado
Cuando se crea el instalador
Entonces falla con un mensaje explícito
```
*Fuente: test `[VERIFY: tests/test_autostart.py:48]`*

### CA-014.3: El comando de arranque apunta al ejecutable correcto
```gherkin
Dado una instalación normal o un binario congelado
Cuando se construye el comando de autoarranque
Entonces apunta al CLI instalado, o solo al ejecutable si está congelado
```
*Fuente: tests `[VERIFY: tests/test_autostart.py:15]`,
`[VERIFY: tests/test_autostart.py:21]` — en un bundle PyInstaller no existe un
intérprete separado al que invocar*

### CA-014.4: La unidad systemd contiene ExecStart y WantedBy
```gherkin
Dado la generación de la unidad de usuario
Cuando se produce su contenido
Entonces incluye ExecStart y el WantedBy correcto
```
*Fuente: test `[VERIFY: tests/test_autostart_linux.py:28]`*

### CA-014.5: El plist de macOS contiene Label, args y RunAtLoad
```gherkin
Dado la generación del LaunchAgent
Cuando se produce el plist
Entonces incluye Label, ProgramArguments y RunAtLoad
```
*Fuente: test `[VERIFY: tests/test_autostart_macos.py:31]`*

### CA-014.6: La tarea de Windows se crea con disparador de inicio de sesión
```gherkin
Dado la generación del comando de schtasks
Cuando se produce la línea de comando
Entonces usa el disparador ONLOGON y el nombre de tarea previsto
```
*Fuente: tests `[VERIFY: tests/test_autostart_windows.py:40]`,
`[VERIFY: tests/test_autostart_windows.py:74]`*

### CA-014.7: Instalar escribe el artefacto y lo activa
```gherkin
Dado una instalación de autoarranque
Cuando se ejecuta
Entonces se escribe el artefacto y se invoca el comando de activación del sistema
```
*Fuente: tests `[VERIFY: tests/test_autostart_linux.py:39]`,
`[VERIFY: tests/test_autostart_macos.py:41]`,
`[VERIFY: tests/test_autostart_windows.py:57]`*

### CA-014.8: Desinstalar revierte por completo
```gherkin
Dado un autoarranque instalado
Cuando se desinstala
Entonces se desactiva y se elimina el artefacto
```
*Fuente: tests `[VERIFY: tests/test_autostart_linux.py:59]`,
`[VERIFY: tests/test_autostart_macos.py:58]`,
`[VERIFY: tests/test_autostart_windows.py:65]`*

### CA-014.9: Desinstalar sin haber instalado no falla
```gherkin
Dado que no hay autoarranque instalado
Cuando se desinstala
Entonces la operación termina sin error
```
*Fuente: tests `[VERIFY: tests/test_autostart_linux.py:70]`,
`[VERIFY: tests/test_autostart_macos.py:69]` — operación idempotente*

### CA-014.10: Se puede consultar si está instalado
```gherkin
Dado un estado cualquiera
Cuando se consulta is_installed
Entonces refleja la presencia real del artefacto
```
*Fuente: tests `[VERIFY: tests/test_autostart_linux.py:52]`,
`[VERIFY: tests/test_autostart_macos.py:51]`*

### CA-014.11: El subproceso del sistema recibe un entorno saneado
```gherkin
Dado un binario congelado que lanza systemctl
Cuando se invoca el comando del sistema
Entonces el entorno va saneado de variables del bundle
```
*Fuente: test `[VERIFY: tests/test_subprocess_env.py:73]` — ver HU-015*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-014.1 | CA-014.1 | feliz | Linux | platform=linux | SystemdInstaller | `[VERIFY: tests/test_autostart.py:29]` |
| TC-014.2 | CA-014.1 | feliz | macOS | platform=darwin | LaunchAgentInstaller | `[VERIFY: tests/test_autostart.py:33]` |
| TC-014.3 | CA-014.1 | feliz | Windows | platform=win32 | SchtasksInstaller | `[VERIFY: tests/test_autostart.py:37]` |
| TC-014.4 | CA-014.2 | negativo | SO desconocido | otro | Error claro | `[VERIFY: tests/test_autostart.py:48]` |
| TC-014.5 | CA-014.3 | borde | Binario congelado | frozen=True | Solo ejecutable | `[VERIFY: tests/test_autostart.py:21]` |
| TC-014.6 | CA-014.4 | feliz | Unit systemd | generación | ExecStart+WantedBy | `[VERIFY: tests/test_autostart_linux.py:28]` |
| TC-014.7 | CA-014.5 | feliz | Plist macOS | generación | Label+RunAtLoad | `[VERIFY: tests/test_autostart_macos.py:31]` |
| TC-014.8 | CA-014.6 | feliz | schtasks | generación | ONLOGON | `[VERIFY: tests/test_autostart_windows.py:40]` |
| TC-014.9 | CA-014.7 | feliz | Instalación Linux | install | Escribe + enable | `[VERIFY: tests/test_autostart_linux.py:39]` |
| TC-014.10 | CA-014.8 | feliz | Desinstalación | uninstall | Disable + borra | `[VERIFY: tests/test_autostart_linux.py:59]` |
| TC-014.11 | CA-014.9 | borde | Desinstalar sin instalar | limpio | Sin error | `[VERIFY: tests/test_autostart_linux.py:70]` |
| TC-014.12 | CA-014.10 | feliz | Consulta de estado | instalado/no | Refleja realidad | `[VERIFY: tests/test_autostart_linux.py:52]` |
| TC-014.13 | CA-014.11 | borde | Entorno saneado | frozen | Sin vars del bundle | `[VERIFY: tests/test_subprocess_env.py:73]` |
| TC-014.14 | CA-014.7 | negativo | systemctl ausente o falla | comando inexistente | Error informativo, no traza cruda | **escribir en v2** |

## Dependencias

- **Requiere**: HU-013 (el CLI que se autoarranca), HU-015 (rutas del binario congelado)
- **Habilita**: uso desatendido del agente

## Notas para la v2

El patrón "generar puro / ejecutar impuro" es el más reutilizable de todo el repo: 22
tests cubren tres sistemas operativos desde una sola máquina Linux. Replicarlo en
cualquier integración con el SO.

TC-014.14 es el hueco: no hay cobertura de qué ve el usuario cuando el comando del sistema
no existe o devuelve error.
