# Análisis del historial git

**Repo:** `/home/user/vigia-eew` · **Commits:** 47 (2026-06-28 → 2026-08-16) · **Conventional commits:** 97.9%

## Eras (base para 03-EVOLUCION.md)

| Era | Desde | Hasta | Commits | Tipos dominantes |
|---|---|---|---|---|
| 2026-Q2 | 2026-06-28 | 2026-06-28 | 7 | feat:5, docs:1, other:1 |
| 2026-Q3 | 2026-07-03 | 2026-08-16 | 40 | feat:11, chore:10, fix:8 |

## Clusters de features (base para las HUs — CURAR antes de usar)

### `dir:(raiz)` — 20 commits, churn 3743
*2026-06-28 → 2026-07-17* · hashes: `737d7fa`…`bd4a555`
- docs: artefactos SDD, scaffolding y ARCHITECTURE (Fase 0)
- Initial commit
- fix: ícono placeholder de resolución inválida rompía linuxdeploy (v0.1.2)
- fix: icono placeholder inválido rompía el build de AppImage (v0.1.1)
- chore: release v0.1.0
- docs: agrega CLAUDE.md con guía de desarrollo para el repo
- chore: release v0.2.1
- chore: release v0.2.0

### `dir:src/vigia_eew` — 17 commits, churn 20364
*2026-06-28 → 2026-08-16* · hashes: `4fb49d0`…`6e0f133`
- feat: CLI, ensamblaje del agente y modo --simulate (Fase 5)
- feat: capa de notificación (Fase 4)
- feat: pipeline de normalización, filtro y dedup (Fase 3)
- feat: ingestión EMSC/USGS y supervisor asyncio (Fase 2)
- feat: estructura, modelos, config, estado y logging (Fase 1)
- feat: autoarranque multiplataforma y flags de CLI (Fase 6)
- feat: country notification filter (RF-37, Phase 12)
- fix: sanitize LD_LIBRARY_PATH when spawning system binaries (PyInstaller onefile)

### `dir:.github` — 6 commits, churn 110
*2026-07-05 → 2026-07-05* · hashes: `559f077`…`5ee3b1d`
- ci: run ci on PRs to main; document PR-based release flow
- fix: make the agent import-safe on a headless host (RF-36)
- ci: use uv-managed Python so tkinter is available
- ci: key uv cache on pyproject.toml (uv.lock is gitignored)
- ci: bind publish-pypi to the pypi environment so the token resolves
- ci: publish to PyPI after all packages build

### `dir:docs` — 3 commits, churn 348
*2026-07-03 → 2026-07-06* · hashes: `f49d139`…`8e0064a`
- test: resiliencia end-to-end del pipeline y verificación --simulate (Fase 7)
- docs: profundiza el contrato D-Bus del ADR-010 (Opción 3, solo diseño)
- fix: use HTTPS for the GEOFON fdsnws-event endpoint

### `dir:packaging` — 1 commits, churn 499
*2026-07-03 → 2026-07-03* · hashes: `b6413e3`…`b6413e3`
- feat: empaquetado multiplataforma y CI de release (Fase 8)

## Hotspots (archivos más tocados)

| Archivo | Toques |
|---|---|
| `CHANGELOG.md` | 22 |
| `pyproject.toml` | 17 |
| `docs/IMPLEMENTATION-PLAN.md` | 14 |
| `src/vigia_eew/app.py` | 11 |
| `src/vigia_eew/config.py` | 10 |
| `docs/TECHNICAL-DESIGN.md` | 10 |
| `src/vigia_eew/cli.py` | 9 |
| `tests/test_app.py` | 9 |
| `tests/test_config.py` | 9 |
| `README.md` | 9 |
| `docs/PRD.md` | 9 |
| `tests/test_cli.py` | 7 |
| `docs/API-SPEC.md` | 7 |
| `src/vigia_eew/notify/alert_window.py` | 6 |
| `docs/DATA-MODEL.md` | 6 |

## Archivos con fixes recurrentes (candidatos a criterios de aceptación y a rediseño en v2)

| Archivo | Nº de commits fix |
|---|---|
| `CHANGELOG.md` | 5 |
| `packaging/build_linux.sh` | 2 |
| `pyproject.toml` | 2 |
| `src/vigia_eew/tray.py` | 2 |
| `tests/test_tray.py` | 2 |
| `src/vigia_eew/notify/alert_window.py` | 2 |
| `tests/test_alert_window.py` | 2 |

## Autores

- Ernesto Crespo: 46 commits
- Claude: 1 commits
