# ADR-001 — Extraer el cableado de `Application` a un módulo de composición

**Estado:** propuesto · **Fecha:** 2026-09-06 · **Debilidad:** P1-1 (y P2-4)
**Atributos:** evolutividad, cohesión

## Contexto

`app.py::Application` es a la vez la raíz de composición del sistema y el punto por el que entra
toda feature nueva. La evidencia:

- `[METRIC: analysis/file_level_graph.txt → vigia_eew.app importa 25 de los 40 módulos (62,5 %);
  el segundo mayor fan-out del repositorio es 5]`
- `[METRIC: analysis/file_level_graph.txt § co-cambio → app.py ↔ config.py 7 co-cambios (0,70);
  app.py ↔ cli.py 6 (0,67), sobre los 47 commits sin merges]`
- `[VERIFY: src/vigia_eew/app.py:85-195]` — 111 de sus 450 líneas son fábricas
  (`_build_supervisor`, `_build_geo_filter`, `_build_controller`, `_build_tray`)
- `[COMMITS: c20a59b, fb3fe14, 7f98980, a3a4a1a, 10bb72d, ade1199, b0f832c]` — las 7 features
  posteriores a v0.1.0 lo tocaron

**No es un problema de tamaño.** 450 líneas no justifican nada por sí solas. El problema es que
la clase mezcla **dos razones de cambio**: cambia cuando se añade un componente (fábricas) y
cuando cambia un modo de ejecución (`execute` / `run_tui` / `simulate`). El historial muestra que
la primera razón se ejerció siete veces.

## Decisión

Separar por razón de cambio, sin crear capas nuevas:

1. **futuro `src/vigia_eew/wiring.py`** — recibe `Settings` y `StateStore`, devuelve los componentes ya
   construidos. Se lleva `_build_supervisor`, `_build_geo_filter`, `_build_controller`,
   `_build_tray`, `_resolve_user_country` y `_resolve_automatic_reference`.
2. **`Application`** queda como orquestador de los tres modos: pide sus piezas a `wiring`, gestiona
   los hilos y el ciclo de vida. Estimado: ~200 líneas.
3. **Registro de fuentes** (cierra P2-4): un `dict[Source, SourceSpec]` en `ingest/__init__.py`
   con, por fuente, su clase de config, su fábrica de ingestor y su mapper de normalización.
   `wiring` itera el registro en vez de enumerar cuatro `lambda`, y `Normalizer` lo consulta en
   vez de la escalera `if/elif` de `[VERIFY: src/vigia_eew/pipeline/normalize.py:55]`.

**La costura viene del grafo, no de la intuición.** Las seis funciones que se mueven son
exactamente las que importan los 25 módulos; `execute`/`run_tui`/`simulate` solo importan
`threading`, `asyncio` y las piezas ya construidas. Tras el corte, el fan-out se reparte
aproximadamente 25 → `wiring` ~20 / `app` ~6, y `wiring` queda con fan-in 1.

## Alternativas consideradas

**(a) No hacer nada.** Defendible con seriedad: el sistema funciona, tiene 344 pruebas en verde y
`mypy --strict` limpio; ninguno de los siete cambios que tocaron `app.py` introdujo un bug —
`[METRIC: arch_signals.json.fix_prone_files → app.py no aparece: 0 commits de tipo fix]`. El coste del
acoplamiento se ha pagado en esfuerzo de edición, no en defectos. Si el proyecto no va a añadir
más fuentes ni frontends, esta alternativa es la correcta y este ADR debe rechazarse.
Se descarta **solo porque** `docs/reverse-sdd/05-PLAN-RECONSTRUCCION.md` contempla una v2 con
fuentes adicionales y con el frontend D-Bus del ADR-010 pendiente: son al menos dos features más
por la misma costura.

**(b) Contenedor de inyección de dependencias** (`dependency-injector`, `punq`). Resolvería el
cableado de forma declarativa, pero añade una dependencia de runtime y un nivel de indirección
que hay que aprender, sobre un grafo de 40 módulos que cabe en la cabeza. Contradice RNF-06
(núcleo Python portable y mínimo). **Rechazada.**

**(c) Un módulo de fábrica por subsistema** (`ingest/factory.py`, `notify/factory.py`, …). Reparte
mejor, pero multiplica los puntos donde mirar para entender el arranque, que hoy es una de las
virtudes del proyecto. **Rechazada** por desproporcionada para 40 módulos.

**(d) Solo el registro de fuentes, sin mover el cableado.** Cierra P2-4 (de 5 archivos a 3) y
cuesta la mitad. Es una alternativa **legítima** si hay poco tiempo: captura la mayor parte del
beneficio recurrente. Queda registrada como el corte mínimo aceptable de este ADR.

## Consecuencias

**Positivas:** añadir una fuente pasa de tocar ≥5 archivos a tocar el ingestor nuevo, su mapper y
una entrada del registro. `Application` vuelve a tener una sola razón de cambio. La costura
`wiring` es exactamente donde los tests de `test_app.py` ya inyectan dobles.

**Negativas:** un módulo más que leer para entender el arranque. `git blame` sobre las 111 líneas
movidas apuntará al commit de refactor. Y el registro de fuentes introduce una indirección: leer
el mapper de GEOFON exige un salto más que hoy.

**Lo que NO se toca:** `models.py`, `state.py`, `pipeline/`, `notify/` y `ingest/*` no cambian.
No se crea ninguna capa ni interfaz nueva. `AlertController` sigue recibiendo los tres callbacks
tal cual `[VERIFY: src/vigia_eew/notify/controller.py:35]`.

## Coste y reversibilidad

**Coste:** M (media jornada) para el corte completo; S solo para la alternativa (d).
**Reversibilidad: alta.** Es un movimiento de código sin cambio de comportamiento: la suite
existente es el criterio de aceptación. Revertir es un `git revert`.
**Verificación:** `pytest` en verde sin modificar ningún test; `mypy src` limpio; y
`vigia_eew.app` con fan-out ≤ 8 al re-ejecutar el análisis de dependencias.
