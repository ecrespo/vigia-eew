# 02 — Stack tecnológico

> Generado por ingeniería inversa el 2026-08-16. Commit de referencia: `6e0f133`.
> Versiones "declaradas" salen de `pyproject.toml`; las "resueltas" son las que se
> instalaron realmente al verificar el repo (2026-08-16). **No hay lockfile versionado**
> — ver RR-1 en riesgos.

## 1. Lenguajes y tamaño

| Lenguaje | LOC | Uso |
|---|---|---|
| Python | 9.197 | Todo el agente y los tests |
| YAML | 455 | GitHub Actions, pre-commit |
| Shell / PowerShell | 122 | Scripts de empaquetado nativo |

**Python `>=3.11`** `[VERIFY: pyproject.toml:14]` — el piso lo fija `tomllib`, que entró a
la stdlib en 3.11 y evita una dependencia de parseo TOML. Clasificadores declaran soporte
hasta 3.13 `[VERIFY: pyproject.toml:26]`.

## 2. Dependencias de runtime

| Paquete | Declarado | Resuelto | Para qué | Evidencia |
|---|---|---|---|---|
| `websockets` | `>=12.0` | 17.0.1 | Canal push EMSC, keepalive nativo | `[VERIFY: pyproject.toml:32]` |
| `httpx` | `>=0.27` | 0.28.1 | REST async (USGS, GEOFON, FUNVISIS, geoloc) | `[VERIFY: pyproject.toml:33]` |
| `pydantic` | `>=2.6` | 2.13.4 | Validación de modelos y config | `[VERIFY: pyproject.toml:34]` |
| `desktop-notifier` | `>=5.0` | 6.2.0 | Toast nativo multiplataforma | `[VERIFY: pyproject.toml:35]` |
| `platformdirs` | `>=4.0` | 4.11.3 | Rutas de config/estado por SO | `[VERIFY: pyproject.toml:36]` |
| `tzdata` | `>=2024.1` | 2026.3 | Zona `America/Caracas` en Win/macOS | `[VERIFY: pyproject.toml:37]` |
| `pystray` | `>=0.19` | 0.19.5 | Ícono de bandeja | `[VERIFY: pyproject.toml:38]` |
| `Pillow` | `>=10.0` | 12.3.0 | Imagen del ícono (requisito de pystray) | `[VERIFY: pyproject.toml:39]` |
| `textual` | `>=0.60` | 8.2.8 | Dashboard TUI headless | `[VERIFY: pyproject.toml:40]` |

**Tkinter no aparece aquí**: viene con CPython, y esa es exactamente la razón por la que
se eligió sobre PyQt/PySide (ADR-003). El costo es una UI más sobria; el beneficio, cero
peso de instalación para la garantía central del producto.

Tres dependencias son **excepciones documentadas** a la regla de "cero dependencias extra"
del proyecto, y las tres son de frontends opcionales: `pystray`+`Pillow` (bandeja) y
`textual` (TUI). Ninguna hace red ni telemetría.

## 3. Dependencias de desarrollo y build

| Grupo | Paquetes | Evidencia |
|---|---|---|
| `dev` | pytest ≥8 (9.1.1), pytest-asyncio (1.4.0), pytest-cov (7.1.0), ruff ≥0.5 (0.16.3), mypy ≥1.10 (2.3.1), pre-commit ≥3.7 | `[VERIFY: pyproject.toml:53]` |
| `packaging` | pyinstaller ≥6.0 | `[VERIFY: pyproject.toml:63]` |
| `security` | bandit ≥1.8, pip-audit ≥2.7 | `[VERIFY: pyproject.toml:68]` |

- **Gestor**: `uv`; **backend de build**: `hatchling` `[VERIFY: pyproject.toml:6]`.
- **Layout `src/`** `[VERIFY: pyproject.toml:76]` — evita importar el paquete desde el
  directorio de trabajo y que los tests pasen por accidente.
- **Entry point de consola**: `vigia-eew = "vigia_eew.cli:main"`
  `[VERIFY: pyproject.toml:50]`.

## 4. Configuración de calidad

| Herramienta | Configuración | Evidencia |
|---|---|---|
| ruff | line-length 100, reglas `E,F,I,UP,B`, target py311 | `[VERIFY: pyproject.toml:86]` |
| mypy | **`strict = true`** + `warn_unused_ignores` | `[VERIFY: pyproject.toml:94]` |
| pytest | `asyncio_mode = "auto"`, testpaths `tests` | `[VERIFY: pyproject.toml:82]` |
| coverage | `branch = true` | `[VERIFY: pyproject.toml:106]` |
| bandit | excluye `tests/` (asserts y subprocess son ruido ahí) | `[VERIFY: pyproject.toml:104]` |

Un solo `ignore_missing_imports`, para `pystray`, que no publica stubs
`[VERIFY: pyproject.toml:98]`. Que mypy strict pase sobre 40 módulos con una única
excepción es una señal fuerte de la salud del tipado.

## 5. Infraestructura y CI/CD

Tres workflows de GitHub Actions, con una acción compuesta común que instala `uv` y
sincroniza el proyecto `[VERIFY: .github/actions/setup-python-env/action.yml:1]`.

| Workflow | Dispara en | Contenido | Evidencia |
|---|---|---|---|
| `ci.yml` | push/PR a `develop` | ruff, mypy, pytest+cobertura en jobs paralelos | `[VERIFY: .github/workflows/ci.yml:27]` |
| `security.yml` | PR a `main` | bandit y semgrep (SAST), pip-audit y trivy (SCA), gitleaks (secretos); cada uno sube su reporte | `[VERIFY: .github/workflows/security.yml:23]` |
| `build.yml` | tag `vX.Y.Z` | wheel+sdist, `.exe` Windows, `.dmg` macOS, AppImage+`.deb`/`.rpm` Linux, publicación a PyPI | `[VERIFY: .github/workflows/build.yml:21]` |

El build es genuinamente multiplataforma: usa `windows-latest`, `macos-latest` y
`ubuntu-latest` `[VERIFY: .github/workflows/build.yml:34]`, más `fpm` y
`linuxdeploy`/`appimagetool` instalados en el runner
`[VERIFY: .github/workflows/build.yml:71]`.

`.pre-commit-config.yaml` replica el gate localmente: las verificaciones rápidas por
commit y las pesadas (pytest, pip-audit, semgrep, trivy) en pre-push.

## 6. Persistencia e integraciones

- **Sin base de datos.** El estado es un único JSON escrito atómicamente
  `[VERIFY: src/vigia_eew/state.py:33]` en el directorio de datos del usuario resuelto por
  `platformdirs` `[VERIFY: src/vigia_eew/state.py:28]`.
- **Sin servidor, sin API propia, sin autenticación.** Cuatro integraciones salientes de
  solo lectura sobre HTTP/WS público, más `ipapi.co` una única vez.
- **Assets embebidos** en el paquete: WAVs por severidad, `tray_icon.png` y
  `countries.geojson` (Natural Earth 1:110m, ~186 KiB, dominio público) —
  `[VERIFY: src/vigia_eew/geocode.py:32]`. Elegir un asset embebido en vez de una
  dependencia geoespacial mantiene el binario liviano y elimina la red por evento.

## 7. Riesgos para la reconstrucción

| # | Riesgo | Evidencia | Acción propuesta para v2 |
|---|---|---|---|
| RR-1 | **`uv.lock` está gitignoreado** → builds no reproducibles; el CI cachea sobre `pyproject.toml` como workaround | `[VERIFY: .gitignore:29]`, `27e4b45` | Versionar el lockfile. Es el riesgo más accionable de esta tabla |
| RR-2 | Rangos abiertos (`>=`) en todas las dependencias; lo resuelto ya divergió mucho de lo declarado (websockets 12→17, textual 0.60→8.2, mypy 1.10→2.3) | `[VERIFY: pyproject.toml:31]` | Fijar techos mayores (`>=x,<y+1`) al menos en `textual` y `websockets`, que cambiaron de major varias veces |
| RR-3 | **Tkinter bajo Wayland** no puede forzar topmost/focus de forma confiable; ADR-010 lo reconoce y su solución (D-Bus + extensión GNOME) nunca se implementó | Sin módulo D-Bus en `src/` | Decisión explícita en el diseño de v2 antes de comprometerse con Tkinter — es la garantía central del producto |
| RR-4 | `pystray` requiere `run()` en el hilo principal en macOS (requisito de Cocoa), lo que choca con Tkinter; nunca se validó en hardware macOS | ADR-012; `[VERIFY: src/vigia_eew/tray.py:110]` | Validar en macOS real o declarar la bandeja como no soportada ahí |
| RR-5 | FUNVISIS se consume por **HTTP plano** (no ofrece HTTPS válido) | ADR-015 | Aceptable (dato público, solo lectura), pero re-verificar si FUNVISIS habilitó TLS |
| RR-6 | Dos tests del suite por defecto exigen display real | `[VERIFY: tests/test_tray.py:81]` | Marcarlos con el mismo guard `VIGIA_GUI_TESTS=1` que los smokes de Tkinter, o correr CI bajo `xvfb` |
| RR-7 | Endpoints externos sin contrato estable: FUNVISIS es un JSON de su mapa web, GEOFON entrega texto pipe-delimitado | `[VERIFY: src/vigia_eew/ingest/rest_geofon.py:83]` | Tests de contrato contra respuestas reales grabadas, para detectar cambios de formato antes que el usuario |
