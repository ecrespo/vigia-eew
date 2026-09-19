# HU-010: Que el agente me hable en mi idioma

> **Cluster de origen:** C-12 · **Commits:** 2 `[COMMITS: 7f9132e, e49404d]`
> **Período:** 2026-07-04 · **Era:** v0.1.3

## Historia

**Como** usuario cuyo sistema está en español o en inglés
**Quiero** que la ventana de alerta, el toast y el menú de la bandeja aparezcan en el idioma de mi sistema
**Para** entender la alerta de inmediato sin configurar nada

## Contexto de la implementación original

El commit `7f9132e` es un `feat!` que traduce **todo** el código, los docstrings, la documentación
y los nombres de módulo del español al inglés (`filtro.py` → `filter.py`, `presentacion.py` →
`presentation.py`, `controlador.py` → `controller.py`, `procesador.py` → `processor.py`,
`simulacion.py` → `simulation.py`, `estado_agente.py` → `agent_state.py`) y renombra los assets de
audio (`critico.wav` → `critical.wav`, `atencion.wav` → `warning.wav`). En el mismo movimiento
introduce `i18n.py` `[VERIFY: src/vigia_eew/i18n.py:64]`. El commit siguiente `e49404d` unifica los
imports del paquete a absolutos.

Es el commit más invasivo del repositorio: más de 30 archivos, incluidos artefactos binarios.

## Criterios de aceptación

### CA-010.1: El idioma se detecta del sistema operativo
```gherkin
Dado un sistema con variables de entorno de locale definidas
Cuando se resuelve el idioma en modo auto
Entonces se usa el locale detectado, leyendo LC_ALL con prioridad
Y sin variables de entorno se usa el idioma por defecto
```
*Fuente: tests `[VERIFY: tests/test_i18n.py:48]`, `[VERIFY: tests/test_i18n.py:54]`, `[VERIFY: tests/test_i18n.py:38]`*

### CA-010.2: Un locale no soportado degrada a inglés, nunca falla
```gherkin
Dado un locale no soportado, detectado o configurado explícitamente
Cuando se resuelve el idioma
Entonces se usa inglés
Y una clave de traducción inexistente devuelve la propia clave en lugar de fallar
```
*Fuente: tests `[VERIFY: tests/test_i18n.py:34]`, `[VERIFY: tests/test_i18n.py:43]`, `[VERIFY: tests/test_i18n.py:16]`, `[VERIFY: tests/test_i18n.py:25]`*

### CA-010.3: La configuración puede forzar el idioma
```gherkin
Dado [notification] language con un valor soportado
Cuando se resuelve el idioma
Entonces se usa ese idioma en lugar del detectado del sistema
```
*Fuente: test `[VERIFY: tests/test_i18n.py:29]`; código `[VERIFY: src/vigia_eew/i18n.py:54]`*

### CA-010.4: Los textos admiten sustitución de valores
```gherkin
Dada una cadena traducida con marcadores de posición
Cuando se formatea con los valores del evento
Entonces el texto resultante los incorpora correctamente en ambos idiomas
```
*Fuente: test `[VERIFY: tests/test_i18n.py:20]`*

### CA-010.5: El código fuente está en inglés
```gherkin
Dado cualquier módulo del paquete
Cuando se revisa su código, docstrings y comentarios
Entonces están en inglés, y las cadenas de usuario pasan por la capa de traducción
```
*Fuente: `[COMMITS: 7f9132e]`; convención registrada en `[VERIFY: CLAUDE.md:1]`. **Sin test automatizado** — es una convención verificada por revisión.*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-010.1 | CA-010.1 | feliz | sistema en español | `LC_ALL=es_VE.UTF-8` | textos en español | `[VERIFY: tests/test_i18n.py:38]` |
| TC-010.2 | CA-010.1 | borde | LC_ALL vs LANG | ambas definidas | gana LC_ALL | `[VERIFY: tests/test_i18n.py:48]` |
| TC-010.3 | CA-010.1 | negativo | sin variables | entorno limpio | idioma por defecto | `[VERIFY: tests/test_i18n.py:54]` |
| TC-010.4 | CA-010.2 | negativo | locale `xx_XX` | no soportado | inglés | `[VERIFY: tests/test_i18n.py:43]` |
| TC-010.5 | CA-010.2 | negativo | clave inexistente | `"no.existe"` | devuelve la clave | `[VERIFY: tests/test_i18n.py:25]` |
| TC-010.6 | CA-010.3 | feliz | `language = "es"` | config | español pese al SO | `[VERIFY: tests/test_i18n.py:29]` |
| TC-010.7 | CA-010.4 | feliz | placeholders | magnitud y lugar | texto sustituido | `[VERIFY: tests/test_i18n.py:20]` |
| TC-010.8 | CA-010.5 | borde | revisión de fuentes | módulos de `src/` | inglés | No — añadir lint de idioma en v2 |

## Dependencias

- **Requiere**: HU-004 (los textos que se traducen son los de la capa de notificación)
- **Habilita**: ninguna directamente; afecta transversalmente a HU-004, HU-009 y HU-011

## Notas para la v2

**Lección principal del repositorio.** Nacer en inglés con i18n desde la fase 1 evita un `feat!`
que toca 30 archivos, renombra módulos y mueve assets binarios. El coste de hacerlo tarde no fue
solo el commit: rompió toda referencia previa a rutas de archivo en la documentación e historia.
