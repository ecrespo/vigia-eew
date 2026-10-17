# 02 — Stack tecnológico

> Commit de referencia: `c3a2c29` · Fecha: 2026-09-06
> Versiones exactas tomadas de `uv.lock`; los rangos vienen de `pyproject.toml`.

## 1. Resumen ejecutivo

| Categoría | Tecnología |
|---|---|
| Lenguaje | Python ≥ 3.11 (usa `tomllib` de stdlib) `[VERIFY: pyproject.toml:14]` |
| Concurrencia | asyncio (un proceso, tareas supervisadas) |
| UI escritorio | Tkinter (stdlib) + `pystray` bandeja |
| UI terminal | Textual (`--tui`) |
| Validación / config | pydantic 2 sobre `tomllib` |
| Cliente HTTP | `httpx` (async) |
| Cliente WebSocket | `websockets` |
| Persistencia | **JSON atómico en disco** vía `platformdirs` — sin base de datos |
| Empaquetado | hatchling (wheel/PyPI) + PyInstaller (binarios) |
| Gestor de proyecto | `uv` |
| CI/CD | GitHub Actions (`ci.yml`, `security.yml`, `build.yml`) |
| Contenedores / IaC | **ninguno** — es un agente de escritorio, no un servicio |

## 2. Lenguajes

| Lenguaje | LOC | Rol | Versión | Evidencia |
|---|---|---|---|---|
| Python | 9.186 (`src` 4.387 · `tests` 4.714 · `packaging` 85) | todo el sistema | ≥ 3.11, `target-version = "py311"` | `[VERIFY: pyproject.toml:87]` |
| YAML | 455 | workflows de CI y acción compuesta | — | `[VERIFY: .github/workflows/ci.yml:7]` |
| Shell / PowerShell | 122 | scripts de build por plataforma | — | `[VERIFY: packaging/build_linux.sh:1]` |

> La cifra de 251.255 LOC del script crudo incluye `.venv_sandbox/`; ver `00-INVENTARIO.md` §2.

## 3. Dependencias de runtime

| Dependencia | Rango declarado | Versión en lockfile | Rol | Evidencia de uso |
|---|---|---|---|---|
| `websockets` | ≥ 12.0 | **16.0** | canal push EMSC, keepalive nativo | `[VERIFY: src/vigia_eew/ingest/ws_emsc.py:37]` |
| `httpx` | ≥ 0.27 | **0.28.1** | REST async a USGS/GEOFON/FUNVISIS/geo-IP | `[VERIFY: src/vigia_eew/ingest/rest_usgs.py:42]` |
| `pydantic` | ≥ 2.6 | **2.13.4** | contrato interno y validación de config | `[VERIFY: src/vigia_eew/models.py:51]` |
| `desktop-notifier` | ≥ 5.0 | **6.2.0** | toast nativo multiplataforma | `[VERIFY: src/vigia_eew/notify/toast.py:40]` |
| `platformdirs` | ≥ 4.0 | **4.10.0** | rutas de estado/config por SO | `[VERIFY: src/vigia_eew/state.py:28]` |
| `tzdata` | ≥ 2024.1 | **2026.2** | zona `America/Caracas` en Win/macOS | `[VERIFY: src/vigia_eew/timeutil.py:23]` |
| `pystray` | ≥ 0.19 | **0.19.5** | ícono de bandeja | `[VERIFY: src/vigia_eew/tray.py:110]` |
| `Pillow` | ≥ 10.0 | **12.3.0** | imagen del ícono (requisito de pystray) | `[VERIFY: src/vigia_eew/tray.py:72]` |
| `textual` | ≥ 0.60 | **8.2.8** | dashboard TUI headless | `[VERIFY: src/vigia_eew/tui.py:101]` |

**Sin dependencias geoespaciales.** El punto-en-polígono es Python puro sobre un GeoJSON reducido
que se genera en el repo `[VERIFY: src/vigia_eew/geocode.py:89]`, `[VERIFY: packaging/build_countries_geojson.py:1]`.

Módulos de stdlib que hacen trabajo estructural: `tomllib` (config), `zoneinfo` (día local),
`tkinter` (ventana de alerta), `asyncio`, `threading` (bandeja y puente).

## 4. Persistencia

No hay motor de base de datos. El estado vive en un único `state.json` escrito de forma **atómica**
`[VERIFY: src/vigia_eew/state.py:61]`, en la ruta por SO de `platformdirs`
`[VERIFY: src/vigia_eew/state.py:28]`. Contiene: ids alertados, firmas recientes, cursores
USGS/GEOFON y la ubicación geo-IP cacheada `[VERIFY: src/vigia_eew/models.py:133]`.
Poda a 24 h en `prune()` `[VERIFY: src/vigia_eew/state.py:129]`.

La configuración es `config.toml`, **solo lectura** (`tomllib`), sembrada desde una plantilla
empaquetada en el primer arranque `[VERIFY: src/vigia_eew/config.py:176]`.

## 5. Infraestructura y despliegue

- **Contenedores/IaC**: ninguno, por diseño (un proceso por máquina de usuario).
- **Distribución**: wheel a PyPI (hatchling) + binarios congelados con PyInstaller
  `[VERIFY: packaging/vigia-eew.spec:1]`, construidos por plataforma
  `[VERIFY: packaging/build_linux.sh:1]`, `[VERIFY: packaging/build_macos.sh:1]`,
  `[VERIFY: packaging/build_windows.ps1:1]`.
- **Arranque automático**: unidad systemd `--user`, LaunchAgent o tarea programada, generados como
  **strings puros** y aplicados por subprocess `[VERIFY: src/vigia_eew/autostart/linux_systemd.py:26]`.
- **CI**: `ci.yml` (ruff → mypy → pytest+cobertura) en PRs a `develop`
  `[VERIFY: .github/workflows/ci.yml:27]`; `security.yml` (bandit, pip-audit, gitleaks, semgrep,
  trivy) en PRs a `main`; `build.yml` publica en tags `vX.Y.Z`.

## 6. Testing y calidad

| Herramienta | Versión (lock) | Configuración |
|---|---|---|
| pytest | 9.1.1 | `asyncio_mode = "auto"` |
| pytest-asyncio | 1.4.0 | — |
| pytest-cov | 7.1.0 | `branch = true` |
| ruff | 0.15.20 | `line-length = 100`, reglas `E,F,I,UP,B` `[VERIFY: pyproject.toml:87]` |
| mypy | 2.1.0 | `strict = true`, `python_version = 3.11` `[VERIFY: pyproject.toml:93]` |
| pre-commit | 4.6.0 | rápidas por commit, pesadas en pre-push `[VERIFY: .pre-commit-config.yaml:1]` |

**344 pruebas** en 35 archivos `test_*.py`. Las pruebas de GUI real están tras `VIGIA_GUI_TESTS=1`;
la suite por defecto corre headless.

## 7. Riesgos para la reconstrucción

| Riesgo | Severidad | Detalle | Acción para la v2 |
|---|---|---|---|
| **Deriva mayor entre rango y lockfile** | Alta | `websockets` 12→**16**, `textual` 0.60→**8.2**, `mypy` 1.10→**2.1**, `Pillow` 10→**12**. Los rangos `>=` no protegen de cambios rompientes | Fijar límites superiores (`>=16,<17`) o commitear el lock |
| **Tkinter bajo Wayland** | Alta | El compositor puede negar *topmost* y foco; la garantía central del producto queda sin cumplir | Implementar ADR-010 (D-Bus + extensión GNOME) o adoptar un frontend nativo |
| **`pystray` en macOS** | Media | Cocoa exige `run()` en el hilo principal, en conflicto con Tk; nunca se validó en hardware macOS | Validar en macOS real o declarar la bandeja no soportada allí |
| **`uv.lock` ignorado en git** | Media | La CI cachea por `pyproject.toml` porque el lock no está versionado `[COMMITS: 27e4b45]` | Versionar el lock: builds reproducibles |
| **Endpoint FUNVISIS sin HTTPS** | Baja | Aceptado por ser público y de solo lectura | Revisar si FUNVISIS publica TLS |
| **Duplicación FDSN USGS/GEOFON** | Baja | Dos parsers para la misma familia de servicio | Unificar solo si entra una 5ª fuente |
| **Sin base de datos** | Baja (informativa) | `state.json` completo en memoria; adecuado a la escala actual | Mantener; revisar si el histórico crece |

Nada del stack está EOL. Python 3.11 sigue soportado; el mínimo podría subirse a 3.12 en la v2 sin
coste, ya que la única razón del piso 3.11 es `tomllib`.
