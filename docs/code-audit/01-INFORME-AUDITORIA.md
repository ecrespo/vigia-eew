# Auditoría de código y seguridad — vigia-eew

**Fecha:** 2026-09-06 · **Stack:** Python 3.11+ (agente de escritorio asyncio; **no** FastAPI ni Django)
**Commit auditado:** `c3a2c29` · **Ejecución:** copia aislada del repo en disco nativo, modo solo lectura

**Herramientas ejecutadas:** ruff 0.15.20 (versión del lockfile) y 0.16.6 · bandit 1.9.4 ·
mypy 2.1.0 · lizard 1.24.0 · flake8 7.3.0 + flake8-cognitive-complexity 0.1.0 · pylint 4.0.8
(`duplicate-code`) · jscpd 4 · detect-secrets 1.5.0 (árbol + 59 commits: todo `git rev-list --all`, las tres ramas) ·
PyPI Advisory Database (90 paquetes del lockfile)

**No ejecutadas y por qué** — ver §Gaps de tooling al final; **ninguna se sustituyó por una
estimación**:

| Herramienta | Motivo | Sustituto aplicado |
|---|---|---|
| Gitleaks | binario desde GitHub Releases; `github.com` no resuelve en el entorno | **detect-secrets** sobre árbol de trabajo **y sobre los 59 commits de todas las ramas** (`git rev-list --all`; el historial de `HEAD` son 58) |
| pip-audit (OSV) | `api.osv.dev` responde 403; además `pip-audit -r` no resuelve el lock (Python 3.10 vs `requires-python >=3.11`) | Consulta directa a la **PyPI Advisory Database**, la misma fuente de `pip-audit -s pypi` |
| pytest + cobertura | el proyecto exige Python ≥3.11 (`tomllib`, `datetime.UTC`); el entorno solo tiene 3.10 y no puede descargar otro (GitHub bloqueado) | Ninguno posible → **dimensión 3 sin veredicto de cobertura**; se aporta inventario estático y análisis de smells |
| Semgrep | descarga rulesets de `semgrep.dev` | Bandit + revisión dirigida con `[VERIFY:]` |
| Trivy / Hadolint / Dockle | binarios desde GitHub; además **el repo no tiene Dockerfiles** | Dimensión 8 fuera de alcance por diseño del producto |

## Resumen ejecutivo

La postura de seguridad y calidad de este repositorio es **notablemente buena para su tamaño**:
cero secretos en el árbol y en toda la historia de git, cero hallazgos SAST de severidad alta,
`mypy --strict` limpio sobre 40 archivos, duplicación del 0,95 % y complejidad ciclomática media
de 2,5. No se encontró **ningún hallazgo P1**.

El hallazgo más relevante es de proceso, no de código: **la cobertura de pruebas nunca se mide
contra un umbral**. Hay 344 pruebas y una razón test/código de 1,07:1, pero `pytest-cov` está
instalado y ningún gate exige un mínimo, así que un módulo puede quedar en 0 % sin que nada avise.
El segundo es que `ruff format` no está en ningún gate y **19 archivos están sin formatear**
según la propia versión que el proyecto fija.

La fortaleza principal es el gate existente: pre-commit en dos etapas que replica la CI, con
binarios de herramientas **verificados por checksum** y pinneados tras un incidente de supply
chain documentado en el propio workflow.

**Primer paso del plan**: añadir `ruff-format`, un umbral de cobertura y tres hooks de calidad al
`.pre-commit-config.yaml` existente (Fase 0 del plan de remediación) — todo lo demás es
mantenimiento.

## Scorecard

| # | Dimensión | Veredicto | Evidencia |
|---|---|---|---|
| 1 | DRY | 🟢 | `[TOOL: jscpd → 0,95 % de líneas duplicadas en Python, 5 clones]`. Los 2 clones de producción están concentrados en el par `rest_usgs.py`/`rest_geofon.py`, corroborados por `[TOOL: pylint R0801 → 3 bloques]` |
| 2 | SOLID | 🟡 | S🟡 O🟡 L🟢 I🟢 D🟢. `Application` con 22 métodos y 450 líneas `[VERIFY: src/vigia_eew/app.py:54]`; escalera de despacho por fuente `[VERIFY: src/vigia_eew/pipeline/normalize.py:55]`. Protocolos de 1 y 3 métodos; el dominio no importa infraestructura |
| 3 | Pruebas unitarias | ⚪ **no evaluado (cobertura)** | 344 pruebas en 35 archivos `test_*.py`, 4.714 líneas de test vs 4.387 de código. **La cobertura no pudo medirse**: `[TOOL: pytest → ImportError: cannot import name 'UTC'; No module named 'tomllib']` (entorno Python 3.10, proyecto ≥3.11). Además, ningún gate exige umbral `[GAP: sin --cov-fail-under en ci.yml ni en pre-commit]` |
| 4 | Pruebas integración | 🟡 | Existen 5 pruebas e2e reales del pipeline completo `[VERIFY: tests/test_resilience.py:94]`, pero **no hay separación formal**: `[GAP: pyproject.toml sin markers; testpaths = ["tests"] plano]`. Todo corre en el mismo lote |
| 5 | SAST | 🟢 | `[TOOL: bandit → 0 HIGH, 1 MEDIUM, 15 LOW sobre 3.565 LOC]`. El único MEDIUM está en un script de build, no en el producto `[VERIFY: packaging/build_countries_geojson.py:47]` |
| 6 | SCA | 🟢 | `[TOOL: PyPI Advisory DB → 90/90 paquetes del lockfile auditados, 1 con vulnerabilidad]`: `pip==26.1.2` (CVE-2026-13346), transitiva de `pip-api` ← `pip-audit`, **solo en el extra `security`** |
| 7 | Secretos | 🟢 | `[TOOL: detect-secrets → 0 hallazgos reales en el árbol; 0 en los 59 commits de todas las ramas]`. Los 3 positivos del árbol son checksums SHA-256 de binarios pinneados y un id de ejemplo en documentación |
| 8 | Contenedores | ⚫ **fuera de alcance** | `[TOOL: detect_stack.py → 0 Dockerfiles]`. El producto es un agente de escritorio que se distribuye como wheel y binarios PyInstaller; no hay superficie de contenedor. La CI ya corre `trivy fs` sobre el árbol |

## Fortalezas

1. **Historia de git limpia de secretos.** `[TOOL: detect-secrets sobre los 59 commits de todas las ramas → 0
   hallazgos]`. No es lo habitual: la mayoría de repos tiene al menos un `.env` o una clave de
   prueba en algún commit antiguo.
2. **Tipado estricto real, no decorativo.** `[TOOL: mypy 2.1.0 --strict → Success: no issues found
   in 40 source files]` con `strict = true` `[VERIFY: pyproject.toml:93]`. El gate lo ejecuta en
   cada commit `[VERIFY: .pre-commit-config.yaml:44]`.
3. **Complejidad bajo control.** `[TOOL: lizard → CCN media 2,5 sobre 253 funciones; ninguna
   supera el umbral de 15]`. Solo dos funciones exceden complejidad cognitiva 12
   `[TOOL: flake8 CCR001 → cli.py:56 (13), rest_geofon.py:133 (16)]`.
4. **Gate en dos etapas que replica la CI.** pre-commit rápido (gitleaks, ruff, mypy, bandit) y
   pre-push lento (pytest, pip-audit, semgrep, trivy) `[VERIFY: .pre-commit-config.yaml:1]`.
   Pocos repos personales mantienen paridad local/CI.
5. **Supply chain de herramientas verificado por checksum.** Los binarios de gitleaks y trivy se
   descargan pinneados y con SHA-256 comprobado `[VERIFY: .github/workflows/security.yml:90]`, y
   trivy está fijado en 0.70.0 **explícitamente por un incidente previo**
   `[VERIFY: .github/workflows/security.yml:118]`. Es madurez poco común.
6. **Inversión de dependencias sostenida.** El dominio (`models.py`, `pipeline/`, `geo.py`,
   `timeutil.py`) no importa ni HTTP, ni websockets, ni disco `[TOOL: solid-signals.txt § DIP]`.
   Relojes, `sleep`, clientes y los tres efectos de notificación son inyectados: por eso la suite
   corre headless y sin red.
7. **Razón test/código de 1,07:1.** 4.714 líneas de test para 4.387 de producción, con 77 tests
   asíncronos y control determinista del tiempo.

## Hallazgos

No hay hallazgos **P1**.

### P2-1 — La cobertura de pruebas no se mide contra ningún umbral

- **Dimensión:** 3 · **Evidencia:** la CI **sí mide** cobertura con branch coverage
  `[VERIFY: .github/workflows/ci.yml:53]` (`--cov=vigia_eew --cov-branch --cov-report=term-missing`)
  y sube `coverage.xml` como artefacto `[VERIFY: .github/workflows/ci.yml:62]`, pero
  `[GAP: no existe --cov-fail-under en .github/workflows/ci.yml ni en .pre-commit-config.yaml;
  pytest-cov está declarado en pyproject.toml:56]`. Se mide y se archiva; **no se exige**.
- **Impacto:** un módulo puede caer a 0 % de cobertura sin que ningún gate lo detecte. El propio
  historial del repositorio muestra el riesgo concreto: `StateStore.prune()` convivió 14 fases con
  un test en verde y **cero llamadas desde código de producción**, hasta que se cableó en
  `[COMMITS: b0f832c]`. La cobertura de líneas no habría detectado eso, pero un umbral por módulo
  sí habría hecho visible el desequilibrio.
- **Fix:** → PLAN-REMEDIACION R-01

### P2-2 — `ruff format` no está en ningún gate y 19 archivos están sin formatear

- **Dimensión:** 1 (calidad) · **Evidencia:** `[TOOL: ruff 0.15.20 format --check . → 19 files
  would be reformatted, 60 files already formatted]` — ejecutado con **la versión exacta que fija
  el lockfile**, así que no es deriva de versión. El pre-commit solo corre `ruff check`
  `[VERIFY: .pre-commit-config.yaml:37]`
- **Impacto:** ruido de diff en cada PR y decisiones de formato que se resuelven por revisión
  humana en lugar de por herramienta. Bajo riesgo, coste recurrente.
- **Fix:** → PLAN-REMEDIACION R-02

### P2-3 — Unitarias e integración no están separadas

- **Dimensión:** 4 · **Evidencia:** `[GAP: pyproject.toml:81 [tool.pytest.ini_options] solo declara
  testpaths y asyncio_mode; no hay markers]`. Las pruebas e2e reales
  `[VERIFY: tests/test_resilience.py:94]` corren en el mismo lote que las unitarias puras
  `[VERIFY: tests/test_geo.py:8]`
- **Impacto:** no se puede correr solo el lote rápido en pre-commit ni exigir cobertura distinta
  por tipo. Hoy el coste es bajo (la suite es rápida porque todo está inyectado), pero crece con
  cada prueba lenta que se añada.
- **Fix:** → PLAN-REMEDIACION R-03

### P2-4 — El gate no cubre tres de las ocho dimensiones

- **Dimensión:** 1, 2 · **Evidencia:** `[GAP: analysis/gaps.md → DRY ❌, SOLID ❌]`. No hay jscpd
  ni control de complejidad (lizard / CCR001) en pre-commit ni en CI
- **Impacto:** la duplicación y la complejidad solo se detectan si alguien las audita a mano —
  como en esta auditoría. Hoy ambas están en verde; nada impide que se degraden sin aviso.
- **Fix:** → PLAN-REMEDIACION R-04

### P2-5 — CVE en `pip`, alcanzable solo desde el extra `security`

- **Dimensión:** 6 · **Evidencia:** `[TOOL: PyPI Advisory DB → pip==26.1.2, PYSEC-2026-3721 /
  GHSA-qwm4-qh6w-59xr (CVE-2026-13346), fixed_in 26.2]`. Cadena:
  `pip` ← `pip-api` ← `pip-audit` `[VERIFY: uv.lock:921]`
- **Impacto:** **no llega al usuario final** — no es dependencia de runtime ni viaja en el wheel ni
  en los binarios PyInstaller. Afecta al entorno de desarrollo y a los runners de CI.
- **Fix:** → PLAN-REMEDIACION R-05

### P3 — Hallazgos de calidad (agrupados)

| # | Hallazgo | Dimensión | Evidencia |
|---|---|---|---|
| P3-1 | Duplicación estructural entre los dos pollers FDSN: constructor (22 líneas) y bucle de cursor (17 líneas) | 1 | `[TOOL: jscpd → src/vigia_eew/ingest/rest_geofon.py:57-78 ↔ rest_usgs.py:47-68 y :163-179 ↔ :142-157]`, `[TOOL: pylint R0801 ×3]` |
| P3-2 | `Application` concentra 22 métodos en 450 líneas — archivo más grande del repo y hotspot #4 del historial (10 toques) | 2 (SRP) | `[VERIFY: src/vigia_eew/app.py:54]`, `[TOOL: solid-signals.txt]` |
| P3-3 | Despacho por fuente con escalera `if/elif`: añadir una 5ª fuente obliga a tocar ≥5 archivos | 2 (OCP) | `[VERIFY: src/vigia_eew/pipeline/normalize.py:55]` + `models.py:20`, `config.py:150`, `app.py:117`, `ingest/__init__.py:22` |
| P3-4 | `StateStore` expone 12 métodos públicos sobre un único documento de estado | 2 (SRP/ISP) | `[VERIFY: src/vigia_eew/state.py:33]` |
| P3-5 | Dos funciones sobre complejidad cognitiva 12 | 2 | `[TOOL: flake8 CCR001 → src/vigia_eew/cli.py:56 (13), src/vigia_eew/ingest/rest_geofon.py:133 (16)]` |
| P3-6 | Un `asyncio.sleep(0.05)` real como sincronización en un test | 3 | `[VERIFY: tests/test_processor.py:106]` — el resto de la suite usa relojes inyectados |
| P3-7 | Tres tests sin `assert` ni `pytest.raises` (verifican "no lanza", pero pasarían aunque la función no hiciera nada) | 3 | `[VERIFY: tests/test_tui.py:153]`, `[VERIFY: tests/test_autostart_macos.py:69]`, `[VERIFY: tests/test_toast.py:62]` |
| P3-8 | Clon de fixture de 23 líneas entre dos archivos de test | 1 | `[TOOL: jscpd → tests/test_resilience.py:157-179 ↔ tests/test_ws_emsc.py:43-65]` |

## Hallazgos descartados

| Reporte de la herramienta | Razón del descarte |
|---|---|
| bandit B404 ×5 (`import subprocess`) | El agente **necesita** subprocess para systemd/launchctl/schtasks y el reproductor de audio. No es hallazgo por sí mismo. |
| bandit B603 ×4 (`subprocess call - untrusted input`) | Los comandos se construyen como listas literales desde funciones puras `[VERIFY: src/vigia_eew/autostart/linux_systemd.py:26]`, sin `shell=True` ni entrada de usuario. Además el entorno se sanea antes de lanzar `[VERIFY: src/vigia_eew/subprocess_env.py:25]`. |
| bandit B101 ×2 (`assert`) | En `models.py:99` y `:129`, dentro de validadores pydantic sobre datos ya validados. Riesgo real solo bajo `python -O`, que el proyecto no usa. Aun así, sustituirlos es trivial (ver R-06). |
| bandit B110 (`try/except/pass`) | `[VERIFY: src/vigia_eew/app.py:449]` es apagado best-effort durante el cierre, coherente con la política *fail-safe* del proyecto. |
| bandit B606 (`process without shell`) | `[VERIFY: src/vigia_eew/tray.py:63]` — abrir el editor del sistema con `os.startfile`/`xdg-open` es exactamente lo correcto. |
| bandit B310 (`urlopen`) | `[VERIFY: packaging/build_countries_geojson.py:47]` es un **script de build**, ejecutado a mano por el mantenedor con una URL literal; no viaja en el paquete distribuido. |
| detect-secrets: 2 "Hex High Entropy String" en `security.yml:90,121` | Son los **checksums SHA-256** que verifican los binarios de gitleaks y trivy. Es una buena práctica, no una fuga. |
| detect-secrets: 1 en `docs/API-SPEC.md:212` | Id de evento de ejemplo (`"2026abcd123"`) en la documentación de contrato. |
| detect-secrets: ~48 en `docs/reverse-sdd/analysis/history.json` | Hashes de commit del propio análisis de historial generado hoy. Artefacto de auditoría, no del producto. |
| lizard: 14 avisos `PARAM > 5` | Son constructores de inyección de dependencias `[VERIFY: src/vigia_eew/notify/controller.py:35]`. La inyección es la decisión de diseño que hace testeable el repo; penalizarla sería premiar el acoplamiento. |
| ruff `check` | 0 hallazgos con la versión del lockfile. Sin nada que reportar. |
| Semgrep, Trivy, Hadolint | No ejecutables en el entorno (ver cabecera). **No se les asigna veredicto.** |

## Gaps de tooling — qué falta para cerrar el informe

Estos gaps son del **entorno de auditoría**, no del repositorio. El repositorio sí ejecuta estas
herramientas en su CI.

| Dimensión | Qué falta | Cómo cerrarlo |
|---|---|---|
| 3 (cobertura) | Un intérprete Python ≥3.11 | `uv run pytest --cov=src --cov-branch --cov-report=json` en un entorno con 3.11+. Es el único dato numérico que este informe no puede aportar. |
| 5 (Semgrep) | Acceso a `semgrep.dev` para los rulesets | Ya corre en `security.yml`; revisar su SARIF del último run en `main`. |
| 6 (OSV) | Acceso a `api.osv.dev` | El resultado de PyPI Advisory DB es equivalente para paquetes PyPI; OSV añadiría avisos de fuentes no-PyPI. |
| 7 (Gitleaks) | Binario desde GitHub Releases | detect-secrets cubrió árbol e historia con 0 hallazgos; gitleaks usa reglas distintas y vale re-correrlo en CI (ya lo hace). |
| 8 (contenedores) | No aplica: 0 Dockerfiles | Si alguna vez se publica una imagen, activar hadolint + trivy image. |
