# HU-011: Alerta de escritorio imposible de descartar por accidente

> **Cluster de origen:** Fase 4 · **Commits:** 3 `[COMMITS: fb50326, f90c796, f0960ac]`
> **Período:** 2026-06-28 → 2026-07-04 · **Era:** Era 0 + Era 2

## Historia

**Como** usuario que puede estar distraído cuando ocurre un sismo `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** una alerta que no pueda cerrarse por reflejo ni quedar detrás de otras ventanas
**Para** enterarme de verdad, y no descubrir después que la descarté sin leerla

## Contexto de la implementación original

Esta es **la promesa central del producto**. `configure_undismissable`
`[VERIFY: src/vigia_eew/notify/alert_window.py:39]` retira deliberadamente cada comodidad
que normalmente hace educada a una ventana: sin decoración, siempre encima, la X no
cierra, Escape no cierra, y si pierde el foco lo recupera. La única salida es el
reconocimiento explícito `[VERIFY: src/vigia_eew/notify/alert_window.py:48]`.

`AlertQueue` `[VERIFY: src/vigia_eew/notify/queue.py:25]` serializa: una alerta a la vez,
en orden. Durante un enjambre, apilar modales produciría una pila peleando por el foco y
el usuario las limpiaría a ciegas — el mismo fallo por reflejo que esta HU existe para
evitar.

Dos fixes posteriores muestran que la garantía siguió madurando: la hora se recortaba por
falta de `wraplength` `[COMMITS: f90c796]` y el contenido chocaba contra el borde inferior
`[COMMITS: f0960ac]`.

## Criterios de aceptación

### CA-011.1: La ventana es topmost y sin decoración
```gherkin
Dado que se muestra una alerta
Cuando se aplica la política de ventana
Entonces queda siempre encima y sin barra de título ni botones
```
*Fuente: test `[VERIFY: tests/test_alert_window.py:70]`*

### CA-011.2: El botón de cerrar no cierra
```gherkin
Dado una alerta visible
Cuando el usuario intenta cerrarla con la X del gestor de ventanas
Entonces la ventana permanece abierta
```
*Fuente: test `[VERIFY: tests/test_alert_window.py:77]`*

### CA-011.3: Escape no cierra
```gherkin
Dado una alerta visible
Cuando el usuario pulsa Escape
Entonces la ventana permanece abierta
```
*Fuente: test `[VERIFY: tests/test_alert_window.py:87]` — Escape es el reflejo más
probable, por eso está explícitamente anulado y no simplemente "no implementado"*

### CA-011.4: Perder el foco lo recupera
```gherkin
Dado una alerta visible
Cuando otra ventana le roba el foco
Entonces la alerta vuelve a levantarse y recupera el foco
```
*Fuente: tests `[VERIFY: tests/test_alert_window.py:94]`,
`[VERIFY: tests/test_alert_window.py:102]`*

### CA-011.5: Solo el reconocimiento explícito cierra
```gherkin
Dado una alerta visible
Cuando el usuario la reconoce
Entonces se invoca el callback y la ventana se destruye
```
*Fuente: test `[VERIFY: tests/test_alert_window.py:111]`*

### CA-011.6: Reconocer dos veces es idempotente
```gherkin
Dado una alerta ya reconocida
Cuando se reconoce de nuevo
Entonces no se duplica el efecto ni falla
```
*Fuente: test `[VERIFY: tests/test_alert_window.py:119]`*

### CA-011.7: Se muestra una alerta a la vez, en orden FIFO
```gherkin
Dado varios eventos encolados
Cuando se muestran
Entonces aparece uno solo a la vez y en el orden de llegada
```
*Fuente: tests `[VERIFY: tests/test_alert_queue.py:53]`,
`[VERIFY: tests/test_alert_queue.py:73]`, `[VERIFY: tests/test_alert_queue.py:62]`*

### CA-011.8: Un `update` del evento visible lo refresca sin re-encolar
```gherkin
Dado una alerta visible
Cuando llega un update de ese mismo evento
Entonces se refresca en sitio, sin crear una alerta nueva
Y si el update es de otro id, se encola
```
*Fuente: tests `[VERIFY: tests/test_alert_queue.py:128]`,
`[VERIFY: tests/test_alert_queue.py:139]`*

### CA-011.9: El texto largo no se recorta
```gherkin
Dado un evento con lugar y hora largos
Cuando se renderiza la ventana real
Entonces el detalle usa wraplength y la altura acomoda el contenido completo
```
*Fuente: fixes `[COMMITS: f90c796]` (hora recortada) y `[COMMITS: f0960ac]` (contenido
contra el borde inferior); tests de humo
`[VERIFY: tests/test_alert_window.py:157]`, `[VERIFY: tests/test_alert_window.py:174]`*

### CA-011.10: El cruce asyncio→Tk preserva el orden
```gherkin
Dado eventos publicados desde el hilo asyncio
Cuando el puente los drena en el hilo de Tk
Entonces llegan en orden y drenar una cola vacía no hace nada
```
*Fuente: tests `[VERIFY: tests/test_alert_queue.py:151]`,
`[VERIFY: tests/test_alert_queue.py:160]`, `[VERIFY: tests/test_alert_queue.py:174]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-011.1 | CA-011.1 | feliz | Política de ventana | alerta | topmost + sin decoración | `[VERIFY: tests/test_alert_window.py:70]` |
| TC-011.2 | CA-011.2 | negativo | Clic en la X | WM_DELETE | No cierra | `[VERIFY: tests/test_alert_window.py:77]` |
| TC-011.3 | CA-011.3 | negativo | Escape | tecla | No cierra | `[VERIFY: tests/test_alert_window.py:87]` |
| TC-011.4 | CA-011.4 | borde | Pérdida de foco | FocusOut | Se re-eleva | `[VERIFY: tests/test_alert_window.py:94]` |
| TC-011.5 | CA-011.5 | feliz | Reconocimiento | ACK | Callback + destroy | `[VERIFY: tests/test_alert_window.py:111]` |
| TC-011.6 | CA-011.6 | borde | Doble ACK | 2 clics | Idempotente | `[VERIFY: tests/test_alert_window.py:119]` |
| TC-011.7 | CA-011.7 | feliz | Dos eventos | A, B | Solo A visible | `[VERIFY: tests/test_alert_queue.py:53]` |
| TC-011.8 | CA-011.7 | feliz | Orden FIFO | A,B,C | A→B→C | `[VERIFY: tests/test_alert_queue.py:73]` |
| TC-011.9 | CA-011.8 | feliz | update del visible | mismo id | Refresca | `[VERIFY: tests/test_alert_queue.py:128]` |
| TC-011.10 | CA-011.8 | borde | update de otro id | otro id | Se encola | `[VERIFY: tests/test_alert_queue.py:139]` |
| TC-011.11 | CA-011.9 | borde | Texto largo | lugar extenso | Sin recorte | `[VERIFY: tests/test_alert_window.py:157]` |
| TC-011.12 | CA-011.10 | feliz | Puente de hilos | N eventos | Orden preservado | `[VERIFY: tests/test_alert_queue.py:151]` |
| TC-011.13 | CA-011.1 | negativo | **Wayland**: compositor niega topmost/focus | sesión GNOME Wayland | Comportamiento no verificado — ver RR-3 | **escribir en v2** |

## Dependencias

- **Requiere**: HU-001, HU-009, HU-010
- **Habilita**: HU-012, HU-017, HU-019

## Notas para la v2

TC-011.13 es el hueco más serio del kit completo. Toda esta HU —la promesa central del
producto— se verifica contra un Tk simulado o un X11 real, pero **bajo Wayland el
compositor controla el apilamiento y el foco**, y una app XWayland no puede forzarlos de
forma confiable. ADR-010 lo reconoce y propone un frontend por D-Bus con extensión de
GNOME Shell; nunca se implementó.

La v2 debe resolver esto **antes** de elegir toolkit, no después. Ver RR-3 en
`02-STACK-TECNOLOGICO.md` y DT-3 en `01-ARQUITECTURA.md`.
