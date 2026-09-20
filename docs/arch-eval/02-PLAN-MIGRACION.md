# Plan de migración arquitectónica — vigia-eew

**Base:** `01-INFORME-EVALUACION.md` (commit `c3a2c29`) · **ADRs:** 3
**Alcance:** 1 debilidad P1, 4 P2, 5 P3. Ninguna es un fallo de corrección en producción.

Este es un plan de **endurecimiento incremental**, no una reescritura. La arquitectura actual es
correcta: cero ciclos, fronteras que la historia confirma, resiliencia verificada de punta a punta.
Lo que se corrige es su **coste de cambio** y una inconsistencia de concurrencia.

Fases ordenadas por (reducción de riesgo ÷ esfuerzo). Cada una es independiente y reversible.

---

## Fase 0 — Guardrails: hacer ejecutable el estado actual

**ADRs:** [ADR-003](adr/ADR-003-fronteras-ejecutables-con-import-linter.md)
**Prerequisitos:** ninguno · **Esfuerzo:** S (≈1 h)

Antes de mover una línea, fijar lo que hoy se cumple. Los cuatro contratos de import-linter pasan
en verde sobre el código actual sin tocarlo, así que esta fase **no puede romper nada** y protege
todas las siguientes.

Incluye también sacar `.venv_sandbox/` del árbol de trabajo (P3-4): mientras esté ahí, cualquier
análisis estático futuro arrastra 643 archivos y 211k LOC de ruido — este mismo informe tuvo que
corregirlo a mano.

**Done verificable:**
- `lint-imports` → 4 contratos en verde, 0 violaciones
- Prueba negativa: un import prohibido introducido a propósito **falla** el gate
- `python3 scripts/dep_graph.py . ` → sin el módulo huérfano `.venv_sandbox/lib`

**Rollback:** borrar la sección `[tool.importlinter]` y el hook. Sin efecto sobre el código.

---

## Fase 1 — Convertir P2-1 en evidencia determinista, y cerrarlo

**ADRs:** [ADR-002](adr/ADR-002-sincronizar-estado-compartido-de-application.md)
**Prerequisitos:** Fase 0 · **Esfuerzo:** S (≈1 h)

Va antes que el refactor grande por dos razones: es más barato, y porque ADR-001 va a mover el
código donde vive la carrera — arreglarlo primero evita arrastrar el defecto al sitio nuevo.

**Orden estricto:**

1. Escribir el test de regresión **primero**: monkeypatchear `_build_supervisor` con un retardo,
   lanzar `_run_loop` en un hilo, llamar a `_stop()` de inmediato y afirmar que `request_stop()` se
   invocó. **Debe fallar.** Este paso es el que convierte un hallazgo de lectura de código en
   evidencia determinista; si el test no falla, la premisa de ADR-002 es incorrecta y hay que
   revisar el ADR antes de seguir.
2. Aplicar el `Lock` + `Event` de ADR-002.
3. Documentar el contrato de hilos en `lat.md/architecture.md` y ejecutar `lat check`.

**Done verificable:**
- El test nuevo falla en `HEAD` y pasa tras el fix (evidencia registrada en el commit)
- `pytest` completo en verde, `mypy src` limpio
- `grep -n 'self._loop\|self._sup' src/vigia_eew/app.py` → toda lectura/escritura cruzada, bajo lock

**Rollback:** `git revert`. Cambio local y aditivo a `app.py`.

---

## Fase 2 — Registro de fuentes (corte mínimo de ADR-001)

**ADRs:** [ADR-001](adr/ADR-001-extraer-cableado-de-application.md), alternativa (d)
**Prerequisitos:** Fases 0 y 1 · **Esfuerzo:** S–M

Captura la mayor parte del beneficio recurrente de ADR-001 con la mitad del riesgo, y es
**verificable con la propia historia**: el flujo "añadir una fuente" se ejerció cuatro veces
`[COMMITS: fc0ca99, 10bb72d, ade1199]`.

Sustituir la escalera de `[VERIFY: src/vigia_eew/pipeline/normalize.py:55]` y las cuatro `lambda`
de `[VERIFY: src/vigia_eew/app.py:117]` por un registro `dict[Source, SourceSpec]` en
`ingest/__init__.py`.

**Done verificable:**
- Añadir una fuente ficticia en un test toca **3 puntos** (ingestor, mapper, entrada del registro),
  frente a los ≥5 de hoy
- `pytest` en verde **sin modificar ningún test existente** — es un refactor sin cambio de
  comportamiento
- El contrato 4 de import-linter (ingestores independientes) sigue en verde

**Rollback:** `git revert`. Si el registro resulta más opaco que la escalera en la práctica,
volver atrás es legítimo: la escalera es explícita y solo tiene cuatro ramas.

---

## Fase 3 — Extraer el cableado a `wiring.py`

**ADRs:** [ADR-001](adr/ADR-001-extraer-cableado-de-application.md), decisión completa
**Prerequisitos:** Fases 0–2 · **Esfuerzo:** M (media jornada)

Mover las seis funciones de fábrica (`_build_supervisor`, `_build_geo_filter`, `_build_controller`,
`_build_tray`, `_resolve_user_country`, `_resolve_automatic_reference`) a el futuro `src/vigia_eew/wiring.py`.
`Application` conserva los tres modos y la gestión de hilos.

**Decidir antes de empezar** si esta fase se ejecuta o se difiere a la v2 — ver §Conciliación.

**Done verificable (métricas, no impresiones):**
- `vigia_eew.app` con **fan-out ≤ 8** al re-ejecutar el análisis a nivel de archivo (hoy: 25)
- `wiring` con fan-in 1
- `lizard src/vigia_eew/app.py` → NLOC < 300 (hoy: 450)
- `pytest` en verde **sin tocar ningún test**; `mypy src` limpio
- Los 4 contratos de import-linter en verde, incluido el que fija `app` como sumidero

**Rollback:** `git revert` de un único commit. El movimiento no cambia comportamiento, así que la
suite existente es a la vez criterio de aceptación y red de seguridad.

**Riesgo:** el único real es hacerlo *a la vez* que un cambio funcional. Regla: este commit no
añade ni quita comportamiento; si el diff toca lógica, se parte en dos.

---

## Fase 4 — Observabilidad: ID de correlación

**ADRs:** ninguno (P3-1, no justifica un ADR) · **Prerequisitos:** Fase 2 · **Esfuerzo:** S

Propagar un identificador de correlación desde `RawMessage` hasta el log de la alerta, para poder
responder "¿qué pasó con este sismo?" cuando llega por dos fuentes y una se deduplica.

Se sitúa aquí y no antes porque es la única mejora del plan que **añade** un campo al contrato
interno, y conviene hacerlo después de que el registro de fuentes esté estable.

**Done verificable:** `grep 'corr=' vigia-eew.log` permite reconstruir el recorrido completo de un
evento —ingesta, normalización, filtro, veredicto de dedup, presentación— con una sola búsqueda.

---

## Fases descartadas explícitamente

| Propuesta | Por qué NO está en el plan |
|---|---|
| Reestructurar en `core/` + `adapters/` + `app/` | Mueve 19 archivos para resolver un problema que a nivel de archivo **no existe**: 0 ciclos. El ciclo que motivaría el cambio es un falso positivo del análisis por directorio (ver §Hallazgos descartados del informe) |
| Extraer los ingestores a procesos o servicios | Ninguna justificación operativa: un mantenedor, un proceso por máquina, y ADR-008 ya descartó el relay central por SPOF. La complejidad distribuida se paga a diario |
| Contenedor de inyección de dependencias | ADR-001, alternativa (b): dependencia de runtime e indirección sobre un grafo de 40 módulos que cabe en la cabeza |
| Clase base compartida para los pollers FDSN | Con dos implementaciones, la regla de tres no se cumple. ADR-016 ya lo difirió con criterio; reevaluar con una quinta fuente |
| Partir `StateStore` (P3-2) | 12 métodos públicos sobre un único documento es una fachada, no un god object. Sin evidencia de co-cambio que sugiera una costura. Documentarlo en `lat.md` es suficiente |

**Balance de complejidad:** de las cuatro fases, tres **retiran** complejidad (`app.py` 450→~200
líneas, escalera→registro, carrera→invariante explícita) y una **añade** una dependencia de
desarrollo y ~30 líneas de configuración (import-linter). El plan no introduce ninguna capa, ni
servicio, ni tecnología nueva en runtime.

---

## Conciliación con `docs/reverse-sdd/05-PLAN-RECONSTRUCCION.md`

Ese plan describe una **v2 reconstruida desde cero**; este describe **cambios incrementales sobre
el código actual**. Reparto propuesto, para que no compitan:

| Cambio | Dónde aterriza | Razón |
|---|---|---|
| ADR-003 (fronteras ejecutables) | **Aquí**, Fase 0 | Cuesta 1 h y protege el código que existe hoy. Esperar a una v2 es regalar el intervalo |
| ADR-002 (sincronización) | **Aquí**, Fase 1 | Es un defecto en el código actual; la v2 heredaría el patrón si no se corrige y documenta |
| ADR-001 registro de fuentes | **Aquí**, Fase 2 | Beneficio inmediato en el flujo de cambio más frecuente del proyecto |
| ADR-001 extracción de `wiring` | **Decidir** | Si la v2 va en serio y arranca pronto, entra como **decisión de diseño** de su Fase 5 (que ya anticipaba "un registro declarativo de fuentes y flags"). Si la v2 es una intención a largo plazo, se ejecuta aquí como Fase 3 |
| ID de correlación (P3-1) | **Aquí**, Fase 4, y como requisito de la v2 | Barato ahora; en la v2 pertenece al Data Model desde el diseño |
| Frontend D-Bus (ADR-010, sin implementar) | **En la v2**, su Fase 4 | Es la decisión de mayor alcance sin estimar del proyecto; no es un refactor, es una capacidad nueva |

**Regla para no duplicar:** todo lo que este plan ejecute debe reflejarse en
`05-PLAN-RECONSTRUCCION.md` §1 como "reconstruido a paridad" en vez de "rediseñado".

---

## Seguimiento

| Fase | ADR | Esfuerzo | Métrica de "Done" | Estado |
|---|---|---|---|---|
| 0 · Guardrails | ADR-003 | S | 4 contratos en verde + prueba negativa falla | pendiente |
| 1 · Sincronización | ADR-002 | S | Test de carrera falla antes, pasa después | pendiente |
| 2 · Registro de fuentes | ADR-001 (d) | S–M | Añadir fuente = 3 puntos (hoy ≥5) | pendiente |
| 3 · `wiring.py` | ADR-001 | M | `app` fan-out 25 → ≤8; NLOC 450 → <300 | a decidir |
| 4 · Correlación | — | S | Un `grep` reconstruye el flujo de un evento | pendiente |

**Ruta crítica realista:** Fases 0 a 2 son tres tareas pequeñas — una jornada cierra el P2 de
concurrencia, hace ejecutables las fronteras y reduce a la mitad el coste de añadir una fuente.
La Fase 3 es la única que requiere una decisión previa sobre la v2.
