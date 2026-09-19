# HU-004: Una alerta que no puedo cerrar por reflejo

> **Cluster de origen:** C-05 · **Commits:** 3 `[COMMITS: fb50326, f90c796, f0960ac]`
> **Período:** 2026-06-28 → 2026-07-04 · **Era:** v0.1.0 → v0.1.3

## Historia

**Como** persona que puede estar mirando otra cosa cuando ocurre el sismo
**Quiero** que la alerta se ponga delante de todo, suene según la gravedad y no se cierre sola ni por accidente
**Para** enterarme aunque no esté atento a la pantalla, y no descartarla sin haberla leído

## Contexto de la implementación original

1.084 líneas: ventana Tk no descartable, cola de una alerta a la vez, sonido por severidad y toast
nativo, más los tres assets `.wav`. `AlertController`
`[VERIFY: src/vigia_eew/notify/controller.py:32]` orquesta los tres efectos como *callbacks
inyectables*, lo que permite probar toda la capa sin display ni audio.
`configure_undismissable` `[VERIFY: src/vigia_eew/notify/alert_window.py:38]` concentra la política
de no-cierre. Dos fixes posteriores corrigieron recortes de contenido en la ventana.

## Criterios de aceptación

### CA-004.1: La ventana se impone y no se cierra por vías accidentales
```gherkin
Dada una alerta visible
Cuando el usuario pulsa Escape, la X de la ventana, o la ventana pierde el foco
Entonces la alerta sigue en pantalla
Y la ventana permanece topmost y sin decoración
Y solo el acuse explícito la cierra
```
*Fuente: tests `[VERIFY: tests/test_alert_window.py:70]`, `[VERIFY: tests/test_alert_window.py:77]`, `[VERIFY: tests/test_alert_window.py:87]`, `[VERIFY: tests/test_alert_window.py:94]`, `[VERIFY: tests/test_alert_window.py:111]`*

### CA-004.2: El acuse es idempotente
```gherkin
Dada una alerta ya reconocida
Cuando se vuelve a invocar el acuse
Entonces no se ejecuta el callback por segunda vez ni se produce error
```
*Fuente: test `[VERIFY: tests/test_alert_window.py:119]`*

### CA-004.3: El contenido de la alerta cabe completo en la ventana
```gherkin
Dada una alerta con texto largo de lugar y hora
Cuando se construye la ventana real
Entonces la línea de detalle usa wraplength y no se recorta
Y la altura de la ventana acomoda todo el contenido sin chocar con el borde inferior
```
*Fuente: fix `[COMMITS: f90c796]` — la hora se recortaba por falta de `wraplength`; fix `[COMMITS: f0960ac]` — el detalle chocaba contra el borde inferior. Tests de humo `[VERIFY: tests/test_alert_window.py:157]`, `[VERIFY: tests/test_alert_window.py:174]`*

### CA-004.4: Una alerta a la vez, en orden de llegada
```gherkin
Dadas varias alertas encoladas
Cuando se muestra una
Entonces las demás esperan y se muestran en orden FIFO al acusar la anterior
Y un update del evento visible refresca la ventana sin volver a encolarlo
```
*Fuente: tests `[VERIFY: tests/test_alert_queue.py:53]`, `[VERIFY: tests/test_alert_queue.py:73]`, `[VERIFY: tests/test_alert_queue.py:128]`, `[VERIFY: tests/test_alert_queue.py:139]`*

### CA-004.5: El sonido escala con la severidad y nunca interrumpe la alerta
```gherkin
Dado un evento de severidad crítica
Cuando se reproduce el sonido
Entonces se repite más veces que en severidad informativa
Y si el reproductor del sistema falla, la alerta visual sigue funcionando
```
*Fuente: tests `[VERIFY: tests/test_sound.py:39]`, `[VERIFY: tests/test_sound.py:50]`, `[VERIFY: tests/test_sound.py:76]`*

### CA-004.6: El toast es best-effort
```gherkin
Dado un backend de notificaciones caído
Cuando se intenta enviar el toast
Entonces el fallo se registra y no se propaga
Y la urgencia del toast corresponde a la severidad del evento
```
*Fuente: tests `[VERIFY: tests/test_toast.py:62]`, `[VERIFY: tests/test_toast.py:51]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-004.1 | CA-004.1 | feliz | acuse explícito | click acuse | ventana destruida, callback llamado | `[VERIFY: tests/test_alert_window.py:111]` |
| TC-004.2 | CA-004.1 | negativo | tecla Escape | Escape | ventana intacta | `[VERIFY: tests/test_alert_window.py:87]` |
| TC-004.3 | CA-004.1 | negativo | pérdida de foco | FocusOut | ventana re-elevada | `[VERIFY: tests/test_alert_window.py:94]` |
| TC-004.4 | CA-004.2 | borde | doble acuse | 2 llamadas | 1 sola ejecución | `[VERIFY: tests/test_alert_window.py:119]` |
| TC-004.5 | CA-004.3 | borde | texto largo de lugar | detalle extenso | sin recorte, altura suficiente | `[VERIFY: tests/test_alert_window.py:174]` |
| TC-004.6 | CA-004.4 | feliz | 3 alertas | encoladas | FIFO | `[VERIFY: tests/test_alert_queue.py:73]` |
| TC-004.7 | CA-004.4 | borde | update del visible | mismo id | refresco sin re-encolar | `[VERIFY: tests/test_alert_queue.py:128]` |
| TC-004.8 | CA-004.5 | feliz | severidad crítica | mag alta | más repeticiones | `[VERIFY: tests/test_sound.py:44]` |
| TC-004.9 | CA-004.5 | negativo | reproductor ausente | sin `paplay`/`aplay` | comando None, sin fallo | `[VERIFY: tests/test_sound.py:97]` |
| TC-004.10 | CA-004.6 | negativo | notificador caído | excepción | registrado, no propagado | `[VERIFY: tests/test_toast.py:62]` |

## Dependencias

- **Requiere**: HU-001, HU-003
- **Habilita**: HU-005, HU-009, HU-011

## Notas para la v2

Los dos fixes de layout `[COMMITS: f90c796, f0960ac]` atacaron síntomas. La v2 debe especificar el
contrato de tamaño de la ventana como criterio verificable (CA-004.3) desde el diseño. Y bajo
Wayland CA-004.1 **no está garantizado**: ver `01-ARQUITECTURA.md` §7.
