# Tasks — Vigía-eew v2, Fases 0 a 2

> Specs de origen: [Constitution](00-CONSTITUTION.md) · [PRD](01-PRD.md) · [API Spec](02-API-SPEC.md) · [Tech Design](03-TECHNICAL-DESIGN.md) · [Data Model](04-DATA-MODEL.md) · [Plan](05-IMPLEMENTATION-PLAN.md)
> Cubre: **Fases 0, 1 y 2** del plan · Generado: 2026-09-06

Las fases 3 a 8 generan su propio archivo de tareas al llegar a ellas. Desglosar 56 REQ de una vez
produciría una lista de 100+ tareas que nadie ejecuta ni revisa.

## Convenciones

- El orden es el de ejecución, salvo las marcadas **[P]** (paralelizables: sin dependencia mutua ni
  archivos compartidos).
- Estados: `[ ]` pendiente · `[~]` en curso · `[x] AAAA-MM-DD` hecha · `[!]` bloqueada.
- Cada tarea cita su REQ. Una tarea sin REQ sobra o falta el requisito.

---

## Fase 0 — Guardrails

### [ ] T-001 · Esqueleto del proyecto y gate mínimo
- **Qué**: estructura `src/`+`tests/`, `pyproject.toml` con Python ≥3.12, **todos los rangos de
  dependencia con techo superior** y `uv.lock` versionado.
- **REQ**: Constitución §Restricciones del stack
- **Depende de**: —
- **Done**: `uv sync` reproducible desde el lock; `ruff check` y `ruff format --check` en verde.

### [ ] T-002 · Gate de las ocho dimensiones **[P]**
- **Qué**: `.pre-commit-config.yaml` completo — partir del propuesto en
  `docs/code-audit/.pre-commit-config.yaml.propuesto` (23 hooks, ya validado) y añadir
  `lint-imports`.
- **REQ**: REQ-OBS-003, REQ-OBS-004
- **Done**: `pre-commit validate-config` sin errores; `pre-commit run --all-files` en verde.

### [ ] T-003 · Umbral de cobertura que muerde
- **Qué**: `[tool.coverage.report]` con `fail_under` global y umbrales por módulo (85/70/40 según
  Plan F1); job de CI que lo exige.
- **REQ**: REQ-OBS-003
- **Depende de**: T-001 (modifica el `pyproject.toml` que aquella crea)
- **Done**: bajar artificialmente la cobertura hace fallar el CI. **Sin esta comprobación negativa
  la tarea no está hecha.**

### [ ] T-004 · Contratos de fronteras
- **Qué**: los cuatro contratos de import-linter de TD-05 en `pyproject.toml`.
- **REQ**: REQ-OBS-005, REQ-ING-010
- **Depende de**: T-001
- **Done**: `lint-imports` en verde **y** un import prohibido introducido a propósito lo hace fallar.

### [ ] T-005 · Validación de assets de empaquetado **[P]**
- **Qué**: script que verifica formato y dimensiones de los recursos antes de invocar al
  empaquetador, integrado en el pipeline de build.
- **REQ**: REQ-OPS-007
- **Done**: un PNG deliberadamente inválido hace fallar el build con un mensaje que lo nombra.
- **Nota**: rompió dos releases de la v1 (`7b1c71c`, `c38d9f6`); es la tarea de mejor relación
  coste/valor de esta fase.

---

## Fase 1 — Núcleo

### [ ] T-006 · Contrato interno `SeismicEvent`
- **Qué**: modelo con validación de UTC tz-aware, rechazo de naive, severidad y distancia derivadas,
  y `correlation_id` **desde el inicio**.
- **REQ**: REQ-PIP-001, REQ-OBS-002 (parte de modelo), INV-1
- **Depende de**: T-001
- **Archivos**: `src/vigia_eew/models.py`, `tests/test_models.py`
- **Done**: los 10 casos de HU-001 portados y en verde; un `datetime` naive es rechazado.

### [ ] T-007 · Utilidades de tiempo local **[P]**
- **Qué**: día local y medianoche local con zona configurable y reloj inyectado; fail-safe ante zona
  inválida.
- **REQ**: REQ-PIP-004, REQ-PIP-006, Art. 4
- **Depende de**: T-006
- **Done**: el caso "21:00 hora local es hoy aunque en UTC sea mañana" en verde.

### [ ] T-008 · Configuración validada
- **Qué**: esquema de configuración por secciones, carga TOML de solo lectura, fallo explícito ante
  configuración o ruta inválidas.
- **REQ**: REQ-CFG-005
- **Depende de**: T-006
- **Done**: los casos de configuración de HU-001 y HU-013 en verde.

### [ ] T-009 · Estado persistido con poda cableada
- **Qué**: almacén de estado con escritura atómica, cursores monótonos, y **poda invocada desde el
  registro de alerta en el mismo commit que la introduce**.
- **REQ**: REQ-CFG-001..004, INV-2, INV-3, INV-4
- **Depende de**: T-006
- **Done**: INV-2 verificada con estado envejecido; INV-4 comprueba que no quedan temporales.
- **Nota**: en la v1 la poda existió 14 fases sin llamador (`b0f832c`). El "Done" de esta tarea
  incluye una comprobación de alcanzabilidad: ninguna función pública del módulo queda sin llamador.

### [ ] T-010 · Registro estructurado en UTC **[P]**
- **Qué**: configuración de logging con marcas en UTC y claves estables por etapa, con hueco
  reservado para `corr=`.
- **REQ**: REQ-OBS-001
- **Depende de**: T-001
- **Done**: una entrada de ejemplo por etapa, con formato verificado en test.

---

## Fase 2 — Composición e ingesta base

### [ ] T-011 · Contrato `SourceSpec` y registro vacío
- **Qué**: el tipo del registro según API Spec §3, con el registro poblado solo por EMSC.
- **REQ**: REQ-ING-009
- **Depende de**: T-008
- **Done**: `mypy --strict` limpio sobre el contrato; el registro tiene exactamente una entrada.

### [ ] T-012 · `wiring` separado de `Application`
- **Qué**: módulo de composición que construye componentes desde configuración y estado; la clase de
  aplicación solo orquesta modos y ciclo de vida.
- **REQ**: TD-01 (soporta REQ-ING-009, REQ-OPS-003)
- **Depende de**: T-011
- **Done**: `app` con fan-out ≤ 8 y menos de 300 líneas, medido con el analizador de
  `docs/arch-eval/analysis/file_level_graph.txt`.

### [ ] T-013 · **Test de la carrera de apagado — debe fallar**
- **Qué**: test que retrasa la construcción del supervisor, lanza el bucle en un hilo e invoca la
  parada de inmediato, afirmando que la cancelación se solicita.
- **REQ**: REQ-OPS-002
- **Depende de**: T-012
- **Done**: **el test falla** contra una implementación sin sincronizar. Si pasa, la premisa de
  TD-04 es incorrecta y hay que revisar el diseño antes de seguir.

### [ ] T-014 · Sincronización del estado compartido
- **Qué**: lock más evento de "runtime listo"; la parada espera con tiempo límite y registra un
  aviso explícito si expira. Tabla de contrato de hilos en `lat.md/architecture.md`.
- **REQ**: REQ-OPS-002, REQ-OPS-003, Art. 6
- **Depende de**: T-013
- **Done**: T-013 pasa; `lat check` en verde; la tabla del API Spec §6 coincide con el código.

### [ ] T-015 · Supervisor con reinicio aislado
- **Qué**: orquestador de tareas de larga vida con backoff exponencial y jitter, que aísla fallos y
  cancela limpiamente.
- **REQ**: REQ-OPS-001, REQ-ING-002
- **Depende de**: T-012
- **Done**: los 4 casos de supervisor de HU-002 y el e2e E2E-5 en verde.

### [ ] T-016 · Ingestor push EMSC
- **Qué**: WebSocket persistente con keepalive, reconexión con backoff, y emisión al registro con
  `correlation_id` asignado.
- **REQ**: REQ-ING-001, REQ-ING-002, REQ-ING-006
- **Depende de**: T-015, T-011
- **Done**: los casos de HU-002 CA-002.1 y CA-002.2 en verde; cobertura del módulo ≥70 %.

### [ ] T-017 · Fuente REST con cursor (patrón base)
- **Qué**: primer poller con cursor persistido y piso en medianoche local; entra **por el registro**,
  sin tocar `wiring`.
- **REQ**: REQ-ING-003, REQ-ING-004, REQ-ING-007
- **Depende de**: T-016, T-009
- **Done**: añadir esta fuente toca **exactamente 3 puntos** — verificado por revisión del diff.

---

## Matriz de trazabilidad (Fases 0-2)

| REQ | Tareas | Pruebas de origen |
|---|---|---|
| REQ-PIP-001 | T-006 | HU-003 CA-003.1 |
| REQ-PIP-004, PIP-006 | T-007 | HU-016 CA-016.1..3 |
| REQ-CFG-001..004 | T-009 | HU-001 CA-001.3..5, HU-016 CA-016.6 |
| REQ-CFG-005 | T-008 | HU-001 CA-001.6 |
| REQ-ING-001, ING-002 | T-016 | HU-002 CA-002.1, CA-002.2 |
| REQ-ING-003, ING-004, ING-007 | T-017 | HU-002 CA-002.3, HU-016 CA-016.5 |
| REQ-ING-006 | T-016, T-017 | HU-002 CA-002.4 |
| REQ-ING-009, ING-010 | T-011, T-012, T-004 | nuevo: test de "3 puntos" |
| REQ-OPS-001 | T-015 | HU-002 CA-002.5, E2E-5 |
| REQ-OPS-002, OPS-003 | T-013, T-014 | **nuevo**: test de carrera |
| REQ-OPS-007 | T-005 | **nuevo**: TC-007.4 de la matriz de pruebas |
| REQ-OBS-001 | T-010 | nuevo |
| REQ-OBS-002 (modelo) | T-006 | nuevo |
| REQ-OBS-003, OBS-004 | T-002, T-003 | **nuevo**: prueba negativa del umbral |
| REQ-OBS-005 | T-004 | **nuevo**: prueba negativa de import-linter |

**Diferidos a fases posteriores** (con REQ, sin tarea aquí): todos los REQ-ALE (F4-F5), REQ-PIP-002
a 009 (F3), REQ-UX (F5), REQ-CFG-006..008 (F5), REQ-ING-005/008 (F6), REQ-OPS-004..006/008 (F8),
REQ-OBS-002 completo (F7).

## Primera tanda supervisada

**T-001 → T-005** (Fase 0 completa). Son independientes del diseño del producto, verificables en
aislamiento, y dejan el gate en pie antes de escribir la primera línea de dominio. Revisar el
resultado antes de escalar a la Fase 1.

Tres de las cinco tienen **comprobación negativa obligatoria** (T-003, T-004, T-005): el gate no
está hecho hasta que se demuestra que falla cuando debe.

## Registro de ejecución

| Fecha | Tareas | Resultado | Notas |
|---|---|---|---|
| — | — | — | Sin ejecutar: la v2 no ha comenzado |

Si al implementar se descubre que la spec está mal: **parar, abrir un Delta Spec en
`docs/sdd/changes/`, y solo entonces continuar** (Art. 9).
