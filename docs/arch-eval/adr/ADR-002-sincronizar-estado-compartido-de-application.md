# ADR-002 — Sincronizar el estado que `Application` comparte entre hilos

**Estado:** propuesto · **Fecha:** 2026-09-06 · **Debilidad:** P2-1
**Atributos:** resiliencia, consistencia

## Contexto

En modo GUI, `Application` reparte trabajo entre tres hilos: el principal (Tkinter), un trabajador
(asyncio) y el de la bandeja (pystray). Dos campos mutables cruzan esa frontera **sin ninguna
sincronización**:

- `self._loop` se asigna en el hilo trabajador `[VERIFY: src/vigia_eew/app.py:420]`
- `self._sup` se asigna en el hilo trabajador `[VERIFY: src/vigia_eew/app.py:431]`
- `_stop()` los lee desde el hilo de Tk `[VERIFY: src/vigia_eew/app.py:443]`
- `publish_toast()` lee `self._loop` desde el hilo de Tk `[VERIFY: src/vigia_eew/app.py:298]`

El fallo concreto: si el usuario sale (Ctrl-C, o "Salir" en la bandeja) antes de que el trabajador
haya asignado `self._sup`, la guarda `self._loop is not None and self._sup is not None` es falsa,
**`request_stop()` no se invoca nunca**, y el `join(timeout=5.0)` de la línea 445 expira. El
proceso termina igualmente porque el hilo es *daemon*, pero sin cancelar las tareas de ingesta ni
cerrar limpiamente el event loop.

**El propio proyecto ya resolvió este problema bien en otro sitio.** `AgentState` protege con
`threading.Lock` exactamente el mismo tipo de estado compartido entre esos mismos tres hilos
`[VERIFY: src/vigia_eew/agent_state.py:18]`. La inconsistencia es la señal: no falta criterio,
falta aplicarlo.

**Calibración honesta del riesgo.** El GIL de CPython garantiza que estas lecturas no pueden
devolver un valor roto, así que **no hay corrupción de datos ni pérdida de eventos**. La ventana
es de milisegundos, entre `thread.start()` (línea 408) y la asignación de la línea 431. El daño
máximo es un apagado sucio en un arranque abortado muy rápido.

## Decisión

Sustituir las dos asignaciones cruzadas por un **`threading.Event` de "runtime listo"** más un
`Lock` para los dos campos, siguiendo el patrón que `AgentState` ya establece:

1. `Application.__init__` crea `self._runtime_lock = threading.Lock()` y
   `self._runtime_ready = threading.Event()`.
2. `_run_loop` asigna `_loop` y `_sup` **bajo el lock** y solo entonces hace `set()` del evento.
3. `_stop` espera `self._runtime_ready.wait(timeout=2.0)` antes de leer; si expira, registra un
   warning explícito (`shutdown_before_runtime_ready`) en lugar de saltarse el apagado en silencio.
4. `publish_toast` lee `_loop` bajo el mismo lock.

Adicionalmente, documentar el contrato de hilos en `lat.md/architecture.md`: qué campo pertenece a
qué hilo y cuál es la única forma de cruzarlo.

## Alternativas consideradas

**(a) No hacer nada.** Argumentable de verdad: en 47 commits y todo el uso real del agente esto
**nunca se ha manifestado** — `[METRIC: arch_signals.json.fix_prone_files → app.py no aparece: 0 commits de tipo fix]`. El GIL elimina la clase de fallo más grave, y el daño residual (un apagado
sucio en un caso de esquina) es cosmético. Un equipo con poco tiempo haría bien en priorizar
ADR-001 sobre este. Se descarta porque el coste del fix es de una hora, es puramente aditivo, y
deja el código consistente consigo mismo — lo cual importa más de lo habitual en un repositorio
con bus factor 1, donde la consistencia de patrones es lo que permite a un futuro mantenedor
razonar sin leerlo todo.

**(b) Pasar `loop` y `sup` como valores de retorno en vez de campos.** Más limpio en teoría, pero
`_run_loop` corre en un hilo: no hay retorno que recoger sin una `Future` o una cola, que es
sincronización con otro nombre y menos legible. **Rechazada.**

**(c) Arrancar el event loop antes que la UI** y pasarlo ya construido a `Application`. Elimina la
carrera de raíz y es arquitectónicamente más limpio. Pero invierte el orden de arranque que ADR-006
fijó (Tk dueño del hilo principal) y toca `execute`, `simulate` y `run_tui`. **Rechazada por ahora**
por desproporcionada; reconsiderar si ADR-001 reordena el arranque de todos modos.

**(d) Marcar los campos como `volatile`/atómicos.** No existe en Python. Mencionada solo para
descartar la intuición de quien venga de Java o Go.

## Consecuencias

**Positivas:** el apagado deja de depender del *timing*; el fallo, si ocurre, queda registrado en
lugar de ser silencioso; el contrato de hilos queda escrito y verificable.

**Negativas:** dos primitivas de sincronización más que entender. `_stop` puede tardar hasta 2 s
extra en el caso patológico — aceptable en una ruta de apagado.

**Lo que NO se toca:** `AgentState`, `AsyncioTkBridge` y `AlertQueue` ya son correctos. El modo
`--tui` no está afectado: corre sobre un único event loop sin puente
`[VERIFY: src/vigia_eew/app.py:369]`.

## Coste y reversibilidad

**Coste:** S (≈1 h), incluido el test de regresión.
**Reversibilidad: alta.** Cambio aditivo y local a `app.py`.
**Verificación:** un test que monkeypatchea `_build_supervisor` con un retardo, lanza `_run_loop`
en un hilo e invoca `_stop()` de inmediato. **Debe fallar antes del fix y pasar después** — eso es
lo que convierte este hallazgo de lectura de código en evidencia determinista.
