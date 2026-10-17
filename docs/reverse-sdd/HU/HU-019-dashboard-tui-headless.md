# HU-019: Dashboard TUI para servidores headless

> **Cluster de origen:** Fase 11 (RF-36) · **Commits:** 2 `[COMMITS: 7f98980, 651c024]`
> **Período:** 2026-07-04 → 2026-07-05 · **Era:** Era 2 — Contexto del usuario

## Historia

**Como** administrador que corre el agente en un servidor por SSH `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** ver su estado y reconocer alertas desde la terminal
**Para** usarlo donde no hay sesión gráfica

## Contexto de la implementación original

`VigiaTuiApp` `[VERIFY: src/vigia_eew/tui.py:101]` es un **frontend alternativo**, no una
capa sobre Tkinter. Muestra barra de estado, log de alertas y un modal no descartable
`[VERIFY: src/vigia_eew/tui.py:29]` con el mismo contrato que la ventana Tk: solo ENTER
reconoce, y `escape` está atado a un no-op explícito.

**No usa el puente asyncio↔Tk**: Textual ya es asyncio-nativo, así que el supervisor corre
como worker de Textual en el *mismo* event loop y el procesador llama al controlador
directamente. El camino TUI es genuinamente más simple que el gráfico, y esa asimetría es
intencional.

Reutiliza el contrato de efectos: se construye el mismo `AlertController` inyectando
`create_window = tui_app.push_alert` `[VERIFY: src/vigia_eew/app.py:313]`.

**Ventaja de testeo decisiva**: Textual trae `App.run_test()`, un piloto headless, así que
los 13 tests de esta HU corren en el suite por defecto sin necesitar terminal real ni el
guard `VIGIA_GUI_TESTS=1` — al contrario que la ventana Tkinter.

## Criterios de aceptación

### CA-019.1: La interfaz muestra barra de estado y log de alertas
```gherkin
Dado la TUI arrancada
Cuando se compone la vista
Entonces se muestran la barra de estado y el log de alertas
```
*Fuente: test `[VERIFY: tests/test_tui.py:26]`*

### CA-019.2: La barra refleja el estado de conexión
```gherkin
Dado el estado del ingestor
Cuando cambia a conectado o reconectando
Entonces la barra lo refleja
```
*Fuente: tests `[VERIFY: tests/test_tui.py:33]`, `[VERIFY: tests/test_tui.py:41]`*

### CA-019.3: Un evento relevante muestra un modal y queda en el log
```gherkin
Dado un evento que pasa el pipeline
Cuando llega a la TUI
Entonces se muestra un modal y se registra en el log
```
*Fuente: tests `[VERIFY: tests/test_tui.py:50]`, `[VERIFY: tests/test_tui.py:57]`*

### CA-019.4: Solo ENTER reconoce la alerta
```gherkin
Dado un modal de alerta visible
Cuando el usuario pulsa ENTER
Entonces se invoca el callback y el modal se cierra
```
*Fuente: test `[VERIFY: tests/test_tui.py:65]`*

### CA-019.5: Escape no cierra la alerta
```gherkin
Dado un modal de alerta visible
Cuando el usuario pulsa escape
Entonces el modal permanece abierto
```
*Fuente: test `[VERIFY: tests/test_tui.py:78]` — paridad explícita con la ventana Tk
(CA-011.3): la garantía del producto no puede depender del frontend elegido*

### CA-019.6: Un update refresca el modal visible
```gherkin
Dado un modal visible
Cuando llega una revisión del mismo evento
Entonces los campos se actualizan sin recrear la pantalla
```
*Fuente: test `[VERIFY: tests/test_tui.py:90]`*

### CA-019.7: La tecla `p` pausa y reanuda
```gherkin
Dado la TUI corriendo
Cuando el usuario pulsa p
Entonces alterna entre pausado y reanudado
```
*Fuente: test `[VERIFY: tests/test_tui.py:117]`*

### CA-019.8: La tecla `q` sale limpiamente, con o sin supervisor
```gherkin
Dado la TUI corriendo, con o sin supervisor enlazado
Cuando el usuario pulsa q
Entonces se solicita la parada y la aplicación termina sin error
```
*Fuente: tests `[VERIFY: tests/test_tui.py:143]`, `[VERIFY: tests/test_tui.py:153]`*

### CA-019.9: `--simulate --tui` inyecta el evento en la app ya corriendo
```gherkin
Dado el modo simulación con TUI
Cuando la aplicación monta
Entonces se inyecta el evento simulado sin arrancar el supervisor real
```
*Fuente: tests `[VERIFY: tests/test_tui.py:161]`,
`[VERIFY: tests/test_tui.py:169]` (end-to-end), `[VERIFY: tests/test_app.py:277]`*

### CA-019.10: El cableado construye el controlador con `push_alert`
```gherkin
Dado el arranque en modo TUI
Cuando se construye el controlador
Entonces usa push_alert como fábrica de ventana y enlaza supervisor y controlador
```
*Fuente: tests `[VERIFY: tests/test_app.py:247]`,
`[VERIFY: tests/test_app.py:258]`, `[VERIFY: tests/test_app.py:269]`*

### CA-019.11: En modo TUI no hay toast ni bandeja
```gherkin
Dado un servidor headless
Cuando corre el modo TUI
Entonces no se envían toasts ni se construye la bandeja
```
*Fuente: código `[VERIFY: src/vigia_eew/app.py:313]` — un servidor sin sesión de
escritorio no tiene a quién notificar*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-019.1 | CA-019.1 | feliz | Composición | arranque | Barra + log | `[VERIFY: tests/test_tui.py:26]` |
| TC-019.2 | CA-019.2 | feliz | Conectado | estado ok | Barra "conectado" | `[VERIFY: tests/test_tui.py:41]` |
| TC-019.3 | CA-019.2 | borde | Reconectando | caída | Barra "reconectando" | `[VERIFY: tests/test_tui.py:33]` |
| TC-019.4 | CA-019.3 | feliz | Alerta | evento | Modal + log | `[VERIFY: tests/test_tui.py:50]` |
| TC-019.5 | CA-019.4 | feliz | ENTER | tecla | Reconoce y cierra | `[VERIFY: tests/test_tui.py:65]` |
| TC-019.6 | CA-019.5 | negativo | Escape | tecla | No cierra | `[VERIFY: tests/test_tui.py:78]` |
| TC-019.7 | CA-019.6 | feliz | Update | revisión | Refresca | `[VERIFY: tests/test_tui.py:90]` |
| TC-019.8 | CA-019.7 | feliz | Pausa/reanuda | p, p | Alterna | `[VERIFY: tests/test_tui.py:117]` |
| TC-019.9 | CA-019.8 | feliz | Salir | q | Stop + exit | `[VERIFY: tests/test_tui.py:143]` |
| TC-019.10 | CA-019.8 | borde | Salir sin supervisor | q | Exit limpio | `[VERIFY: tests/test_tui.py:153]` |
| TC-019.11 | CA-019.9 | feliz | Simulación TUI | --simulate --tui | Modal y ACK | `[VERIFY: tests/test_tui.py:169]` |
| TC-019.12 | CA-019.10 | feliz | Cableado | run_tui | push_alert inyectado | `[VERIFY: tests/test_app.py:247]` |
| TC-019.13 | CA-019.11 | borde | Sin toast ni bandeja | headless | Ninguno construido | **escribir en v2** |

## Dependencias

- **Requiere**: HU-007, HU-012 (reutiliza colores y formato), HU-013
- **Habilita**: uso del agente en servidores

## Notas para la v2

Esta HU tiene la **mejor relación cobertura/esfuerzo de todo el repo**: 13 tests de
comportamiento de interfaz corriendo headless en el suite por defecto, frente a los
smokes de Tkinter que necesitan `VIGIA_GUI_TESTS=1` y un display.

Es un argumento fuerte para la v2: si la TUI puede testearse así de bien y el frontend
gráfico está limitado por Wayland (RR-3), conviene evaluar si la TUI debería ser el
frontend **primario** y el gráfico el alternativo, invirtiendo la jerarquía actual.
