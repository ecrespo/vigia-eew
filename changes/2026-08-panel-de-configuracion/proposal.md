# Propuesta — Panel de configuración y selección de redes desde la bandeja

> Estado: **borrador** · Fecha: 2026-08-16
> Specs base afectadas: `docs/PRD.md` (RF-24, RF-34), `docs/TECHNICAL-DESIGN.md`
> (ADR-007, ADR-012, ADR-016), `docs/DATA-MODEL.md` §3, `docs/reverse-sdd/HU/HU-003`,
> `HU-017`, `HU-021`, `HU-022`

## Problema / motivación

Hoy, "Editar configuración" en la bandeja abre `config.toml` con el editor de texto del
sistema `[VERIFY: src/vigia_eew/tray.py:52]`. Eso implica tres cosas para el usuario:

1. **Tiene que saber TOML.** Un error de sintaxis o un valor fuera de rango no se detecta
   al guardar, sino en el siguiente arranque — y el agente no arranca.
2. **No hay descubrimiento.** Nada le dice qué claves existen ni qué rangos son válidos;
   la única guía son los comentarios del archivo.
3. **Las cuatro redes sísmicas son invisibles.** Para saber que existen EMSC, USGS,
   GEOFON y FUNVISIS —y qué aporta cada una— hay que leer `config.toml.example` o los
   ADRs. Un usuario en Chile no tiene forma de descubrir que FUNVISIS no le sirve y que
   podría añadir su red nacional.

La evidencia de que esto importa: `config.py` es el hotspot de código #3
`[METRIC: 10 toques, churn 505]`, y la mayoría de las features de las eras 3 a 5 añadieron
claves de configuración. La configuración es la superficie que más crece.

## Alcance

**Cambia:**

- Se añade un **panel de configuración** (diálogo Tkinter) accesible desde la bandeja, con
  las claves que un usuario ajusta de verdad: radio, magnitud mínima, umbrales de
  severidad, sonido, idioma, zona horaria, filtro de país y "solo hoy".
- Se añade un **selector de redes sísmicas** dentro de ese panel, que lista las cuatro
  fuentes con su cobertura y tipo, y permite activarlas o desactivarlas.
- Se añade la capacidad de **registrar una red FDSN adicional** por URL, reutilizando el
  camino ya probado de USGS/GEOFON.
- La escritura de `config.toml` pasa de no existir a existir, **preservando los
  comentarios** del archivo (ver Impacto).

**NO cambia:**

- El contrato de la alerta (Art. 1 de la constitución): este panel no toca la
  presentación ni el reconocimiento.
- La edición manual de `config.toml` sigue funcionando y sigue siendo la vía para las
  claves avanzadas (endpoints, intervalos de poll, umbrales de dedup). El panel es un
  atajo para lo común, no un reemplazo.
- El pipeline, el dedup y el supervisor no se modifican.
- No se añade ninguna llamada de red nueva.

## Impacto

**Sobre ADR-007 (config de solo lectura).** ADR-007 decidió `tomllib` explícitamente
porque "escribir configuración no hace falta en v1". Esta propuesta **contradice esa
decisión** y por tanto exige un ADR nuevo que la reemplace parcialmente, no un cambio
silencioso. La restricción real es que `tomllib` no escribe, así que hay tres caminos:

| Opción | Coste | Riesgo |
|---|---|---|
| Añadir `tomli-w` como dependencia de runtime | 1 dep más, excepción a RNF-06 | **Destruye los comentarios** del archivo al reescribirlo |
| Escritor propio del subconjunto gestionado | ~150 líneas + tests | Mismo problema de comentarios si se reescribe entero |
| **Edición quirúrgica en sitio**: localizar la clave y sustituir solo su valor, dejando el resto del archivo byte a byte | ~120 líneas + tests | Ninguno para los comentarios; hay que manejar el caso "la clave no existe aún" |

Se propone la tercera. Los comentarios de `config.toml.example` no son decorativos:
explican por qué FUNVISIS va por HTTP plano y por qué `[reference]` viene comentada
`[VERIFY: src/vigia_eew/config.toml.example:59]`. Perderlos degradaría el producto.

**Sobre ADR-016 (unificar los pollers FDSN).** ADR-016 difirió extraer un poller FDSN
común "hasta que se añada una tercera fuente FDSN". **Registrar redes FDSN por URL es
exactamente esa tercera fuente**, así que esta propuesta activa el disparador que el ADR
dejó escrito. La unificación deja de ser deuda opcional y pasa a ser prerrequisito
técnico — lo mismo que ya señalan `code-audit` R-07 y `arch-eval` DEB-P3.

**Sobre qué se aplica en caliente y qué exige reinicio.** Es la parte del diseño que más
fácilmente se promete de más:

- **En caliente**: radio, magnitud, severidad, país, "solo hoy", sonido, idioma. Se leen
  por evento o por presentación, así que basta con reemplazar el objeto de configuración.
- **Exige reinicio**: activar o desactivar una red, y añadir una FDSN nueva. Las tareas de
  ingesta se cablean al arrancar el supervisor `[VERIFY: src/vigia_eew/app.py:85]`.
  Reconstruirlas en vivo sería un cambio de arquitectura mucho mayor y no se propone aquí.
  El panel **DEBE decírselo al usuario**, no simularlo.

**Compatibilidad**: aditiva. Un `config.toml` existente sigue siendo válido; las claves
nuevas tienen defaults. No hay migración de datos.

## Constitution check

| Artículo | Cómo se cumple |
|---|---|
| Art. 1 (alerta no descartable) | No se toca la capa de alerta |
| Art. 2 (ante la duda, no suprimir) | Si el archivo guardado no valida, se conserva la configuración anterior y se avisa; nunca se queda el agente con un filtro roto |
| Art. 3 (fallo parcial no tumba) | El panel es best-effort como la bandeja: si Tk no puede abrirlo, se registra y el agente sigue |
| Art. 4 (UTC) | La zona horaria configurable solo afecta a presentación y día local, como hoy |
| Art. 5 (fronteras) | El panel vive en la capa de frontends; no importa nada de `pipeline/` |
| Art. 6 (efectos inyectados) | La función de guardado y la de recarga se inyectan; el panel se testea sin escribir en disco real |
| Art. 7 (privacidad) | Sin llamadas nuevas. Registrar una red FDSN añade un destino elegido **por el usuario**, no por el producto |
| Art. 8 (spec e intención) | Este delta + ADR-023 (escritura de config) y ADR-024 (registro de redes) antes de implementar |
