# Plan de migración arquitectónica — Vigía-eew

> Deriva de `01-INFORME-EVALUACION.md` (commit `8660eea`) y de los ADR-019 a ADR-021.
> Fases ordenadas por **reducción de riesgo ÷ esfuerzo**, no por dependencia técnica.

## Postura de fondo: evolucionar, no reconstruir

Ninguna de las seis debilidades justifica un rediseño. La arquitectura demostró
empíricamente que absorbe cambio —dos fuentes sísmicas y dos frontends entraron sin
deformarla— y no tiene ni un ciclo real. Lo que falta no es estructura: es **hacer
verificable la estructura que ya existe**.

Por eso las tres fases de abajo suman, en total, alrededor de dos días de trabajo, y las
dos primeras son reversibles con un `git revert`.

### Reconciliación con `docs/reverse-sdd/05-PLAN-RECONSTRUCCION.md`

Aquel plan describe una v2 desde cero; éste describe cambios incrementales sobre el código
actual. **No compiten** — se reparten así:

| Cambio | Dónde aterriza | Por qué |
|---|---|---|
| ADR-019 (núcleo/composición) | **Aquí**, incremental · y como estructura de partida de la v2 | Es mover archivos; hacerlo hoy es barato y la v2 nacería ya con la separación |
| ADR-020 (import-linter) | **Aquí**, incremental · y en la Fase 0 de la v2 | Cuesta 2 horas y protege la fortaleza #1 desde hoy |
| ADR-021 (config única) | **Aquí**, incremental | No tiene nada que ver con reconstruir; es deuda de proceso |
| Decisión sobre Wayland (RR-3) | **Solo en la v2** (`05-PLAN-RECONSTRUCCION.md` Fase 4) | Es una decisión de plataforma, no de estructura; puede cambiar el frontend entero |
| Unificar los pollers FDSN | **Ninguno de los dos todavía** | ADR-016 lo difirió a la tercera fuente FDSN; `[METRIC: jscpd → 0,85 %]` no lo justifica hoy |
| Partir `app.py` | `docs/code-audit/02-PLAN-REMEDIACION.md` R-04 | Es cohesión de un archivo, no arquitectura de módulos. Ya está planificado allí, después de ADR-019 |

Si la v2 llega a existir, `05-PLAN-RECONSTRUCCION.md` §2 debe adoptar `core/` +
import-linter como decisiones de partida, no re-derivarlas.

---

## Fase 0 — Guardrails (hacer el estado actual exigible)

**Objetivo**: que la arquitectura de hoy no se pueda erosionar mientras se trabaja en las
fases siguientes. Nada de esto mueve código de producción.

| # | Acción | ADR | Esfuerzo |
|---|---|---|---|
| 0.1 | Añadir `import-linter` al grupo `dev` y **solo el contrato 3**: `pipeline` y los módulos del núcleo no pueden importar `httpx`, `websockets`, `tkinter`, `pystray`, `textual` ni `subprocess` | ADR-020 (parcial) | 1 h |
| 0.2 | Colgar `lint-imports` del gate de pre-commit, junto a ruff y mypy | ADR-020 | 15 min |
| 0.3 | Test de paridad entre las claves de `Settings` y las de `config.toml.example` | ADR-021 (Alt. B) | 2 h |

- **Prerrequisitos**: ninguno. **El contrato 3 no depende de ADR-019** — funciona con la
  estructura de directorios actual, y esa es la razón de empezar por él.
- **Done verificable**: `lint-imports` en verde · `pytest -k config_parity` en verde ·
  ambos hooks bloqueando en un commit de prueba que introduzca `import httpx` en
  `pipeline/filter.py`.
- **Rollback**: borrar el archivo de contratos y el hook. No hay nada que deshacer en
  `src/`.

> Si el proyecto solo va a hacer **una** cosa de este plan, que sea la Fase 0. Cuesta tres
> horas y protege la propiedad de la que depende el 89 % de cobertura.

## Fase 1 — Separar núcleo de composición

**Objetivo**: que el árbol de directorios exprese la dirección de dependencias, y que el
falso ciclo desaparezca de todas las herramientas de análisis.

| # | Acción | ADR | Esfuerzo |
|---|---|---|---|
| 1.1 | Crear `src/vigia_eew/core/` y mover los 9 módulos del núcleo (lista exacta en ADR-019) | ADR-019 | 3 h |
| 1.2 | Mover `RawMessage` de `ingest/__init__.py` a `core/` — elimina la arista `pipeline → ingest` | ADR-019 | 30 min |
| 1.3 | Actualizar imports (`ruff --fix` cubre la mayor parte) y correr el gate completo | — | 1 h |
| 1.4 | Ampliar los contratos de import-linter a los 3 completos, ahora que `core` es un paquete | ADR-020 | 30 min |

- **Prerrequisitos**: Fase 0 completa (el contrato 3 ya vigila que el movimiento no
  introduzca dependencias nuevas por accidente).
- **Done verificable, con métrica**:
  - `python3 scripts/dep_graph.py .` → **ciclos SCC: 1 → 0**
  - aristas del grafo: **15 → 14** (desaparece `pipeline → ingest`)
  - `src/vigia_eew` deja de aparecer en "candidatos a god-module"
  - `pytest -q` → 345 passed · `mypy src` → sin errores · `lat check` → en verde
- **Rollback**: `git revert` del commit. Es un movimiento de archivos sin cambio de
  comportamiento; el revert es limpio por construcción.
- **Riesgo**: conflictos con cualquier rama abierta. **Hacerlo cuando no haya trabajo en
  vuelo**, y en un commit propio que no mezcle nada más.

## Fase 2 — Fuente única del esquema de configuración

**Objetivo**: que añadir una clave cueste dos sitios en vez de seis.

| # | Acción | ADR | Esfuerzo |
|---|---|---|---|
| 2.1 | Migrar los comentarios artesanales de `config.toml.example` a docstrings de los campos de `Settings`, **con revisión humana** — es el paso donde se puede perder calidad | ADR-021 | 4 h |
| 2.2 | Script en `packaging/` que genere la plantilla desde el modelo | ADR-021 | 2 h |
| 2.3 | Verificación en CI: regenerar y comparar; si difiere, falla | ADR-021 | 1 h |
| 2.4 | Sustituir las tablas de claves de los 4 documentos por la tabla generada o un enlace; **conservar intactas las secciones de decisión** | ADR-021 | 2 h |

- **Prerrequisitos**: 0.3 (el test de paridad ya habrá revelado cualquier divergencia
  pendiente antes de automatizar).
- **Done verificable**: `packaging/build_config_example.py && git diff --exit-code
  src/vigia_eew/config.toml.example` → sin cambios · en la siguiente ejecución de
  `arch_signals.py` tras 3-4 releases, los pares `config.toml.example ↔ docs/*` deberían
  desaparecer de la tabla de co-cambio.
- **Rollback**: dejar de generar y volver a editar a mano. **Asimetría a tener presente**:
  si las docstrings quedaron peor que los comentarios originales, eso no se revierte solo —
  por eso 2.1 lleva revisión y va primero.

## Lo que este plan deliberadamente NO hace

| No se hace | Por qué |
|---|---|
| Partir `app.py` | Es cohesión de archivo, no de módulos. Está en `code-audit` R-04, y depende de que ADR-019 aterrice antes |
| Unificar `RESTReconciler` y `GEOFONPoller` | `[METRIC: jscpd → 0,85 % duplicado]` está en verde y ADR-016 difirió la abstracción a la tercera fuente FDSN. Abstraer con dos casos es la trampa clásica |
| Introducir capas de dominio/aplicación al estilo hexagonal | El sistema ya tiene la separación que necesita. Añadir puertos y adaptadores para cuatro integraciones que **no varían en tipo** sería abstracción sin variación real |
| Extraer cualquier servicio | ADR-008 (un agente por máquina, sin relay) sigue siendo correcto y este informe no aporta ni una evidencia en contra |
| Tocar el modelo `SeismicEvent` | Es la fortaleza estructural del sistema; absorbió dos fuentes nuevas sin cambiar |

## Balance de complejidad

Guarda del skill: si las propuestas que **añaden** complejidad dominan a las que la
**quitan**, hay que recortar.

| Añade complejidad | Quita complejidad |
|---|---|
| `import-linter` (1 dependencia dev + 1 archivo de contratos) | Elimina 1 arista del grafo (`pipeline → ingest`) |
| Script generador de la plantilla (1 paso de release) | Elimina el ciclo SCC falso (1 → 0) |
| | Baja el costo de una clave de config de 6 sitios a 2 |
| | Elimina el candidato a god-module |
| **2 adiciones, ambas de tooling** | **4 reducciones, todas estructurales** |

Ninguna propuesta añade capas, servicios, tecnología nueva de runtime ni abstracciones.
Las dos adiciones son herramientas de verificación, que es la categoría de complejidad que
se paga una vez.

## Seguimiento

| Fase | Ítem | Métrica de verificación | Estado |
|---|---|---|---|
| 0 | Contrato "dominio sin infraestructura" | `lint-imports` en verde | pendiente |
| 0 | Hook en pre-commit | bloquea un `import httpx` de prueba en `pipeline/` | pendiente |
| 0 | Test de paridad de config | `pytest -k config_parity` | pendiente |
| 1 | Núcleo movido a `core/` | ciclos SCC 1→0; aristas 15→14 | pendiente |
| 1 | `RawMessage` reubicado | arista `pipeline → ingest` ausente | pendiente |
| 1 | Contratos completos | 3 contratos en verde | pendiente |
| 2 | Docstrings migradas | revisión humana del diff | pendiente |
| 2 | Plantilla generada | `git diff --exit-code` tras regenerar | pendiente |
| 2 | Docs sin tablas duplicadas | co-cambio `config.toml.example ↔ docs/*` → 0 | pendiente |
