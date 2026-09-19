# HU-011: Usar el agente en un servidor sin escritorio

> **Cluster de origen:** C-13 · **Commits:** 2 `[COMMITS: 7f98980, 651c024]`
> **Período:** 2026-07-04 → 2026-07-05 · **Era:** v0.1.3 → v0.3.0

## Historia

**Como** administrador que corre el agente en un servidor por SSH
**Quiero** un panel en el terminal con el estado y las alertas, que también sea imposible de descartar por accidente
**Para** vigilar y reconocer alertas sin sesión gráfica

## Contexto de la implementación original

`VigiaTuiApp` `[VERIFY: src/vigia_eew/tui.py:101]` sobre Textual, seleccionado con `--tui`.
Es un **modo alternativo**, no una capa sobre Tkinter: al ser Textual asyncio-nativo, el supervisor
corre como worker en el mismo event loop `[VERIFY: src/vigia_eew/app.py:369]` y **no existe puente
asyncio↔UI**. El modal `AlertScreen` `[VERIFY: src/vigia_eew/tui.py:29]` replica el contrato de
no-descarte de la ventana Tk. Sin toast ni bandeja en este modo.

Textual aporta una ventaja de prueba decisiva: `App.run_test()` es headless, así que este modo se
cubre en la suite por defecto, sin la puerta `VIGIA_GUI_TESTS=1`.

## Criterios de aceptación

### CA-011.1: El panel muestra estado de conexión y registro de alertas
```gherkin
Dado el agente arrancado con --tui
Cuando se monta la interfaz
Entonces se muestra una barra de estado y un registro de alertas
Y la barra indica reconectando por defecto y conectado cuando el WebSocket lo está
```
*Fuente: tests `[VERIFY: tests/test_tui.py:26]`, `[VERIFY: tests/test_tui.py:33]`, `[VERIFY: tests/test_tui.py:41]`*

### CA-011.2: La alerta en el terminal tampoco se descarta por accidente
```gherkin
Dada una alerta mostrada como modal en el TUI
Cuando el usuario pulsa Escape
Entonces la alerta permanece
Y solo ENTER la reconoce y la cierra
```
*Fuente: tests `[VERIFY: tests/test_tui.py:78]`, `[VERIFY: tests/test_tui.py:65]`; código `[VERIFY: src/vigia_eew/tui.py:29]`*

### CA-011.3: Un update refresca el modal visible
```gherkin
Dada una alerta visible en el TUI
Cuando llega una actualización del mismo evento
Entonces el modal se actualiza en sitio sin abrir otro
```
*Fuente: test `[VERIFY: tests/test_tui.py:90]`*

### CA-011.4: Las teclas de control funcionan como en la bandeja
```gherkin
Dado el TUI en ejecución
Cuando el usuario pulsa p
Entonces se pausan las notificaciones y al volver a pulsarla se reanudan
Y al pulsar q se solicita la parada del supervisor y la aplicación sale limpiamente
Y si no hay supervisor asociado, q también sale sin error
```
*Fuente: tests `[VERIFY: tests/test_tui.py:117]`, `[VERIFY: tests/test_tui.py:143]`, `[VERIFY: tests/test_tui.py:153]`*

### CA-011.5: `--tui --simulate` funciona sin red ni supervisor
```gherkin
Dado el TUI arrancado en modo simulación
Cuando la interfaz termina de montarse
Entonces se inyecta el evento simulado y se puede reconocer
Y no se arranca el supervisor real
```
*Fuente: tests `[VERIFY: tests/test_tui.py:169]`, `[VERIFY: tests/test_tui.py:161]`, `[VERIFY: tests/test_cli.py:73]`*

### CA-011.6: El paquete se importa en un host sin display
```gherkin
Dado un host headless sin servidor gráfico
Cuando se importa el paquete o se arranca en modo TUI
Entonces no se produce error por ausencia de display
```
*Fuente: fix `[COMMITS: 651c024]` — el agente no era import-safe en host headless, lo que además bloqueaba la CI. Test `[VERIFY: tests/test_tray.py:139]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-011.1 | CA-011.1 | feliz | montaje | `--tui` | barra + log visibles | `[VERIFY: tests/test_tui.py:26]` |
| TC-011.2 | CA-011.1 | borde | WS conectado | estado conectado | barra actualizada | `[VERIFY: tests/test_tui.py:41]` |
| TC-011.3 | CA-011.2 | feliz | ENTER | tecla enter | modal cerrado, callback llamado | `[VERIFY: tests/test_tui.py:65]` |
| TC-011.4 | CA-011.2 | negativo | Escape | tecla escape | modal intacto | `[VERIFY: tests/test_tui.py:78]` |
| TC-011.5 | CA-011.3 | borde | update del visible | mismo id | refresco en sitio | `[VERIFY: tests/test_tui.py:90]` |
| TC-011.6 | CA-011.4 | feliz | pausa/reanuda | tecla p ×2 | pausado y reanudado | `[VERIFY: tests/test_tui.py:117]` |
| TC-011.7 | CA-011.4 | borde | q sin supervisor | tecla q | salida limpia | `[VERIFY: tests/test_tui.py:153]` |
| TC-011.8 | CA-011.5 | feliz | simulación en TUI | `--tui --simulate` | alerta mostrada y reconocida | `[VERIFY: tests/test_tui.py:169]` |
| TC-011.9 | CA-011.6 | negativo | host sin display | import | sin error | `[VERIFY: tests/test_tray.py:139]` |

## Dependencias

- **Requiere**: HU-004 (contrato de efectos inyectables), HU-005
- **Habilita**: despliegue en servidores headless

## Notas para la v2

Dos nombres de método son trampas heredadas de Textual y deben conservarse: el refresco del modal
es `update_data` (no `refresh`, que ya existe en `Widget` sin argumentos) y el repintado interno es
`_paint` (no `_render`, cuyo *override* rompe el renderizado en silencio). Documentado en
`lat.md/notification.md`.
