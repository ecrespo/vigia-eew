# HU-009: Ver el estado del agente y pausarlo sin abrir una terminal

> **Cluster de origen:** C-11 · **Commits:** 1 `[COMMITS: fb3fe14]`
> **Período:** 2026-07-04 · **Era:** v0.1.3

## Historia

**Como** usuario con el agente arrancado automáticamente en segundo plano
**Quiero** un ícono en la bandeja que me diga si está conectado y me deje pausar, editar la configuración o salir
**Para** controlarlo sin depender de la terminal ni de saber cómo se lanzó

## Contexto de la implementación original

`TrayIcon` `[VERIFY: src/vigia_eew/tray.py:110]` corre `pystray` en un **hilo trabajador propio**,
dejando Tkinter como único dueño del hilo principal. `AgentState`
`[VERIFY: src/vigia_eew/agent_state.py:14]` es la instantánea compartida protegida por lock que
alimenta el texto dinámico del menú. Tanto la construcción `[VERIFY: src/vigia_eew/app.py:178]`
como la ejecución del ícono son **best effort**: un fallo solo registra un aviso.

## Criterios de aceptación

### CA-009.1: El menú refleja el estado real de la conexión y la última alerta
```gherkin
Dado el agente en ejecución
Cuando el ingestor WebSocket conecta o pierde la conexión
Entonces el estado compartido pasa a conectado o reconectando
Y cuando se muestra una alerta, el estado registra cuál fue la última
```
*Fuente: tests `[VERIFY: tests/test_agent_state.py:14]`, `[VERIFY: tests/test_agent_state.py:22]`, `[VERIFY: tests/test_ws_emsc.py:193]`, `[VERIFY: tests/test_ws_emsc.py:209]`, `[VERIFY: tests/test_controller.py:118]`*

### CA-009.2: Pausar retiene las alertas, no las descarta
```gherkin
Dado el agente pausado desde la bandeja
Cuando llegan eventos relevantes
Entonces no se muestran, pero se encolan
Y al reanudar se muestran las acumuladas
Y pausar no interrumpe la alerta que ya estaba visible
```
*Fuente: tests `[VERIFY: tests/test_alert_queue.py:94]`, `[VERIFY: tests/test_alert_queue.py:105]`, `[VERIFY: tests/test_alert_queue.py:117]`, `[VERIFY: tests/test_controller.py:103]`*

### CA-009.3: Las acciones que tocan Tk se ejecutan en el hilo de Tk
```gherkin
Dada una acción del menú que puede crear una ventana, como reanudar
Cuando se invoca desde el hilo del ícono
Entonces se reprograma en el hilo de Tkinter
Y salir desde la bandeja también se reprograma allí
```
*Fuente: tests `[VERIFY: tests/test_app.py:181]`, `[VERIFY: tests/test_app.py:195]`*

### CA-009.4: "Editar configuración" abre el archivo realmente en uso
```gherkin
Dado un agente arrancado con una ruta de configuración explícita
Cuando se elige editar la configuración desde la bandeja
Entonces se abre ese archivo y no la ruta por defecto
Y si el archivo no existe todavía, se crea antes de abrirlo
Y si el archivo ya existe, no se sobrescribe
```
*Fuente: tests `[VERIFY: tests/test_app.py:205]`, `[VERIFY: tests/test_app.py:216]`, `[VERIFY: tests/test_tray.py:39]`, `[VERIFY: tests/test_tray.py:51]`*

### CA-009.5: La bandeja nunca impide que el agente arranque
```gherkin
Dado un entorno donde el backend de bandeja no está disponible
Cuando el agente arranca
Entonces el fallo se registra como aviso y el agente sigue funcionando sin ícono
Y el paquete se puede importar sin display
```
*Fuente: tests `[VERIFY: tests/test_tray.py:121]`, `[VERIFY: tests/test_tray.py:139]`, `[VERIFY: tests/test_app.py:170]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-009.1 | CA-009.1 | feliz | WS conecta | evento de conexión | estado conectado | `[VERIFY: tests/test_ws_emsc.py:193]` |
| TC-009.2 | CA-009.1 | borde | WS cae | desconexión | estado reconectando | `[VERIFY: tests/test_ws_emsc.py:209]` |
| TC-009.3 | CA-009.2 | feliz | pausa + 2 eventos | pausado | 0 mostradas, 2 encoladas | `[VERIFY: tests/test_alert_queue.py:94]` |
| TC-009.4 | CA-009.2 | borde | reanudar | resume | muestra pendientes | `[VERIFY: tests/test_alert_queue.py:105]` |
| TC-009.5 | CA-009.2 | borde | pausar con alerta visible | pausa | la visible permanece | `[VERIFY: tests/test_alert_queue.py:117]` |
| TC-009.6 | CA-009.3 | feliz | toggle desde bandeja | callback | reprogramado en hilo Tk | `[VERIFY: tests/test_app.py:181]` |
| TC-009.7 | CA-009.4 | feliz | `--config` explícito | ruta dada | abre esa ruta | `[VERIFY: tests/test_app.py:205]` |
| TC-009.8 | CA-009.4 | borde | config inexistente | primera vez | se crea y se abre | `[VERIFY: tests/test_tray.py:39]` |
| TC-009.9 | CA-009.5 | negativo | backend de bandeja roto | excepción | agente vivo, aviso en log | `[VERIFY: tests/test_tray.py:121]` |
| TC-009.10 | CA-009.5 | negativo | host headless | sin display | import correcto | `[VERIFY: tests/test_tray.py:139]` |

## Dependencias

- **Requiere**: HU-004 (cola de alertas), HU-005 (`Application`)
- **Habilita**: HU-011 (el TUI reutiliza pausa/reanudar y el estado compartido)

## Notas para la v2

Dos limitaciones conocidas siguen sin resolverse: GNOME/Wayland sin la extensión AppIndicator no
muestra íconos de bandeja legacy, y en macOS Cocoa exige `run()` en el hilo principal, en conflicto
con Tk — nunca se validó en hardware macOS. La v2 debe decidir explícitamente si soporta bandeja en
macOS o la declara no disponible allí.
