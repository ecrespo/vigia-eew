# HU-017: Ícono de bandeja del sistema

> **Cluster de origen:** Fase 10 (RF-34) · **Commits:** 1 `[COMMITS: fb3fe14]`
> **Período:** 2026-07-04 · **Era:** Era 2 — Contexto del usuario

## Historia

**Como** usuario que tiene el agente corriendo en segundo plano `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** ver su estado y poder pausarlo, editar la config o salir sin usar la terminal
**Para** controlarlo como cualquier otra aplicación de escritorio

## Contexto de la implementación original

`TrayIcon` `[VERIFY: src/vigia_eew/tray.py:110]` corre `pystray` en un **hilo aparte**,
dejando a Tkinter como dueño único del hilo principal (la decisión de HU-011/arquitectura
no cambia). Los callbacks que pueden tocar Tk se reprograman al hilo de Tk con
`root.after(0, ...)`; los que no —editar config, que solo lanza un subproceso— corren
directamente `[VERIFY: src/vigia_eew/app.py:222]`.

`AgentState` `[VERIFY: src/vigia_eew/agent_state.py:14]` es una instantánea protegida por
lock que **tres hilos distintos** tocan: el ingestor WS la actualiza al conectar/reconectar
(hilo asyncio), el controlador al mostrar alerta (hilo Tk), y el ícono la lee (su propio
hilo).

Todo el componente es **best-effort**: bajo GNOME+Wayland sin extensión de AppIndicator,
GNOME Shell simplemente no muestra iconos de bandeja legacy, y el agente debe seguir
funcionando sin él.

## Criterios de aceptación

### CA-017.1: El menú se arma con las acciones previstas
```gherkin
Dado la construcción del ícono
Cuando se ensambla el menú
Entonces incluye pausar/reanudar, editar configuración y salir
```
*Fuente: test `[VERIFY: tests/test_tray.py:81]`*

### CA-017.2: Un fallo del backend no propaga
```gherkin
Dado un entorno sin bandeja disponible o un pystray que lanza
Cuando se arranca el ícono
Entonces se registra una advertencia y el agente sigue corriendo
```
*Fuente: test `[VERIFY: tests/test_tray.py:121]` — cubre GNOME/Wayland sin extensión y
macOS, donde pystray exige el hilo principal por requisito de Cocoa*

### CA-017.3: El agente se importa sin display
```gherkin
Dado un host headless sin DISPLAY
Cuando se importa la aplicación
Entonces la importación no falla
```
*Fuente: test `[VERIFY: tests/test_tray.py:139]`, fix `[COMMITS: 651c024]` — sin esto, un
servidor sin entorno gráfico no podía ni arrancar el modo TUI*

### CA-017.4: "Editar configuración" abre el archivo realmente en uso
```gherkin
Dado que el agente se lanzó con --config explícito
Cuando el usuario elige editar configuración
Entonces se abre esa ruta, no la ruta por defecto
```
*Fuente: tests `[VERIFY: tests/test_app.py:205]`, `[VERIFY: tests/test_app.py:216]`*

### CA-017.5: El comando de apertura es el correcto por sistema
```gherkin
Dado cada sistema operativo soportado
Cuando se abre la configuración
Entonces se usa el mecanismo nativo de apertura de archivos
```
*Fuente: tests `[VERIFY: tests/test_tray.py:21]`, `[VERIFY: tests/test_tray.py:26]`,
`[VERIFY: tests/test_tray.py:31]`*

### CA-017.6: Editar crea el archivo si falta y nunca sobrescribe
```gherkin
Dado que config.toml no existe
Cuando se elige editar configuración
Entonces se crea desde plantilla; y si existía, se abre sin modificarlo
```
*Fuente: tests `[VERIFY: tests/test_tray.py:39]`, `[VERIFY: tests/test_tray.py:51]`*

### CA-017.7: Un fallo al abrir no rompe
```gherkin
Dado un error al lanzar el editor
Cuando se elige editar configuración
Entonces se registra y no se propaga
```
*Fuente: test `[VERIFY: tests/test_tray.py:62]`*

### CA-017.8: Pausar y reanudar se programan en el hilo de Tk
```gherkin
Dado una acción de pausa desde el menú de la bandeja
Cuando se ejecuta el callback
Entonces se reprograma en el hilo de Tkinter, no se ejecuta en el hilo del ícono
```
*Fuente: tests `[VERIFY: tests/test_app.py:181]`, `[VERIFY: tests/test_app.py:195]` —
Tk no es thread-safe; ejecutarlo desde el hilo del ícono produce fallos intermitentes*

### CA-017.9: El estado compartido refleja conexión y última alerta
```gherkin
Dado cambios de conexión y alertas mostradas
Cuando se consulta AgentState
Entonces refleja el estado actual y la última alerta
```
*Fuente: tests `[VERIFY: tests/test_agent_state.py:14]`,
`[VERIFY: tests/test_agent_state.py:22]`, `[VERIFY: tests/test_controller.py:118]`*

### CA-017.10: La bandeja se puede desactivar por configuración
```gherkin
Dado la bandeja deshabilitada en config
Cuando arranca el agente
Entonces no se construye el ícono
```
*Fuente: test `[VERIFY: tests/test_app.py:170]`*

### CA-017.11: Parar el ícono espera a su hilo
```gherkin
Dado el ícono corriendo
Cuando se detiene
Entonces se invoca stop y se espera la terminación del hilo
```
*Fuente: test `[VERIFY: tests/test_tray.py:128]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-017.1 | CA-017.1 | feliz | Menú | build_icon | Acciones presentes | `[VERIFY: tests/test_tray.py:81]` |
| TC-017.2 | CA-017.2 | negativo | Backend falla | excepción | Warning, sigue vivo | `[VERIFY: tests/test_tray.py:121]` |
| TC-017.3 | CA-017.3 | borde | Sin DISPLAY | headless | Importa igual | `[VERIFY: tests/test_tray.py:139]` |
| TC-017.4 | CA-017.4 | feliz | Config explícita | --config X | Abre X | `[VERIFY: tests/test_app.py:205]` |
| TC-017.5 | CA-017.4 | borde | Sin --config | default | Abre la ruta por defecto | `[VERIFY: tests/test_app.py:216]` |
| TC-017.6 | CA-017.5 | feliz | Apertura Linux | xdg-open | Comando correcto | `[VERIFY: tests/test_tray.py:21]` |
| TC-017.7 | CA-017.6 | borde | Archivo ausente | sin config | Se crea | `[VERIFY: tests/test_tray.py:39]` |
| TC-017.8 | CA-017.6 | borde | Archivo existente | con config | No se sobrescribe | `[VERIFY: tests/test_tray.py:51]` |
| TC-017.9 | CA-017.7 | negativo | Editor falla | error | No propaga | `[VERIFY: tests/test_tray.py:62]` |
| TC-017.10 | CA-017.8 | borde | Pausa desde bandeja | callback | Reprogramado en Tk | `[VERIFY: tests/test_app.py:181]` |
| TC-017.11 | CA-017.9 | feliz | Estado de conexión | connect/reconnect | Refleja | `[VERIFY: tests/test_agent_state.py:14]` |
| TC-017.12 | CA-017.10 | negativo | Bandeja desactivada | enabled=false | Sin ícono | `[VERIFY: tests/test_app.py:170]` |
| TC-017.13 | CA-017.11 | borde | Parada | stop | Espera al hilo | `[VERIFY: tests/test_tray.py:128]` |
| TC-017.14 | CA-017.9 | negativo | **Carrera entre 3 hilos** sobre AgentState | escrituras concurrentes asyncio+Tk+ícono | Sin estado inconsistente | **escribir en v2** |

## Dependencias

- **Requiere**: HU-003, HU-011, HU-013
- **Habilita**: control del agente sin terminal

## Notas para la v2

Dos huecos conocidos, ambos de entorno más que de código:

1. **macOS nunca se validó.** `pystray` exige que su `run()` viva en el hilo principal
   (requisito de Cocoa), lo que choca de frente con Tkinter. No había máquina macOS para
   comprobarlo, y se dejó como best-effort en vez de bloquear el diseño. La v2 debe
   validarlo en hardware real o declarar la bandeja no soportada ahí (RR-4).
2. **TC-017.14**: `AgentState` está protegido por lock y lo tocan tres hilos, pero no hay
   test de concurrencia — solo de las operaciones individuales.

Además, dos tests de esta HU (`test_build_icon_assembles_menu_with_actions` y
`test_build_tray_enabled_returns_icon`) **exigen un display real** y fallan con
`Xlib DisplayNameError` en un entorno headless, pese a que la documentación del repo
afirma que el suite por defecto corre sin display. Ver DT-5 y RR-6.
