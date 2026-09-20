# 00 — Inventario del repositorio

> Ingeniería inversa ejecutada el 2026-09-06. Commit de referencia: `c3a2c29` (HEAD).
> Fuentes brutas: `analysis/inventory.{json,md}` y `analysis/history.{json,md}`.

## 1. Alcance de lo analizado

| Dimensión | Analizado | No analizado |
|---|---|---|
| Commits | **58 en el historial de `HEAD`**, 47 sin merges (los 11 merges son PRs `develop → main`). `git rev-list --all` da 59 al incluir las ramas `develop` y `documentation` — es la cifra que usa `docs/code-audit/` | ninguno |
| Rango temporal | 2026-06-28 → 2026-07-17 | — |
| Código | `src/` (4.387 LOC, 40 archivos), `tests/` (4.714 LOC, 37 archivos `.py`, de los cuales 35 son `test_*.py`), `packaging/` (85 LOC) | — |
| Documentación | `docs/`, `ARCHITECTURE.md`, `CLAUDE.md`, `README.md`, `CHANGELOG.md` | — |
| Assets binarios | 3 `.wav`, `tray_icon.png`, `countries.geojson` (inventariados, no decodificados) | contenido binario |

No hubo truncamiento: el repositorio entra completo dentro de los límites del análisis.

## 2. Corrección de dos artefactos ruidosos del script

El script de inventario recorre el árbol de trabajo completo, y en este repo eso incluye
directorios que **no forman parte del sistema**. Las cifras crudas deben leerse corregidas:

| Dato crudo del script | Realidad | Causa |
|---|---|---|
| Python: **251.255 LOC** | **9.186 LOC** (`src` + `tests` + `packaging`) | `.venv_sandbox/` y `.venv/` están en el árbol de trabajo pero no versionados (`.gitignore`) |
| Manifiesto `…/my-test-package-source/setup.py` | **No es un manifiesto del proyecto** | Es data de test de `pkg_resources`, dentro de `.venv_sandbox/` |
| Directorio de tests `…/pkg_resources/tests` | **No es del proyecto** | Ídem |

El único manifiesto real es `pyproject.toml`; el único directorio de tests real es `tests/`.

## 3. Origen del proyecto — verificado, no inferido

Este repositorio es **greenfield**, no un fork ni un pivote de otro producto. Evidencia directa:

- El commit inicial `406cde0` contiene exactamente **dos archivos**: `LICENSE` y un `README.md`
  de 2 líneas. No hay código heredado. `[COMMITS: 406cde0]`
- El segundo commit `737d7fa` crea los artefactos SDD desde cero (PRD, API-Spec, Technical
  Design, Data Model, Implementation Plan) antes de escribir una sola línea de producción.
  `[COMMITS: 737d7fa]`
- Un único autor en los 58 commits: Ernesto Crespo.

**Coincidencias superficiales que NO deben leerse como origen externo** (se dejan explícitas
porque son la trampa natural de este repo):

- `src/vigia_eew/assets/countries.geojson` es un derivado reducido de Natural Earth 1:110m,
  generado por un script del propio repo `[VERIFY: packaging/build_countries_geojson.py:1]`.
  No implica dependencia ni ascendencia de ningún proyecto GIS.
- `maravilla.json` es el nombre del endpoint público de FUNVISIS que el sistema consume
  `[VERIFY: src/vigia_eew/ingest/rest_funvisis.py:40]`, no un componente interno ni un nombre
  clave del proyecto.
- `.venv_sandbox/` es un entorno virtual local, no un módulo del sistema.
- `vigia-eew-presentacion.pptx` en la raíz es material de divulgación, no un artefacto de build.

## 4. Clusters de features — CURADOS

El script agrupó por directorio dominante y produjo 5 clusters (`dir:(raiz)`,
`dir:src/vigia_eew`, `dir:.github`, `dir:docs`, `dir:packaging`). Esa agrupación es inútil aquí:
el repositorio sigue una disciplina SDD de **un commit por fase**, y casi todo el trabajo de
producto cae en `src/vigia_eew`. Los clusters se recurraron por **capacidad entregada**, usando
los mensajes de commit (97,9 % conventional commits) y las fases/RF que citan.

| # | Cluster curado | Commits | Hashes | → HU |
|---|---|---|---|---|
| C-01 | Andamiaje y artefactos SDD | 4 | `406cde0`, `737d7fa`, `8e7b223`, `230b0b8` | — (ruido de producto; va a evolución) |
| C-02 | Dominio: modelos, config, estado, logging | 1 | `b5c5371` | HU-001 |
| C-03 | Ingesta EMSC/USGS + supervisor | 1 | `fc0ca99` | HU-002 |
| C-04 | Pipeline normalize/filter/dedup | 1 | `b40c20b` | HU-003 |
| C-05 | Capa de notificación + fixes de layout | 3 | `fb50326`, `f90c796`, `f0960ac` | HU-004 |
| C-06 | CLI, ensamblaje y `--simulate` | 1 | `4fb49d0` | HU-005 |
| C-07 | Autoarranque multiplataforma | 1 | `5b79ff1` | HU-006 |
| C-08 | Pruebas de resiliencia e2e | 1 | `f49d139` | — (alimenta 04-MATRIZ-PRUEBAS) |
| C-09 | Empaquetado, binarios y CI de release | 5 | `b6413e3`, `7b1c71c`, `c38d9f6`, `bdc2a9d`, `a02607f` | HU-007 |
| C-10 | Geolocalización automática por IP | 1 | `c20a59b` | HU-008 |
| C-11 | Ícono de bandeja | 1 | `fb3fe14` | HU-009 |
| C-12 | Traducción a inglés + i18n | 2 | `7f9132e`, `e49404d` | HU-010 |
| C-13 | Dashboard TUI headless | 2 | `7f98980`, `651c024` | HU-011 |
| C-14 | Filtro de país offline | 1 | `a3a4a1a` | HU-012 |
| C-15 | Semilla de `config.toml` | 1 | `a06f7a1` | HU-013 |
| C-16 | Fuente FUNVISIS | 1 | `10bb72d` | HU-014 |
| C-17 | Fuente GEOFON | 2 | `ade1199`, `8e0064a` | HU-015 |
| C-18 | Frescura, backlog acotado y poda | 1 | `b0f832c` | HU-016 |
| C-19 | CI, seguridad y pre-commit | 6 | `97b2a8e`, `5ee3b1d`, `f51da9c`, `27e4b45`, `0e707a1`, `559f077` | HU-017 |
| C-20 | Releases (`chore: release vX.Y.Z`) | 9 | `92c65e5` … `bd4a555` | — (ruido; marca eras) |

Cobertura: **17 HUs cubren los 18 clusters de producto**; C-01, C-08 y C-20 quedan fuera de las
HUs por diseño y están representados en `03-EVOLUCION.md` y `04-MATRIZ-PRUEBAS.md`.

## 5. Hotspots y fixes recurrentes

Archivos más tocados (excluyendo documentación de proceso):

| Archivo | Toques | Lectura |
|---|---|---|
| `CHANGELOG.md` | 22 | disciplina de release, no deuda |
| `pyproject.toml` | 17 | crecimiento de dependencias por fase |
| `src/vigia_eew/app.py` | 10 | **composición central** — cada feature nueva lo toca |
| `src/vigia_eew/config.py` | 10 | ídem: cada feature añade su sección de config |
| `src/vigia_eew/cli.py` | 9 | cada feature añade su flag |

Archivos con ≥2 commits de tipo `fix` — cada uno es fuente de un criterio de aceptación P1:

| Archivo | Fixes | Naturaleza |
|---|---|---|
| `packaging/build_linux.sh` | 2 | ícono placeholder inválido rompía AppImage `[COMMITS: 7b1c71c, c38d9f6]` |
| `src/vigia_eew/notify/alert_window.py` | 2 | contenido recortado en la ventana de alerta `[COMMITS: f90c796, f0960ac]` |
| `src/vigia_eew/tray.py` | 2 | rutas de config al abrir el editor `[COMMITS: fb3fe14, a06f7a1]` |
| `pyproject.toml` | 2 | recursos faltantes en el binario congelado `[COMMITS: bdc2a9d]` |

## 6. Estado de la cobertura de evidencia

- **344 pruebas** en 35 archivos `test_*.py` — base primaria de los criterios de aceptación.
- Los artefactos SDD originales (`docs/PRD.md`, `docs/TECHNICAL-DESIGN.md` con 18 ADRs) existen
  y son de alta calidad; esta reconstrucción los **contrasta** con el código, no los copia.
- Densidad de evidencia del kit, medida tras la pasada de validación: **699 citas `[VERIFY:]`**
  (327 únicas, **todas verificadas** contra archivo y número de línea), **98 citas `[COMMITS:]`**
  (39 hashes distintos, **todos existentes** en el repositorio) y solo **2 marcas `[INFERIDO]`**.
  Ambas están en las personas/roles de HU-001 y HU-008, que los commits no nombran explícitamente.
  Ningún área del repositorio resultó demasiado opaca para documentarse con evidencia.
