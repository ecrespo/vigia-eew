# Auditoría de código y seguridad — vigia-eew

**Fecha:** 2026-08-16 · **Stack:** Python 3.11+ (agente de escritorio, sin servidor)
**Commit auditado:** `8742c54`

**Herramientas ejecutadas:** gitleaks 8.21.2 (tree + historia), bandit 1.9.4,
pip-audit 2.10.1, jscpd 5.0.15, pylint 4.0.7 (duplicate-code), lizard 1.23.0,
flake8-cognitive-complexity, mypy 2.3.1 (strict), ruff 0.16.3, pytest 9.1.1 + cov (branch).

**No ejecutadas:**
- **Semgrep 1.173.0** — instalado, pero el registry (`semgrep.dev`) está bloqueado por la
  política de red de este entorno (403 al CONNECT). **Sí corre en el CI del repo**
  (`security.yml`), así que la dimensión no queda descubierta; simplemente no pude
  reproducirla aquí.
- **Hadolint / Trivy image / Dockle** — el repo no tiene Dockerfile ni compose
  (`[TOOL: detect_stack.py → dockerfiles: 0]`). Dimensión 8 **no aplica**.

## Resumen ejecutivo

El repositorio está en muy buen estado de seguridad y calidad: **cero secretos en los 48
commits de historia, cero CVEs en dependencias, cero hallazgos SAST de severidad media o
alta, 0,85 % de duplicación y 89 % de cobertura con branch coverage**. No hay ningún
hallazgo P1.

El hallazgo más serio es P2 y es de *reproducibilidad*, no de vulnerabilidad: **el
lockfile no está versionado**, así que el `pip-audit` que hoy da limpio valida el conjunto
de versiones que resolvió esta máquina, no un conjunto fijado. Con rangos `>=` abiertos en
las nueve dependencias de runtime, dos desarrolladores pueden auditar árboles distintos y
ambos ver verde.

La fortaleza principal es que el gate ya existe y es serio: `.pre-commit-config.yaml`
replica en dos etapas las mismas ocho dimensiones que audita este informe. El primer paso
del plan no es instalar herramientas — es versionar `uv.lock` para que ese gate audite
algo determinista.

## Scorecard

| # | Dimensión | Veredicto | Evidencia |
|---|-----------|-----------|-----------|
| 1 | DRY | 🟢 | `[TOOL: jscpd → 0,85 % líneas duplicadas, 2 clones]` — muy por debajo del umbral verde (3 %). Ambos clones entre `rest_usgs.py` y `rest_geofon.py`; `[TOOL: pylint R0801 → 3 bloques]` mismos ficheros |
| 2 | SOLID | 🟡 | **S🟡 O🟢 L🟢 I🟢 D🟢**. DIP limpio: el dominio no importa infraestructura `[VERIFY: src/vigia_eew/pipeline/dedup.py:1]`. SRP es el único ámbar: `app.py` con 451 líneas concentra el cableado `[VERIFY: src/vigia_eew/app.py:54]` |
| 3 | Pruebas unitarias | 🟢 | `[TOOL: pytest-cov → 89 % global con branch coverage, 345 tests]`. Módulos de dominio al 100 % (dedup, filter, config, models, geocode, timeutil) |
| 4 | Pruebas integración | 🟡 | Existen y son reales `[VERIFY: tests/test_resilience.py:94]`, pero **sin marker ni carpeta propia**: `[TOOL: detect_stack.py → integration_count: 0]` no las ve, y el CI no puede ejecutarlas por separado |
| 5 | SAST | 🟢 | `[TOOL: bandit → 0 HIGH, 0 MEDIUM, 15 LOW]`, y las 15 LOW son subprocess con lista de argumentos sin shell (ver descartados). Semgrep pendiente de CI (ver arriba) |
| 6 | SCA | 🟡 | `[TOOL: pip-audit → No known vulnerabilities found]` — pero `[GAP: uv.lock en .gitignore:29]`: el resultado no es reproducible |
| 7 | Secretos | 🟢 | `[TOOL: gitleaks --log-opts=--all → 48 commits escaneados, no leaks found]`. El único hit del árbol de trabajo es un falso positivo en un artefacto gitignoreado (ver descartados) |
| 8 | Contenedores | ⚪ | **No aplica** — `[TOOL: detect_stack.py → dockerfiles: 0, compose: 0]`. Es un agente de escritorio que se distribuye como binario nativo y wheel, no como imagen |

## Fortalezas

Con la misma exigencia de evidencia que los hallazgos:

1. **Tipado estricto real, no decorativo.** `[TOOL: mypy --strict → Success: no issues
   found in 40 source files]`, con una única excepción documentada (`pystray`, que no
   publica stubs) `[VERIFY: pyproject.toml:98]`. Pasar strict en 40 módulos con una sola
   exención es poco común.

2. **Superficie de ataque deliberadamente mínima.** Sin `eval`, `exec`, `pickle`,
   `os.system` ni `shell=True` en todo `src/`; sin un solo `verify=False` ni
   `ssl._create_unverified_context`. Todas las llamadas HTTP llevan timeout explícito
   `[VERIFY: src/vigia_eew/ingest/rest_usgs.py:103]`,
   `[VERIFY: src/vigia_eew/geoloc.py:47]`.

3. **El gate ya cubre las 8 dimensiones, en dos etapas.** `.pre-commit-config.yaml`
   separa rápido (gitleaks, ruff, mypy, bandit) de lento (pytest, pip-audit, semgrep,
   trivy) `[VERIFY: .pre-commit-config.yaml:9]`, con paridad de comandos con
   `ci.yml`/`security.yml`. Muchos repos auditados no tienen ni la mitad.

4. **Inyección de dependencias sistemática.** `connect`, `sleep`, `client`, `runner`,
   `create_window`, `now` se inyectan `[VERIFY: src/vigia_eew/pipeline/filter.py:37]`,
   `[VERIFY: src/vigia_eew/ingest/rest_usgs.py:45]`. Es la razón de que 345 tests corran
   sin red, sin reloj real y casi sin GUI — y de que la cobertura de branches sea posible.

5. **Complejidad bajo control.** `[TOOL: lizard → CCN medio 2,5 · 250 funciones · 1 sola
   supera CCN 10]`. En un proyecto con cuatro integraciones externas y dos frontends, eso
   es notable.

6. **Aislamiento de fallos aplicado con consistencia.** Cada efecto opcional atrapa lo
   suyo y degrada: toast `[VERIFY: src/vigia_eew/notify/toast.py:40]`, bandeja
   `[VERIFY: src/vigia_eew/tray.py:110]`, geolocalización
   `[VERIFY: src/vigia_eew/geoloc.py:39]`. No es un patrón declarado y luego olvidado.

## Hallazgos

No hay hallazgos **P1**.

### P2-1 — Versionar el lockfile: la auditoría de dependencias no es reproducible

- **Dimensión:** 6 (SCA) · **Evidencia:** `[GAP: .gitignore:29 → uv.lock]` +
  `[VERIFY: pyproject.toml:31-41]` (nueve dependencias, todas con rango `>=` abierto)
- **Impacto:** `pip-audit` da limpio hoy sobre las versiones que resolvió esta máquina.
  Otra máquina, otro día, resuelve otro árbol y el resultado no tiene por qué coincidir.
  La divergencia ya es grande: declarado `websockets>=12.0` → resuelto **17.0.1**;
  `textual>=0.60` → **8.2.8**; `mypy>=1.10` → **2.3.1**. Son saltos de varias versiones
  mayores, y el CI lo sabe: cachea sobre `pyproject.toml` porque el glob por defecto de
  `uv.lock` no encuentra nada `[VERIFY: .github/actions/setup-python-env/action.yml:18]`.
  Un build de release puede llevar una dependencia que nadie auditó.
- **Fix:** → PLAN-REMEDIACION R-01

### P2-2 — Los tests de integración no se distinguen de los unitarios

- **Dimensión:** 4 · **Evidencia:** `[TOOL: detect_stack.py → unit: 35, integration: 0]`
  frente a `[VERIFY: tests/test_resilience.py:94]` (pipeline completo con `Normalizer`,
  `GeoFilter` y `Deduplicator` reales) y `[VERIFY: tests/test_resilience.py:186]`
  (`WSIngestor` real dentro de un `Supervisor` real). Sin marcadores:
  `[TOOL: grep pytest.mark → solo skipif/parametrize]`
- **Impacto:** la capa de integración existe y es de buena calidad, pero es **invisible
  para el tooling**: no se puede ejecutar por separado en CI, no se puede excluir del gate
  rápido, y cualquier análisis automático la cuenta como cero. Hoy es un problema de
  visibilidad; el día que estos tests tarden, no habrá forma de separarlos sin
  reetiquetar a mano.
- **Fix:** → PLAN-REMEDIACION R-02

### P2-3 — Dos tests del suite por defecto exigen display real

- **Dimensión:** 3 · **Evidencia:** `[VERIFY: tests/test_tray.py:81]` y
  `[VERIFY: tests/test_app.py:175]` fallan con `Xlib DisplayNameError` sin `DISPLAY`.
  Verificado en esta auditoría: sin `xvfb` → 2 failed, 343 passed; con
  `xvfb-run` → 345 passed. Contradice lo que documenta el propio repo
  `[VERIFY: CLAUDE.md:139]` ("el suite por defecto corre headless") y el guard
  `VIGIA_GUI_TESTS=1` que sí usan los smokes de Tkinter.
- **Impacto:** el gate `pre-push` de pytest falla en cualquier máquina o contenedor sin
  entorno gráfico. El CI lo evita porque el runner de GitHub trae display, así que el
  fallo aparece solo en local — justo donde desanima a instalar el hook.
- **Fix:** → PLAN-REMEDIACION R-03

### P2-4 — `app.py` concentra el cableado (SRP)

- **Dimensión:** 2 · **Evidencia:** `[VERIFY: src/vigia_eew/app.py:54]` — 451 líneas, el
  archivo de código más grande del repo; `[TOOL: lizard → app.py:57 __init__ 8 params;
  app.py:158 _build_controller 6 params]`. Además es el hotspot de código #1 del historial
  (11 toques) y su cobertura es la segunda más baja del proyecto:
  `[TOOL: pytest-cov → app.py 64 %]`.
- **Impacto:** cada feature nueva pasa por aquí (bandeja, TUI, país, geolocalización), lo
  que lo convierte en punto de conflicto y de regresión. **No es urgente**: solo tiene 3
  métodos públicos, el resto son helpers privados, y el resto de dimensiones SOLID están
  verdes. Es deuda que cobra intereses, no un defecto.
- **Fix:** → PLAN-REMEDIACION R-04

### P3 — Calidad (batch)

| # | Hallazgo | Dimensión | Evidencia | Nota |
|---|---|---|---|---|
| P3-1 | Lógica de cursor/`Retry-After`/piso duplicada entre USGS y GEOFON | 1 | `[TOOL: jscpd → 2 clones: rest_geofon.py:57-78 ↔ rest_usgs.py:47-68 y rest_geofon.py:164-180 ↔ rest_usgs.py:142-157]`, `[TOOL: pylint R0801 → 3 bloques]` | 0,85 % está en verde, pero es **lógica de negocio**, no boilerplate: si un timeout o un piso divergen, lo hacen en silencio. ADR-016 lo difirió a propósito "hasta una tercera fuente FDSN" |
| P3-2 | `_process_text` supera ambos umbrales de complejidad | 2 | `[TOOL: lizard → CCN 13 (>10)]`, `[TOOL: flake8 CCR001 → 16 > 12]` en `[VERIFY: src/vigia_eew/ingest/rest_geofon.py:134]` | Única función del repo sobre CCN 10. Parsea texto pipe-delimitado con validación por fila |
| P3-3 | `main()` supera la complejidad cognitiva | 2 | `[TOOL: flake8 CCR001 → 13 > 12]` en `[VERIFY: src/vigia_eew/cli.py:56]` | Despacho de flags; crece con cada modo nuevo |
| P3-4 | Sincronización por reloj de pared en un test | 3 | `[VERIFY: tests/test_processor.py:106]` — `await asyncio.sleep(0.05)` para que la tarea drene la cola | Único caso del suite; contrasta con el patrón dominante de inyectar `sleep` `[VERIFY: tests/test_rest_usgs.py:83]`. Riesgo de flake bajo carga de CI |
| P3-5 | Falso positivo de gitleaks en artefacto generado | 7 | `[TOOL: gitleaks --no-git → 1 leak en graphify-out/cache/stat-index.json]`; el fichero está gitignoreado `[VERIFY: .gitignore:37]` y no rastreado (`git ls-files graphify-out/` → 0) | El hook `trivy fs .` de pre-push escanea el árbol completo, incluidos ignorados, y el repo ahora recomienda instalar graphify `[VERIFY: CLAUDE.md:42]`. Ruido futuro evitable |
| P3-6 | Cuatro tests sin aserción explícita | 3 | `[VERIFY: tests/test_toast.py:62]`, `[VERIFY: tests/test_tray.py:62]`, `[VERIFY: tests/test_tui.py:153]`, `[VERIFY: tests/test_autostart_macos.py:69]` | Patrón legítimo "no debe lanzar", pero pasarían igual si la función no hiciera nada. Añadir aserción sobre el efecto (log emitido, backend no invocado) los haría verificar de verdad |

## Hallazgos descartados

| Reporte de herramienta | Razón del descarte |
|---|---|
| `bandit B404` × 6 (import de `subprocess`) | Importar `subprocess` no es un defecto. El repo lo necesita para autoarranque, sonido y abrir la config |
| `bandit B603` × 5 (`subprocess` sin shell) | Es el patrón **correcto**: lista de argumentos, sin `shell=True`, y con entorno saneado a propósito `[VERIFY: src/vigia_eew/tray.py:67]`. Bandit marca la categoría, no un fallo |
| `bandit B606` × 1 (`os.startfile`) | Rama exclusiva de Windows para abrir el `config.toml` con la app asociada `[VERIFY: src/vigia_eew/tray.py:63]` |
| `bandit B101` × 2 (`assert` en producción) | Estrechamiento de tipos para mypy: `_require_utc` solo devuelve `None` si recibe `None` `[VERIFY: src/vigia_eew/models.py:31]`, y el campo es obligatorio, así que la aserción no puede dispararse. Con `python -O` el comportamiento no cambia |
| `bandit B110` × 1 (`try/except/pass`) | Destrucción idempotente de la ventana raíz en el apagado, con comentario que lo explica `[VERIFY: src/vigia_eew/app.py:451]`. La alternativa (propagar) rompería el cierre limpio |
| `gitleaks generic-api-key` en `graphify-out/cache/stat-index.json` | Es un hash SHA-256 de contenido (`api-spec.md":"ca0ef1fb…`), no una credencial. Fichero generado y gitignoreado. Se registra igualmente como P3-5 por el ruido que causará |
| `lizard`: 16 avisos de `__init__` con >5 parámetros | Son constructores de inyección de dependencias — la práctica que hace testeable el repo. Penalizarlos premiaría el acoplamiento oculto |
| `isinstance` × 15 | No son escaleras de tipos (OCP); son guardas de validación sobre JSON externo `[VERIFY: src/vigia_eew/pipeline/normalize.py:168]`. Uso correcto en un borde no confiable |
| `NotImplementedError` en `autostart/__init__.py:82` | No es LSP roto: es una fábrica que rechaza plataformas no soportadas, con test propio `[VERIFY: tests/test_autostart.py:48]` |

## Nota sobre la cobertura del logging

`logging_conf.py` marca 97 % `[TOOL: pytest-cov]`, pero **no existe
`tests/test_logging_conf.py`**: el módulo se ejecuta al arrancar la app en otros tests, sin
que nadie afirme nada sobre su comportamiento. Ni el timestamp en UTC, ni la rotación, ni
la tolerancia a un directorio no escribible tienen aserción.

Es el mejor ejemplo del repo de que **la cobertura mide ejecución, no verificación** — y
rima con lo que ya ocurrió con `StateStore.prune()`, que estuvo muerto 14 releases con su
test unitario en verde. No lo elevo a hallazgo formal porque el módulo es pequeño y su
fallo no compromete la seguridad, pero conviene tenerlo presente al leer el 89 % global.
