# Señales arquitectónicas desde git

**Repo:** `/home/user/vigia-eew` · 49 commits (2026-06-28 → 2026-08-16)

## 🔴 Acoplamiento temporal entre módulos — evidencia P1

Pares de archivos en módulos distintos que cambian juntos: la frontera entre esos módulos es ficticia o tiene fugas.

| Archivo A | Archivo B | Co-cambios | Confianza |
|---|---|---|---|
| `README.md` | `docs/IMPLEMENTATION-PLAN.md` | 6 | 0.67 |
| `docs/IMPLEMENTATION-PLAN.md` | `tests/test_cli.py` | 5 | 0.71 |
| `src/vigia_eew/cli.py` | `tests/test_cli.py` | 5 | 0.71 |
| `docs/IMPLEMENTATION-PLAN.md` | `tests/test_app.py` | 5 | 0.56 |
| `src/vigia_eew/app.py` | `tests/test_app.py` | 5 | 0.56 |
| `src/vigia_eew/config.py` | `tests/test_config.py` | 5 | 0.56 |
| `docs/IMPLEMENTATION-PLAN.md` | `src/vigia_eew/cli.py` | 5 | 0.56 |
| `CHANGELOG.md` | `packaging/build_linux.sh` | 3 | 1.0 |
| `packaging/build_linux.sh` | `pyproject.toml` | 3 | 1.0 |
| `src/vigia_eew/notify/alert_window.py` | `tests/test_alert_window.py` | 3 | 0.75 |
| `src/vigia_eew/models.py` | `tests/test_config.py` | 3 | 0.6 |
| `config.toml.example` | `docs/IMPLEMENTATION-PLAN.md` | 3 | 0.6 |
| `config.toml.example` | `docs/PRD.md` | 3 | 0.6 |
| `config.toml.example` | `docs/TECHNICAL-DESIGN.md` | 3 | 0.6 |

## Acoplamiento temporal intra-módulo (contexto)

| Archivo A | Archivo B | Co-cambios | Confianza |
|---|---|---|---|
| `CHANGELOG.md` | `pyproject.toml` | 12 | 0.71 |
| `docs/IMPLEMENTATION-PLAN.md` | `docs/PRD.md` | 5 | 0.56 |
| `docs/PRD.md` | `docs/TECHNICAL-DESIGN.md` | 5 | 0.56 |
| `docs/IMPLEMENTATION-PLAN.md` | `docs/TECHNICAL-DESIGN.md` | 5 | 0.5 |
| `src/vigia_eew/config.py` | `src/vigia_eew/models.py` | 3 | 0.6 |
| `README.md` | `config.toml.example` | 3 | 0.6 |
| `docs/API-SPEC.md` | `docs/DATA-MODEL.md` | 3 | 0.5 |

## Hotspots (toques × (1+fixes))

| Archivo | Toques | Fixes | Churn | Score |
|---|---|---|---|---|
| `CHANGELOG.md` | 22 | 5 | 295 | 132 |
| `pyproject.toml` | 17 | 2 | 164 | 51 |
| `src/vigia_eew/config.py` | 10 | 1 | 505 | 20 |
| `src/vigia_eew/notify/alert_window.py` | 6 | 2 | 399 | 18 |
| `src/vigia_eew/tray.py` | 6 | 2 | 307 | 18 |
| `docs/API-SPEC.md` | 7 | 1 | 809 | 14 |
| `docs/IMPLEMENTATION-PLAN.md` | 14 | 0 | 815 | 14 |
| `docs/DATA-MODEL.md` | 6 | 1 | 651 | 12 |
| `tests/test_tray.py` | 4 | 2 | 307 | 12 |
| `tests/test_alert_window.py` | 4 | 2 | 365 | 12 |
| `src/vigia_eew/app.py` | 11 | 0 | 879 | 11 |
| `docs/TECHNICAL-DESIGN.md` | 10 | 0 | 1378 | 10 |
| `docs/PRD.md` | 9 | 0 | 539 | 9 |
| `tests/test_app.py` | 9 | 0 | 623 | 9 |
| `tests/test_config.py` | 9 | 0 | 320 | 9 |

## Archivos con fixes recurrentes

| Archivo | Fixes |
|---|---|
| `CHANGELOG.md` | 5 |
| `src/vigia_eew/tray.py` | 2 |
| `tests/test_tray.py` | 2 |
| `src/vigia_eew/notify/alert_window.py` | 2 |
| `tests/test_alert_window.py` | 2 |
| `packaging/build_linux.sh` | 2 |
| `pyproject.toml` | 2 |

## Concentración de conocimiento por módulo (bus factor)

| Módulo | Commits | Autores | Autor dominante | % |
|---|---|---|---|---|
| `tests` | 22 | 1 | Ernesto Crespo | 100.0% ⚠️ |
| `docs` | 16 | 1 | Ernesto Crespo | 100.0% ⚠️ |
| `packaging` | 8 | 1 | Ernesto Crespo | 100.0% |
| `.github/workflows` | 8 | 1 | Ernesto Crespo | 100.0% |
| `src/vigia_eew/autostart` | 5 | 1 | Ernesto Crespo | 100.0% |
| `src/vigia_eew/assets` | 4 | 1 | Ernesto Crespo | 100.0% |
| `docs/plans` | 3 | 1 | Ernesto Crespo | 100.0% |
| `.github/actions` | 2 | 1 | Ernesto Crespo | 100.0% |
| `docs/code-audit` | 1 | 1 | Claude | 100.0% |
| `docs/reverse-sdd` | 1 | 1 | Claude | 100.0% |
| `lat.md` | 1 | 1 | Claude | 100.0% |
| `.codegraph` | 1 | 1 | Claude | 100.0% |
