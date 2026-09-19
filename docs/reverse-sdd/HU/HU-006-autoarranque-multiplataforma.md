# HU-006: Que el agente arranque solo al encender el equipo

> **Cluster de origen:** C-07 · **Commits:** 1 `[COMMITS: 5b79ff1]`
> **Período:** 2026-07-03 · **Era:** v0.1.0

## Historia

**Como** usuario que quiere protección continua
**Quiero** instalar el arranque automático con un comando, en Linux, macOS o Windows
**Para** no depender de acordarme de lanzar el agente cada vez que enciendo el equipo

## Contexto de la implementación original

680 líneas con tres instaladores nativos tras una interfaz común: unidad systemd `--user`
`[VERIFY: src/vigia_eew/autostart/linux_systemd.py:57]`, LaunchAgent
`[VERIFY: src/vigia_eew/autostart/macos_launchagent.py:45]` y tarea programada
`[VERIFY: src/vigia_eew/autostart/windows_task.py:55]`. La fábrica elige por plataforma
`[VERIFY: src/vigia_eew/autostart/__init__.py:1]`. La generación de la unidad, el plist y el
comando `schtasks` son **funciones puras**, lo que permite verificarlas sin invocar el SO.

## Criterios de aceptación

### CA-006.1: Cada plataforma obtiene su instalador nativo
```gherkin
Dada la plataforma del sistema
Cuando se solicita un instalador de autoarranque
Entonces se devuelve el instalador de systemd en Linux, LaunchAgent en macOS o schtasks en Windows
Y en un sistema no soportado el fallo es explícito
```
*Fuente: tests `[VERIFY: tests/test_autostart.py:29]`, `[VERIFY: tests/test_autostart.py:33]`, `[VERIFY: tests/test_autostart.py:37]`, `[VERIFY: tests/test_autostart.py:48]`*

### CA-006.2: Los artefactos generados contienen lo necesario para arrancar en sesión
```gherkin
Dado el instalador de la plataforma
Cuando se genera el artefacto de arranque
Entonces la unidad systemd contiene ExecStart y WantedBy
Y el plist contiene Label, ProgramArguments y RunAtLoad
Y el comando schtasks se registra con disparador ONLOGON
```
*Fuente: tests `[VERIFY: tests/test_autostart_linux.py:28]`, `[VERIFY: tests/test_autostart_macos.py:31]`, `[VERIFY: tests/test_autostart_windows.py:40]`*

### CA-006.3: Instalar deja el arranque activo; desinstalar lo revierte
```gherkin
Dado un sistema sin autoarranque instalado
Cuando se ejecuta la instalación
Entonces el artefacto queda escrito y habilitado
Y al desinstalar se deshabilita y se elimina
Y desinstalar sin haber instalado no falla
```
*Fuente: tests `[VERIFY: tests/test_autostart_linux.py:39]`, `[VERIFY: tests/test_autostart_linux.py:59]`, `[VERIFY: tests/test_autostart_linux.py:70]`, `[VERIFY: tests/test_autostart_macos.py:69]`*

### CA-006.4: El comando registrado apunta al ejecutable correcto
```gherkin
Dado un agente instalado como paquete Python
Cuando se calcula el comando de arranque
Entonces apunta al módulo cli
Y si el agente corre como binario congelado, el comando usa solo el ejecutable
```
*Fuente: tests `[VERIFY: tests/test_autostart.py:15]`, `[VERIFY: tests/test_autostart.py:21]`*

### CA-006.5: Los subprocesos del sistema reciben un entorno saneado
```gherkin
Dado un agente ejecutándose como binario PyInstaller onefile
Cuando lanza un binario del sistema
Entonces LD_LIBRARY_PATH (y DYLD_LIBRARY_PATH en macOS) se restauran o eliminan
Y el entorno devuelto es una copia, no os.environ
```
*Fuente: fix `[COMMITS: a02607f]` — las librerías empaquetadas rompían los binarios del sistema. Tests `[VERIFY: tests/test_subprocess_env.py:23]`, `[VERIFY: tests/test_subprocess_env.py:42]`, `[VERIFY: tests/test_subprocess_env.py:61]`, `[VERIFY: tests/test_subprocess_env.py:73]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-006.1 | CA-006.1 | feliz | Linux | `sys.platform=linux` | SystemdInstaller | `[VERIFY: tests/test_autostart.py:29]` |
| TC-006.2 | CA-006.1 | negativo | SO no soportado | plataforma ficticia | error claro | `[VERIFY: tests/test_autostart.py:48]` |
| TC-006.3 | CA-006.2 | feliz | unidad systemd | generación pura | contiene ExecStart/WantedBy | `[VERIFY: tests/test_autostart_linux.py:28]` |
| TC-006.4 | CA-006.3 | feliz | instalar en Linux | install() | unidad escrita y habilitada | `[VERIFY: tests/test_autostart_linux.py:39]` |
| TC-006.5 | CA-006.3 | borde | desinstalar sin instalar | uninstall() | sin error | `[VERIFY: tests/test_autostart_linux.py:70]` |
| TC-006.6 | CA-006.4 | borde | binario congelado | `sys.frozen` | solo el ejecutable | `[VERIFY: tests/test_autostart.py:21]` |
| TC-006.7 | CA-006.5 | negativo | onefile sin ORIG | env sin variable original | LD_LIBRARY_PATH eliminado | `[VERIFY: tests/test_subprocess_env.py:23]` |
| TC-006.8 | CA-006.5 | borde | runner de systemd | invocación real simulada | env saneado propagado | `[VERIFY: tests/test_subprocess_env.py:73]` |

## Dependencias

- **Requiere**: HU-005 (el CLI expone `--install-autostart`)
- **Habilita**: HU-007

## Notas para la v2

La separación entre generación pura y efecto de sistema es el patrón más reutilizable del
repositorio: permitió cubrir tres plataformas con tests deterministas sin ninguna de ellas
disponible. Mantenerlo tal cual.
