# HU-012: Sonido, toast nativo y presentación por severidad

> **Cluster de origen:** Fase 4 · **Commits:** 1 `[COMMITS: fb50326]`
> **Período:** 2026-06-28 · **Era:** Era 0 — Fundación

## Historia

**Como** usuario que puede no estar mirando la pantalla `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** que la alerta suene con insistencia proporcional a la gravedad
**Para** enterarme aunque no esté frente al monitor

## Contexto de la implementación original

El sonido es una **capa propia** `[VERIFY: src/vigia_eew/notify/sound.py:99]`, no el
sonido del toast. Depender del toast dejaría la audibilidad a merced de "No molestar" y de
los ajustes por aplicación — justo los que el usuario activa cuando no quiere ser
interrumpido. Una alerta sísmica tiene que sobrevivir a eso.

`presentation.py` `[VERIFY: src/vigia_eew/notify/presentation.py:56]` son funciones
**puras** y el único lugar donde un instante UTC se convierte a hora local
`[VERIFY: src/vigia_eew/notify/presentation.py:46]`. Confinar la conversión ahí permite
testear la regla de visualización sin GUI y evita que la lógica de zonas horarias se filtre
hacia ingestión o dedup.

`AlertController` `[VERIFY: src/vigia_eew/notify/controller.py:32]` recibe los tres efectos
como callbacks inyectados, que es lo que permite que GUI y TUI compartan controlador.

## Criterios de aceptación

### CA-012.1: La insistencia del sonido crece con la severidad
```gherkin
Dado eventos de severidad info, warning y critical
Cuando se reproduce el sonido
Entonces el número de repeticiones crece con la severidad
```
*Fuente: tests `[VERIFY: tests/test_sound.py:39]`, `[VERIFY: tests/test_sound.py:44]`,
`[VERIFY: tests/test_sound.py:50]`*

### CA-012.2: Cada severidad usa su propio asset
```gherkin
Dado una severidad
Cuando se resuelve la ruta del sonido
Entonces apunta al WAV empaquetado de esa severidad
```
*Fuente: test `[VERIFY: tests/test_sound.py:56]`*

### CA-012.3: El sonido se puede desactivar
```gherkin
Dado la configuración con sonido deshabilitado
Cuando llega una alerta
Entonces no se reproduce nada
```
*Fuente: test `[VERIFY: tests/test_sound.py:62]`*

### CA-012.4: El reproductor se elige por sistema operativo con fallback
```gherkin
Dado un sistema operativo concreto
Cuando se construye el comando de reproducción
Entonces usa el reproductor adecuado, con fallback si el preferido no existe
```
*Fuente: tests `[VERIFY: tests/test_sound.py:85]` (paplay),
`[VERIFY: tests/test_sound.py:89]` (aplay), `[VERIFY: tests/test_sound.py:93]` (afplay),
`[VERIFY: tests/test_sound.py:97]` (sin reproductor)*

### CA-012.5: Un fallo del reproductor no propaga
```gherkin
Dado un reproductor ausente o que falla
Cuando se intenta sonar la alerta
Entonces se registra y la alerta visual sigue su curso
```
*Fuente: test `[VERIFY: tests/test_sound.py:76]` — un servidor headless sin dispositivo
de audio no debe impedir la alerta*

### CA-012.6: El toast nativo lleva título, mensaje y urgencia por severidad
```gherkin
Dado un evento con severidad
Cuando se envía el toast
Entonces incluye magnitud y lugar, con la urgencia correspondiente
```
*Fuente: tests `[VERIFY: tests/test_toast.py:42]`, `[VERIFY: tests/test_toast.py:51]`,
`[VERIFY: tests/test_presentation.py:78]`*

### CA-012.7: Un fallo del backend de toast no propaga
```gherkin
Dado un backend de notificaciones que lanza
Cuando se envía el toast
Entonces se aísla el fallo y el resto de la alerta continúa
```
*Fuente: test `[VERIFY: tests/test_toast.py:62]`*

### CA-012.8: La hora se muestra en la zona local configurada
```gherkin
Dado un evento con tiempo UTC
Cuando se formatea para la alerta
Entonces se muestra en la zona configurada (por defecto America/Caracas)
```
*Fuente: test `[VERIFY: tests/test_presentation.py:50]`*

### CA-012.9: Los campos de la alerta se formatean de forma legible
```gherkin
Dado un evento
Cuando se formatea
Entonces magnitud, distancia redondeada, profundidad, lugar, fuente y severidad
       aparecen en formato legible
```
*Fuente: tests `[VERIFY: tests/test_presentation.py:35]`,
`[VERIFY: tests/test_presentation.py:40]`, `[VERIFY: tests/test_presentation.py:45]`,
`[VERIFY: tests/test_presentation.py:66]`*

### CA-012.10: Hay un lugar mostrable aunque falten datos
```gherkin
Dado un evento sin campo de lugar
Cuando se formatea
Entonces usa la región, o un marcador si tampoco existe
```
*Fuente: tests `[VERIFY: tests/test_presentation.py:56]`,
`[VERIFY: tests/test_presentation.py:61]`*

### CA-012.11: Cada severidad tiene su color
```gherkin
Dado una severidad
Cuando se pide su color
Entonces devuelve el hex asociado
```
*Fuente: test `[VERIFY: tests/test_presentation.py:72]` — reutilizado tal cual por la TUI*

### CA-012.12: El controlador orquesta los tres efectos y tolera su ausencia
```gherkin
Dado un evento encolado
Cuando el controlador lo procesa
Entonces crea ventana, suena y notifica; y si sonido o toast no están configurados,
       la alerta visual funciona igual
```
*Fuente: tests `[VERIFY: tests/test_controller.py:61]`,
`[VERIFY: tests/test_controller.py:92]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-012.1 | CA-012.1 | feliz | Insistencia por severidad | info/warn/crit | Repeticiones crecientes | `[VERIFY: tests/test_sound.py:39]` |
| TC-012.2 | CA-012.1 | borde | Espera entre repeticiones | critical | Pausa entre reproducciones | `[VERIFY: tests/test_sound.py:68]` |
| TC-012.3 | CA-012.2 | feliz | Asset por severidad | critical | WAV correcto | `[VERIFY: tests/test_sound.py:56]` |
| TC-012.4 | CA-012.3 | negativo | Sonido desactivado | enabled=false | Silencio | `[VERIFY: tests/test_sound.py:62]` |
| TC-012.5 | CA-012.4 | feliz | Linux con paplay | Linux | paplay | `[VERIFY: tests/test_sound.py:85]` |
| TC-012.6 | CA-012.4 | borde | Linux sin paplay | fallback | aplay | `[VERIFY: tests/test_sound.py:89]` |
| TC-012.7 | CA-012.4 | negativo | Sin reproductor | ninguno | Comando None | `[VERIFY: tests/test_sound.py:97]` |
| TC-012.8 | CA-012.5 | negativo | Reproductor falla | excepción | No propaga | `[VERIFY: tests/test_sound.py:76]` |
| TC-012.9 | CA-012.6 | feliz | Toast completo | evento | Título+mensaje | `[VERIFY: tests/test_toast.py:42]` |
| TC-012.10 | CA-012.7 | negativo | Backend falla | excepción | Aislado | `[VERIFY: tests/test_toast.py:62]` |
| TC-012.11 | CA-012.8 | feliz | Hora local | UTC→VET | Hora Venezuela | `[VERIFY: tests/test_presentation.py:50]` |
| TC-012.12 | CA-012.10 | borde | Sin lugar ni región | vacío | Marcador | `[VERIFY: tests/test_presentation.py:61]` |
| TC-012.13 | CA-012.12 | borde | Sin sonido ni toast | solo ventana | Funciona | `[VERIFY: tests/test_controller.py:92]` |

## Dependencias

- **Requiere**: HU-001, HU-011
- **Habilita**: HU-018 (los textos que traduce), HU-019 (reutiliza colores)

## Notas para la v2

Preservar dos cosas: el sonido como capa independiente del toast (razón documentada en
ADR-005) y la pureza de `presentation.py`, que es lo que permite 9 tests de formato sin
levantar una GUI.
