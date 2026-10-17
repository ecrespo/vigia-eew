# Evaluación de arquitectura — vigia-eew

**Fecha:** 2026-09-06 · **Commit:** `c3a2c29` · **Sistema:** agente de escritorio, un proceso por
máquina, asyncio + Tkinter/Textual, 4 fuentes sísmicas, sin base de datos ni servicio remoto.

**Evidencia determinista:** `analysis/dep_graph.json` (40 módulos-archivo, 97 aristas de import) y
`analysis/arch_signals.json` (47 commits sin merges, 22 pares de co-cambio, bus factor por módulo).
Cruzado con `docs/reverse-sdd/analysis/history.json` y con `docs/CONTEXT_REPORT.md` (Graphify).

---

## Resumen ejecutivo

La arquitectura **cumple lo que su documentación promete**: cuatro capas con fronteras reales, un
contrato interno único, y dependencias que fluyen en una sola dirección. La evidencia lo respalda
con dos datos fuertes: **cero ciclos de dependencia a nivel de archivo** y **cero pares de
co-cambio entre módulos de producción** en toda la historia.

El hallazgo de mayor impacto es de **evolutividad, no de corrección**: `app.py` importa 25 de los
40 módulos del sistema (62,5 %), cinco veces más que el siguiente, y arrastra a `config.py` y
`cli.py` en cada feature con confianza de co-cambio 0,70. **Cada capacidad nueva cuesta tres
archivos**, y esos tres archivos son los que más han cambiado del código de producción.

El segundo hallazgo es de disciplina de concurrencia: `Application` comparte dos campos mutables
(`_loop`, `_sup`) entre el hilo de Tk y el hilo de asyncio **sin sincronización**, mientras que el
mismo proyecto sí protege con `Lock` el estado equivalente en `AgentState`. La ventana de fallo es
estrecha y el GIL impide lecturas rotas, pero el apagado limpio puede saltarse.

**Dos hallazgos de las herramientas fueron descartados tras verificarlos en el código**, incluido
el ciclo de dependencias que el script marca como evidencia P1: es un artefacto de granularidad de
directorio, no existe a nivel de archivo.

---

## Scorecard de atributos de calidad

Ponderación: este sistema vive de **resiliencia** (nunca perder un evento, nunca morir) y
**evolutividad** (añadir fuentes y frontends). No maneja dinero, ni datos de usuario, ni
transacciones multi-tabla: consistencia de datos y seguridad pesan menos, y se puntúan como tal.

| # | Atributo | Peso | Veredicto | Evidencia |
|---|---|---|---|---|
| 1 | Acoplamiento y fronteras | alto | 🟡 | `[METRIC: analysis/file_level_graph.txt → 0 ciclos (SCC) a nivel de archivo entre 40 módulos y 97 aristas]` y `[METRIC: arch_signals.json.temporal_coupling_pairs → ninguno de los 22 pares relaciona dos archivos de producción de módulos distintos]`. Pero `[METRIC: analysis/file_level_graph.txt → app.py fan-out 25/40]` y `[GAP: ninguna regla enforce las fronteras — no hay import-linter ni equivalente]` |
| 2 | Cohesión y responsabilidad | alto | 🟡 | El paquete raíz `src/vigia_eew` agrupa 19 archivos y 1.771 LOC mezclando dominio (`models`, `geo`), aplicación (`app`, `cli`), infraestructura (`state`, `geoloc`) y UI (`tray`, `tui`), mientras que solo 4 preocupaciones recibieron subpaquete `[METRIC: dep_graph.json.modules]`. `app.py` concentra 15 de sus 28 métodos en cableado `[VERIFY: src/vigia_eew/app.py:85-195]` |
| 3 | Testabilidad | alto | 🟢 | Inyección sistemática de relojes, `sleep`, clientes y los tres efectos de notificación `[VERIFY: src/vigia_eew/notify/controller.py:35]`. Los módulos de mayor fan-in tienen test propio: `config` (14) → `tests/test_config.py`, `models` (14) → `tests/test_models.py`. Cada fix recurrente dejó test de regresión `[VERIFY: tests/test_alert_window.py:157]` |
| 4 | Resiliencia e integraciones | **crítico** | 🟢 | Supervisor que reinicia cada tarea con backoff aislando fallos `[VERIFY: src/vigia_eew/supervisor.py:79]`; timeouts y `Retry-After` en las 3 integraciones REST `[VERIFY: src/vigia_eew/ingest/rest_usgs.py:157]`; deduplicación cruzada como idempotencia de presentación `[VERIFY: src/vigia_eew/pipeline/dedup.py:45]`; degradación *fail-safe* consistente en toast, bandeja y geolocalización |
| 5 | Datos y consistencia | bajo | 🟡 | Escritura atómica del estado `[VERIFY: src/vigia_eew/state.py:61]`, todo `datetime` tz-aware UTC validado `[VERIFY: src/vigia_eew/models.py:25]`, poda acotada a 24 h `[VERIFY: src/vigia_eew/pipeline/dedup.py:56]`. Ámbar por el estado compartido sin lock del hallazgo P2-1, no por los datos persistidos |
| 6 | Observabilidad | medio | 🟡 | Logging estructurado por evento con timestamps en UTC `[VERIFY: src/vigia_eew/logging_conf.py:23]` y claves consistentes (`alert_shown id=…`, `normalize_discarded source=…`). **Sin ID de correlación**: un mismo sismo que llega por dos fuentes no se puede seguir como un solo flujo en los logs `[VERIFY: src/vigia_eew/pipeline/processor.py:54]`. Sin métricas ni alertas |
| 7 | Seguridad | bajo | 🟢 | Sin superficie de autenticación (no hay servidor ni datos de usuario). Toda entrada externa se valida por pydantic en el borde `[VERIFY: src/vigia_eew/models.py:51]`; subprocess siempre con listas literales y entorno saneado `[VERIFY: src/vigia_eew/subprocess_env.py:25]`. 0 secretos en árbol e historia y 0 CVE de runtime — ver `docs/code-audit/01-INFORME-AUDITORIA.md` |
| 8 | Evolutividad y despliegue | **crítico** | 🔴 | `[METRIC: analysis/file_level_graph.txt § co-cambio → app.py+config.py co-cambian 7 veces, confianza 0,70; app.py+cli.py 6 veces, 0,67]`. Añadir una fuente obliga a tocar ≥5 archivos `[VERIFY: src/vigia_eew/pipeline/normalize.py:55]`. `[METRIC: arch_signals.json.bus_factor_by_module → 15/15 módulos con un único autor al 100 %]`. La CI sí tiene gates reales |

---

## Fortalezas

1. **Cero ciclos de dependencia reales.** `[METRIC: analysis/file_level_graph.txt → 0 SCC entre 40
   módulos y 97 aristas de import]`. Todas las dependencias fluyen hacia el núcleo estable; ningún
   subpaquete importa `app.py` salvo `cli.py`.
2. **Abstracciones estables donde deben estarlo.** `config` y `models` tienen fan-in 14 y **fan-out
   0** `[METRIC: analysis/file_level_graph.txt § fan-in]`: no dependen de nada del sistema. Es el principio de dependencias
   estables cumplido de forma exacta, no aproximada.
3. **Fronteras que la historia confirma.** De los 15 pares de co-cambio "entre módulos" que reporta
   el script, **ninguno** relaciona dos archivos de producción de módulos distintos: todos son
   fuente↔su propio test o documento↔documento `[METRIC: arch_signals.json.temporal_coupling_pairs]`.
   Las fronteras de `ingest/`, `pipeline/` y `notify/` no tienen fugas históricas.
4. **Resiliencia como decisión estructural, no como manejo de errores.** El patrón
   "supervisor que reinicia hijos" `[VERIFY: src/vigia_eew/supervisor.py:79]` con backoff
   compartido `[VERIFY: src/vigia_eew/backoff.py:18]` está verificado de punta a punta
   `[VERIFY: tests/test_resilience.py:186]`.
5. **La costura de test está en el sitio correcto.** Los tres efectos de notificación son callbacks
   inyectables `[VERIFY: src/vigia_eew/notify/controller.py:35]`, y por eso los dos frontends (Tk y
   Textual) reutilizan el mismo controlador sin duplicar lógica `[VERIFY: src/vigia_eew/app.py:312]`.
6. **Un solo contrato cruzando capas.** `SeismicEvent` con campos derivados siempre calculados
   `[VERIFY: src/vigia_eew/models.py:51]`: cuatro fuentes heterogéneas convergen sin lógica
   *source-aware* aguas abajo del normalizador.
7. **Arquitectura documentada y sincronizada.** 18 ADRs numerados en `docs/TECHNICAL-DESIGN.md`, con
   dos escritos retroactivamente y admitidos como tales. La documentación describe el sistema que
   existe, no el que se quiso construir.

---

## Debilidades rankeadas

### P1-1 · `app.py` es simultáneamente raíz de composición y god-module

- **Atributo degradado:** 8 (evolutividad), 2 (cohesión)
- **Evidencia:**
  - `[METRIC: analysis/file_level_graph.txt → vigia_eew.app importa 25 de los 40 módulos (62,5 %);
    el segundo mayor fan-out del repositorio es 5]`
  - `[METRIC: analysis/file_level_graph.txt § co-cambio → app.py ↔ config.py: 7 co-cambios,
    confianza 0,70; app.py ↔ cli.py: 6 co-cambios, 0,67. Cómputo directo sobre los 47 commits sin
    merges; este par es intra-módulo y por eso no aparece en la tabla de `arch_signals.md`]`
  - `[VERIFY: src/vigia_eew/app.py:85-195]` — 111 líneas de fábricas (`_build_supervisor`,
    `_build_geo_filter`, `_build_controller`, `_build_tray`) dentro de la misma clase que gestiona
    los tres modos de ejecución
  - `[COMMITS: c20a59b, fb3fe14, 7f98980, a3a4a1a, 10bb72d, ade1199, b0f832c]` — las 7 features
    posteriores a la v0.1.0 tocaron `app.py`
- **Radio de impacto:** máximo del sistema. Coincide con el segundo nodo de mayor intermediación
  del grafo semántico (`docs/CONTEXT_REPORT.md`: `Application`, betweenness 0,136).
- **Por qué importa:** no es que el archivo sea grande — es que **es la única costura por la que
  entra toda feature nueva**. El coste ya se pagó siete veces y el historial lo demuestra.
- **Propuesta:** → [ADR-001](adr/ADR-001-extraer-cableado-de-application.md)

### P2-1 · Estado compartido entre hilos sin sincronizar en `Application`

- **Atributo degradado:** 4 (resiliencia), 5 (consistencia)
- **Evidencia:**
  - `[VERIFY: src/vigia_eew/app.py:420]` y `[VERIFY: src/vigia_eew/app.py:431]` — `self._loop` y
    `self._sup` se **escriben desde el hilo trabajador** de asyncio
  - `[VERIFY: src/vigia_eew/app.py:443]` — `_stop()` los **lee desde el hilo de Tk**; si el usuario
    sale antes de que el trabajador termine de asignar, la condición
    `self._loop is not None and self._sup is not None` es falsa y **`request_stop()` nunca se
    invoca**: el `join(timeout=5.0)` de la línea 445 expira y el apagado no es limpio
  - `[VERIFY: src/vigia_eew/app.py:298]` — segunda lectura cruzada: `publish_toast` corre en el
    hilo de Tk y lee `self._loop` para `run_coroutine_threadsafe`
  - **Contraste interno:** `[VERIFY: src/vigia_eew/agent_state.py:18]` — el propio proyecto sí
    protege con `threading.Lock` el estado compartido equivalente. El patrón correcto existe y no
    se aplicó aquí
- **Radio de impacto:** acotado al arranque y al apagado del modo GUI. El modo `--tui` no está
  afectado (un solo event loop, sin puente). El GIL de CPython impide lecturas rotas, así que **no
  hay corrupción de datos**; el riesgo real es un apagado sucio.
- **Severidad:** P2 y no P1 deliberadamente. La regla de evidencia de esta metodología limita a P2
  los hallazgos sostenidos por lectura de código, y la ventana de fallo es de milisegundos. La
  Fase 1 del plan de migración convierte esto en evidencia determinista con un test que falla.
- **Propuesta:** → [ADR-002](adr/ADR-002-sincronizar-estado-compartido-de-application.md)

### P2-2 · Las fronteras entre paquetes no son ejecutables

- **Atributo degradado:** 1 (fronteras)
- **Evidencia:** `[GAP: no existe import-linter, ni regla de ruff equivalente, ni test de
  arquitectura en el repositorio]`. La disciplina que el grafo confirma hoy
  `[METRIC: file_level_graph.txt → 0 ciclos; arch_signals.json → 0 co-cambios cruzados de producción]` está sostenida **solo por convención y
  por tener un único autor**.
- **Radio de impacto:** todo el sistema, de forma diferida: nada impide que el primer colaborador
  externo introduzca un import de `notify` dentro de `pipeline`.
- **Propuesta:** → [ADR-003](adr/ADR-003-fronteras-ejecutables-con-import-linter.md)

### P2-3 · Bus factor 1 en el 100 % de los módulos

- **Atributo degradado:** 8 (evolutividad)
- **Evidencia:** `[METRIC: arch_signals.json.bus_factor_by_module → los 15 módulos con actividad tienen un único
  autor al 100 %]`
- **Radio de impacto:** organizacional, no técnico. Para un proyecto personal es lo esperado; para
  una herramienta de la que alguien depende para su seguridad física, es el riesgo de continuidad
  más alto del inventario.
- **Mitigación disponible, sin ADR:** ya está parcialmente atendida — los 18 ADRs y la capa de
  intención `lat.md/` registran el *porqué* que no está en el código, que es exactamente lo que se
  pierde cuando el autor único desaparece. Completarla es cuestión de continuidad documental, no de
  arquitectura.
- **Riesgo aceptado** mientras el proyecto siga siendo de un solo mantenedor.

### P2-4 · Añadir una fuente cuesta cinco archivos

- **Atributo degradado:** 8 (evolutividad), 2 (OCP)
- **Evidencia:** `[VERIFY: src/vigia_eew/pipeline/normalize.py:55]` (escalera `if/elif` sobre
  `msg.source`) más `[VERIFY: src/vigia_eew/models.py:20]` (el `Literal`),
  `[VERIFY: src/vigia_eew/config.py:150]` (el campo de config),
  `[VERIFY: src/vigia_eew/app.py:117]` (la fábrica) y el módulo ingestor nuevo.
- **Radio de impacto:** el flujo de cambio más frecuente del proyecto — se ejerció 4 veces
  `[COMMITS: fc0ca99, 10bb72d, ade1199]`.
- **Propuesta:** incluido en [ADR-001](adr/ADR-001-extraer-cableado-de-application.md) como registro
  de fuentes; ya recogido como P3-3 en `docs/code-audit/01-INFORME-AUDITORIA.md`.

### P3 · Batch de consistencia

| # | Debilidad | Atributo | Evidencia |
|---|---|---|---|
| P3-1 | Sin ID de correlación en logs: un sismo reportado por dos fuentes no se sigue como un flujo | 6 | `[VERIFY: src/vigia_eew/pipeline/processor.py:54]` |
| P3-2 | `StateStore` expone 12 métodos públicos sobre un único documento | 2 | `[VERIFY: src/vigia_eew/state.py:33]` |
| P3-3 | Duplicación estructural entre los dos pollers FDSN (39 líneas) | 1 | `[METRIC: jscpd — ver docs/code-audit/analysis/jscpd-report.json]` |
| P3-4 | `.venv_sandbox/` (643 archivos, 211k LOC) está en el árbol de trabajo y contamina cualquier análisis estático | 8 | `[METRIC: dep_graph.json.orphan_modules → `.venv_sandbox/lib`, 643 archivos]` |
| P3-5 | El lambda `paused` de la bandeja lee `AlertQueue._paused` desde el hilo de pystray sin lock | 5 | `[VERIFY: src/vigia_eew/app.py:185]` — lectura de un `bool`, atómica bajo el GIL; se anota por consistencia con ADR-002 |

---

## Hallazgos de las herramientas descartados

Documentados para que la próxima auditoría no vuelva a litigarlos.

| Reporte de la herramienta | Verificación en Fase 1 | Veredicto |
|---|---|---|
| **`dep_graph.py`: 1 ciclo (SCC) entre `src/vigia_eew` y sus 4 subpaquetes, marcado "evidencia P1"** | Análisis a nivel de **archivo** sobre los mismos 40 módulos: **0 ciclos**. El SCC es un artefacto de agrupar por directorio: los subpaquetes importan *hacia arriba* al núcleo estable (`models`, `config`, `state`, que viven en el paquete raíz) y `app.py` — que también vive en el raíz — importa *hacia abajo* a los subpaquetes. Ningún archivo participa en un ciclo | **Falso positivo.** No es un ciclo, es la consecuencia de tener el núcleo estable en el paquete raíz en vez de en un subpaquete `core/`. La causa real está recogida como P1-1 y ADR-001 |
| `dep_graph.py`: god-module `src/vigia_eew` (fan-in 6, fan-out 4, 1.771 LOC) | El módulo-directorio no es la unidad útil aquí: mezcla 19 archivos con responsabilidades distintas. A nivel de archivo el problema se concentra en uno solo | **Reformulado**, no descartado: es P1-1 con la métrica correcta (`app.py` fan-out 25) |
| `dep_graph.py`: módulo huérfano `.venv_sandbox/lib` | Es un entorno virtual en el árbol de trabajo, no versionado | **Falso positivo** del alcance del escaneo. Anotado como P3-4 |
| `arch_signals.py`: 15 pares de co-cambio "entre módulos", marcados "evidencia P1" | Revisados uno a uno: 9 son documento↔documento (disciplina SDD), 5 son fuente↔su propio test (sano y deseable), 1 es `CHANGELOG.md`↔`build_linux.sh` (rutina de release) | **Falsos positivos** como señal de frontera. El único par de producción cruzado, `models.py`↔`tests/test_config.py` (n=3, 0,6), es un test de config que valida modelos: acoplamiento de test, no de arquitectura |
| `arch_signals.py`: hotspot #1 `CHANGELOG.md` (22 toques, score 132) | Un changelog se toca en cada release por definición | **Falso positivo** estructural |

---

## Conciliación con el resto de `docs/`

- **`docs/code-audit/`** — coincidimos en el diagnóstico de `Application` (allí P3-2 por tamaño,
  aquí P1-1 por acoplamiento) y en la duplicación FDSN. La auditoría de código no podía ver el
  fan-out ni el co-cambio; esta evaluación no podía ver la cobertura ni los CVE. Ninguna
  contradice a la otra.
- **`docs/reverse-sdd/05-PLAN-RECONSTRUCCION.md`** — su Fase 5 ya anticipaba "un registro
  declarativo de fuentes y flags" para `app.py`/`config.py`/`cli.py`. ADR-001 le da la costura
  concreta y la evidencia métrica que allí faltaba. Ver §4 del plan de migración para decidir si
  esto entra como cambio incremental o como decisión de diseño de la v2.
- **`docs/CONTEXT_REPORT.md`** — Graphify sitúa `Application` como segundo nodo de mayor
  intermediación (0,136) y `SeismicEvent` como primero (0,105). El primero es el problema (P1-1);
  el segundo es la fortaleza n.º 6.
