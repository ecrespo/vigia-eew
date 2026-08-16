# 00 — Inventario y curaduría de clusters

> Generado por ingeniería inversa el 2026-08-16. Commit de referencia: `6e0f133`.
> Fuentes crudas: `analysis/inventory.{json,md}` y `analysis/history.{json,md}`.

## 1. Alcance del análisis

| Dimensión | Valor |
|---|---|
| Commits analizados | 59 totales; 47 no-merge procesados por el script |
| Rango temporal | 2026-06-28 → 2026-08-16 |
| Conventional commits | 97,9 % |
| LOC | Python 9.197 · YAML 455 · Shell 122 |
| Tests | 348 en 35 archivos bajo `tests/` |
| Tags git | **ninguno** — las eras se derivan por trimestre, no por release tag |
| Autores | Ernesto Crespo (46), Claude (1) |

**Nada fue truncado.** El repo está muy por debajo de los umbrales de escalado
(>2.000 commits / >200k LOC), así que se analizó el historial completo.

Este repositorio ya practica SDD hacia adelante: `docs/PRD.md`, `docs/API-SPEC.md`,
`docs/TECHNICAL-DESIGN.md` (18 ADRs), `docs/DATA-MODEL.md` e
`docs/IMPLEMENTATION-PLAN.md` existen y están vivos. La ingeniería inversa aquí no
rellena un vacío documental: **valida que los specs describen el código real** y produce
lo que faltaba — HUs con criterios de aceptación trazables a commits y tests.

### Capas de conocimiento disponibles

La exploración usó las tres capas ya instaladas en el repo en lugar de lectura cruda:
`lat.md/` (intención), `.codegraph/` (estructura, 1.387 nodos) y `graphify-out/`
(significado, 1.517 nodos). Esto es relevante para la v2: el kit de specs y las capas
son complementarios — los specs dicen qué construir, las capas mantienen el
entendimiento vivo después.

## 2. Corrección de la clusterización automática

El script agrupó por directorio dominante y **produjo clusters inservibles para HUs**:
`dir:src/vigia_eew` acumula 17 commits que incluyen las fases 1 a 6 más el filtro de
país — seis capacidades no relacionadas en un solo bucket.

La causa es que este repo commitea **una fase completa del plan por commit**, así que el
directorio dominante es siempre el mismo. La señal real de clustering no está en la ruta
sino en el asunto del commit, que nombra su fase y su requisito (`Fase 3`, `RF-37`).
Re-clusterizado sobre esa señal, la correspondencia es casi 1:1 entre commit y capacidad.

**Descartados de las HUs** (se conservan en `03-EVOLUCION.md`): merges de PR (12),
`chore: release` (10), y los commits meta `737d7fa` (artefactos SDD), `8e7b223`
(CLAUDE.md), `230b0b8` (diseño D-Bus sin código), `e49404d` (imports absolutos) y
`6e0f133` (capas de conocimiento).

## 3. Clusters curados → HUs

| HU | Capacidad | Commits | Fase original |
|---|---|---|---|
| HU-001 | Contrato interno de evento sísmico | `b5c5371` | Fase 1 |
| HU-002 | Estado persistente entre reinicios | `b5c5371`, `b0f832c` | Fase 1 + 15 |
| HU-003 | Configuración TOML validada y auto-sembrada | `b5c5371`, `a06f7a1` | Fase 1 + RF-24 |
| HU-004 | Observabilidad: logging estructurado | `b5c5371` | Fase 1 |
| HU-005 | Canal push EMSC en tiempo real | `fc0ca99` | Fase 2 |
| HU-006 | Reconciliación USGS con cursor persistido | `fc0ca99` | Fase 2 |
| HU-007 | Supervisión resiliente de tareas asyncio | `fc0ca99`, `f49d139` | Fase 2 + 7 |
| HU-008 | Normalización multi-fuente | `b40c20b` | Fase 3 |
| HU-009 | Filtrado por radio, magnitud y frescura | `b40c20b`, `b0f832c` | Fase 3 + 15 |
| HU-010 | Deduplicación intra e inter-fuente | `b40c20b` | Fase 3 |
| HU-011 | Alerta de escritorio no descartable | `fb50326`, `f90c796`, `f0960ac` | Fase 4 |
| HU-012 | Sonido y toast nativo por severidad | `fb50326` | Fase 4 |
| HU-013 | CLI, ensamblaje y modo simulación | `4fb49d0` | Fase 5 |
| HU-014 | Autoarranque multiplataforma | `5b79ff1` | Fase 6 |
| HU-015 | Empaquetado y distribución | `b6413e3`, `7b1c71c`, `c38d9f6`, `bdc2a9d`, `a02607f` | Fase 8 |
| HU-016 | Ubicación automática por IP | `c20a59b` | Fase 9 |
| HU-017 | Ícono de bandeja del sistema | `fb3fe14` | Fase 10 |
| HU-018 | Internacionalización | `7f9132e` | RF-35 |
| HU-019 | Dashboard TUI headless | `7f98980`, `651c024` | Fase 11 |
| HU-020 | Filtro de notificación por país | `a3a4a1a` | Fase 12 |
| HU-021 | Fuente local FUNVISIS | `10bb72d` | RF-38 |
| HU-022 | Fuente global GEOFON | `ade1199`, `8e0064a` | Fase 14 |

22 HUs para 22 capacidades. Cada commit no descartado aparece en **exactamente una** HU;
`b5c5371`, `fc0ca99`, `b40c20b`, `fb50326` y `b0f832c` aparecen en varias porque cada uno
entregó varias capacidades separables (verificable: cada una tiene su propio archivo de
tests).

## 4. Señales del historial que se convierten en criterios

Archivos con fixes recurrentes — el skill los trata como candidatos a criterio de
aceptación P1 y a rediseño:

| Archivo | Fixes | Qué revela |
|---|---|---|
| `packaging/build_linux.sh` | 2 | El ícono placeholder rompía AppImage/linuxdeploy dos veces seguidas (`7b1c71c`, `c38d9f6`) → el empaquetado necesita validar sus assets, no asumirlos |
| `src/vigia_eew/notify/alert_window.py` | 2 | Dos bugs de layout seguidos (`f90c796` hora recortada, `f0960ac` contenido contra el borde) → el contenido de la alerta debe medirse, no estimarse |
| `src/vigia_eew/tray.py` | 2 | Fallos de arranque en entornos sin display |
| `pyproject.toml` | 2 | Dependencias faltantes en el binario congelado (`bdc2a9d`) |

Los cuatro se convirtieron en criterios de aceptación explícitos en HU-015 y HU-011.

**Hotspots** (`CHANGELOG.md` 22 toques, `pyproject.toml` 17,
`docs/IMPLEMENTATION-PLAN.md` 14, `app.py` 11, `config.py` 10) son en su mayoría archivos
de coordinación, no deuda: se tocan en cada fase por diseño. La excepción a vigilar es
`app.py` — ver la nota de acoplamiento en `01-ARQUITECTURA.md` §5.

## 5. Confianza del análisis

La proporción de afirmaciones marcadas `[INFERIDO]` en el kit es baja (<5 %) y se
concentra en las **personas/roles** de las HUs, que los commits no nombran. Todo lo
demás está anclado a código o a un hash. Las razones son favorables y poco habituales:
el repo tiene conventional commits al 97,9 %, un test suite de 348 casos que documenta
el comportamiento esperado, y 18 ADRs que ya registran el *porqué* con sus alternativas
rechazadas.
