# HU-018: Internacionalización del texto de usuario

> **Cluster de origen:** RF-35 (breaking change) · **Commits:** 1 `[COMMITS: 7f9132e]`
> **Período:** 2026-07-04 · **Era:** Era 2 — Contexto del usuario

## Historia

**Como** usuario que no habla inglés `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** ver la alerta en mi idioma sin configurar nada
**Para** entender de inmediato qué está pasando, que es justo cuando no hay tiempo de traducir mentalmente

## Contexto de la implementación original

Este commit es el más invasivo del historial: marcado `feat!` (breaking), tradujo **todo
el código base** del español al inglés e introdujo la capa de i18n a la vez. El proyecto
había nacido con identificadores, docstrings y comentarios en español.

`t()` `[VERIFY: src/vigia_eew/i18n.py:64]` traduce e interpola; `resolve_locale`
`[VERIFY: src/vigia_eew/i18n.py:54]` decide el idioma efectivo, con `"auto"` detectando el
locale del SO `[VERIFY: src/vigia_eew/i18n.py:37]`. La regla del proyecto queda invertida
respecto al origen: **el código en inglés, el texto de usuario traducido**, con las
cadenas inglesas como fuente de verdad y el español enviado junto a ellas.

## Criterios de aceptación

### CA-018.1: Por defecto se responde en inglés
```gherkin
Dado una clave de traducción sin locale explícito
Cuando se traduce
Entonces devuelve el texto en inglés
```
*Fuente: test `[VERIFY: tests/test_i18n.py:8]`*

### CA-018.2: Se traduce al español cuando se solicita
```gherkin
Dado una clave y el locale español
Cuando se traduce
Entonces devuelve el texto en español
```
*Fuente: test `[VERIFY: tests/test_i18n.py:12]`*

### CA-018.3: Un locale no soportado cae a inglés
```gherkin
Dado un locale sin traducción disponible
Cuando se traduce
Entonces devuelve el texto en inglés en vez de fallar
```
*Fuente: tests `[VERIFY: tests/test_i18n.py:16]`,
`[VERIFY: tests/test_i18n.py:34]`, `[VERIFY: tests/test_i18n.py:43]` — degradar a inglés
es preferible a mostrar una clave cruda o lanzar durante una alerta*

### CA-018.4: Los placeholders se interpolan
```gherkin
Dado una cadena con marcadores y sus valores
Cuando se traduce
Entonces los marcadores se sustituyen
```
*Fuente: test `[VERIFY: tests/test_i18n.py:20]`*

### CA-018.5: Una clave desconocida devuelve la clave
```gherkin
Dado una clave que no existe en ningún catálogo
Cuando se traduce
Entonces devuelve la propia clave, sin lanzar
```
*Fuente: test `[VERIFY: tests/test_i18n.py:25]` — una alerta con texto raro es mucho
mejor que una alerta que no aparece*

### CA-018.6: `"auto"` usa el locale detectado del sistema
```gherkin
Dado language = "auto" en configuración
Cuando se resuelve el locale
Entonces usa el detectado del SO, cayendo a inglés si no está soportado
```
*Fuente: tests `[VERIFY: tests/test_i18n.py:38]`,
`[VERIFY: tests/test_i18n.py:43]`*

### CA-018.7: Un locale explícito y soportado se respeta
```gherkin
Dado language con un idioma soportado
Cuando se resuelve el locale
Entonces se usa ese, ignorando el del sistema
```
*Fuente: test `[VERIFY: tests/test_i18n.py:29]`*

### CA-018.8: La detección del SO respeta la precedencia de variables de entorno
```gherkin
Dado LC_ALL definido
Cuando se detecta el locale del sistema
Entonces LC_ALL tiene precedencia; y sin ninguna variable, se usa el valor por defecto
```
*Fuente: tests `[VERIFY: tests/test_i18n.py:48]`,
`[VERIFY: tests/test_i18n.py:54]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-018.1 | CA-018.1 | feliz | Sin locale | clave | Inglés | `[VERIFY: tests/test_i18n.py:8]` |
| TC-018.2 | CA-018.2 | feliz | Español | locale=es | Español | `[VERIFY: tests/test_i18n.py:12]` |
| TC-018.3 | CA-018.3 | borde | Locale no soportado | fr | Inglés | `[VERIFY: tests/test_i18n.py:16]` |
| TC-018.4 | CA-018.4 | feliz | Interpolación | `{mag}` | Sustituido | `[VERIFY: tests/test_i18n.py:20]` |
| TC-018.5 | CA-018.5 | negativo | Clave inexistente | `"nope"` | Devuelve `"nope"` | `[VERIFY: tests/test_i18n.py:25]` |
| TC-018.6 | CA-018.6 | feliz | auto soportado | LANG=es | Español | `[VERIFY: tests/test_i18n.py:38]` |
| TC-018.7 | CA-018.6 | borde | auto no soportado | LANG=de | Inglés | `[VERIFY: tests/test_i18n.py:43]` |
| TC-018.8 | CA-018.7 | feliz | Explícito | language=es | Español | `[VERIFY: tests/test_i18n.py:29]` |
| TC-018.9 | CA-018.8 | borde | LC_ALL precede | LC_ALL + LANG | Gana LC_ALL | `[VERIFY: tests/test_i18n.py:48]` |
| TC-018.10 | CA-018.8 | borde | Sin variables | entorno limpio | Default | `[VERIFY: tests/test_i18n.py:54]` |
| TC-018.11 | CA-018.2 | negativo | **Catálogo incompleto**: clave presente en inglés y ausente en español | clave nueva sin traducir | Cae a inglés, no a la clave cruda | **escribir en v2** |

## Dependencias

- **Requiere**: HU-012 (los textos que se traducen)
- **Habilita**: alcance internacional del producto

## Notas para la v2

**Nacer en inglés con i18n desde el día uno.** Esta migración fue un breaking change que
tocó todo el árbol y arrastró consigo otro commit de limpieza (imports absolutos,
`e49404d`); hacerla al principio cuesta una fracción.

TC-018.11 es el hueco relevante para el mantenimiento: no hay test ni verificación de que
los catálogos estén sincronizados. Una clave añadida en inglés y olvidada en español
degradaría silenciosamente. En la v2, una comprobación de paridad de catálogos en CI
resuelve esto por unos pocos euros de esfuerzo.
