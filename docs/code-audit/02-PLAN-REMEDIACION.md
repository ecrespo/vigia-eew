# Plan de remediación — vigia-eew

> Deriva de `01-INFORME-AUDITORIA.md` (commit `8742c54`). **No hay P1**, así que la Fase 1
> del plan estándar queda vacía y el trabajo arranca en los P2.

## Fase 0 — Guardrails

**No hay nada que instalar.** El repo ya tiene `.pre-commit-config.yaml` con las ocho
dimensiones repartidas en dos etapas y con paridad de comandos frente a
`ci.yml`/`security.yml` `[VERIFY: .pre-commit-config.yaml:9]`.

La comparación contra la plantilla de la skill arrojó **dos huecos**, ambos de calidad y
ninguno de seguridad; van como R-05 y R-06 (Fase 3) porque son P3, no bloqueantes:

| Hook de la plantilla | ¿Presente? | Comentario |
|---|---|---|
| gitleaks | ✅ | v8.21.2, misma versión que `security.yml` |
| ruff (lint) | ✅ | vía `uv run`, paridad con CI |
| mypy strict | ✅ | |
| bandit medium+ | ✅ | |
| pytest (pre-push) | ✅ | |
| pip-audit (pre-push) | ✅ | |
| semgrep (pre-push) | ✅ | |
| trivy fs (pre-push) | ✅ | best-effort si el binario existe |
| hooks de higiene | ✅ | trailing-whitespace, check-yaml/toml, large-files |
| **lizard / complejidad** | ❌ | → R-05 |
| **ruff format --check** | ❌ | solo corre `ruff check`, no el formateador |

Lo único que conviene hacer antes de tocar código es **R-01**: sin lockfile versionado, el
resto de verificaciones de este plan no son reproducibles entre máquinas.

## Fase 1 — P1

Ninguno. La postura de seguridad del repo es sólida: 0 secretos en 48 commits, 0 CVEs,
0 hallazgos SAST de severidad media o alta.

## Fase 2 — P2 (4 ítems)

### R-01 · Versionar el lockfile y acotar los rangos (P2-1)

- **Fix:**
  1. Quitar `uv.lock` de `.gitignore:29` y commitearlo:
     `uv lock && git add -f uv.lock .gitignore`
  2. Revertir el workaround del caché de CI a su valor por defecto:
     en `.github/actions/setup-python-env/action.yml:18`, `cache-dependency-glob:
     pyproject.toml` → `uv.lock`.
  3. Poner techo mayor a las dependencias que ya saltaron de major, como mínimo
     `websockets>=17,<18` y `textual>=8,<9` `[VERIFY: pyproject.toml:32]`,
     `[VERIFY: pyproject.toml:40]`.
- **Esfuerzo:** S
- **Riesgo del fix:** el `uv.lock` inicial congela lo que resuelva la máquina que lo
  genere; conviene generarlo en CI o en un entorno limpio, no en un portátil con caché.
  Acotar los rangos puede requerir un ajuste si alguna transitiva pide más.
- **Verificación:**
  `git ls-files uv.lock` devuelve la ruta · `uv run pip-audit --skip-editable` →
  `No known vulnerabilities found` · dos clones limpios del repo resuelven el mismo árbol.

### R-02 · Separar los tests de integración con un marker (P2-2)

- **Fix:**
  1. Registrar el marker en `pyproject.toml`, junto a la config de pytest existente
     `[VERIFY: pyproject.toml:81]`:
     ```toml
     [tool.pytest.ini_options]
     markers = ["integration: exercises several real components together (no network)"]
     ```
  2. Marcar los 5 tests de `tests/test_resilience.py` (y cualquier otro que monte el
     pipeline real, p. ej. `[VERIFY: tests/test_tui.py:169]`) con
     `@pytest.mark.integration`.
  3. En `ci.yml`, separar en dos pasos: `pytest -m "not integration"` y
     `pytest -m integration`, para que el fallo diga de qué capa viene.
- **Esfuerzo:** S
- **Riesgo del fix:** ninguno funcional; es etiquetado.
- **Verificación:** `pytest -m integration -q` → 5+ tests seleccionados ·
  `pytest -m "not integration" -q` → el resto · re-ejecutar
  `python3 scripts/detect_stack.py .` → `integration_count > 0`.

### R-03 · Que el suite por defecto corra de verdad sin display (P2-3)

- **Fix:** elegir una de las dos, no ambas.
  - **(a) Coherente con lo que ya documenta el repo** — añadir el guard existente a los
    dos tests, igual que los smokes de Tkinter:
    ```python
    @pytest.mark.skipif(not os.environ.get("VIGIA_GUI_TESTS"), reason="needs a display")
    ```
    en `[VERIFY: tests/test_tray.py:81]` y `[VERIFY: tests/test_app.py:175]`.
  - **(b) Conservar la cobertura** — ejecutar el CI y el hook bajo `xvfb-run -a`, y
    corregir `[VERIFY: CLAUDE.md:139]`, que hoy afirma que el suite corre headless.

  Recomiendo **(a)**: mantiene la promesa de "headless por defecto" que el resto del
  proyecto respeta, y esos dos tests solo verifican que se ensambla el menú de la bandeja
  — cobertura que la opción (b) compraría a cambio de una dependencia de sistema en todas
  las máquinas de desarrollo.
- **Esfuerzo:** S
- **Riesgo del fix:** con (a) se pierde cobertura de `build_icon` en el suite por defecto;
  queda cubierta al correr con `VIGIA_GUI_TESTS=1`.
- **Verificación:** en un entorno sin `DISPLAY`, `pytest -q` → 0 failed (hoy: 2 failed).

### R-04 · Extraer el cableado de `app.py` (P2-4)

- **Fix:** mover las fábricas a un módulo de composición propio (`wiring.py` o
  `composition.py`), dejando `Application` como orquestador de ciclo de vida:
  `_build_supervisor` `[VERIFY: src/vigia_eew/app.py:85]`, `_build_geo_filter`
  `[VERIFY: src/vigia_eew/app.py:137]`, `_build_controller`
  `[VERIFY: src/vigia_eew/app.py:158]` y `_build_tray`
  `[VERIFY: src/vigia_eew/app.py:178]`. Son funciones puras de construcción: se pueden
  testear sin instanciar la app.
- **Esfuerzo:** M
- **Riesgo del fix:** `app.py` es el hotspot #1 del repo y su cobertura es del 64 %;
  refactorizarlo con esa red de seguridad es el riesgo real. **Hacerlo después de R-02**,
  con los tests de integración ya identificados, y subir antes la cobertura de las rutas
  `execute`/`run_tui` que hoy no se ejercitan (líneas 400-451).
- **Verificación:** `pytest -q` → 345 passed · `wc -l src/vigia_eew/app.py` < 300 ·
  `pytest --cov=vigia_eew.app` → ≥ 64 % (no debe bajar).

## Fase 3 — P3 (batch)

| # | Ítem | Fix | Esfuerzo | Verificación |
|---|---|---|---|---|
| R-05 | Complejidad sin gate (P3-2, P3-3) | Añadir al pre-commit: `lizard src --CCN 12 --warnings_only --exit_code 1` y `flake8 --select=CCR001 --max-cognitive-complexity=12 src/`. Antes de activarlo, bajar `_process_text` `[VERIFY: src/vigia_eew/ingest/rest_geofon.py:134]` extrayendo el parseo de fila, y `main()` `[VERIFY: src/vigia_eew/cli.py:56]` con un despacho por diccionario | M | `lizard src --CCN 12 -w` → sin avisos · `flake8 --select=CCR001` → vacío |
| R-06 | `ruff format` no verificado | Añadir el hook `ruff format --check .` (el repo ya usa ruff, solo falta el formateador) | S | `ruff format --check .` → `N files already formatted` |
| R-07 | Duplicación USGS↔GEOFON (P3-1) | **No actuar todavía.** 0,85 % está en verde y ADR-016 difirió la abstracción a propósito. Extraer un `FdsnPoller` base con el parser parametrizado **cuando entre la tercera fuente FDSN** — es la regla de tres, y el ADR ya la anticipó | L (diferido) | `jscpd src --min-tokens 70` → clones sobre `ingest/` en 0 |
| R-08 | Ruido de escaneo en artefactos generados (P3-5) | Crear `.gitleaksignore` con `graphify-out/` y `.codegraph/`, y añadir `--skip-dirs graphify-out,.codegraph` al hook de trivy `[VERIFY: .pre-commit-config.yaml:83]` | S | `gitleaks detect --source . --no-git` → `no leaks found` |
| R-09 | Sincronización por reloj de pared (P3-4) | En `[VERIFY: tests/test_processor.py:106]`, sustituir `asyncio.sleep(0.05)` por una espera sobre condición (`await asyncio.wait_for(cap.first_alert, timeout=1)`) o por el `sleep` inyectado que ya usa el resto del suite | S | `pytest tests/test_processor.py -q -p no:randomly` estable en 20 ejecuciones |
| R-10 | Tests sin aserción (P3-6) | Añadir aserción sobre el efecto observable en los 4 tests "no debe lanzar": que se emitió el log, o que el backend no se invocó | S | Los 4 tests fallan si se vacía el cuerpo de la función bajo prueba |
| R-11 | `logging_conf` sin verificación | Crear `tests/test_logging_conf.py`: timestamp en UTC, ambos handlers registrados, rotación, y que un directorio no escribible **no** impida arrancar | M | `pytest tests/test_logging_conf.py -q` → ≥ 4 tests · cobertura de `logging_conf.py` con aserciones reales |

## Orden recomendado

```
R-01 (lockfile)  →  R-02 (markers)  →  R-03 (headless)  →  R-08, R-06, R-09, R-10 (batch S)
                                            ↓
                                    R-11 (logging)  →  R-05 (complejidad + gate)  →  R-04 (app.py)
                                                                                          ↓
                                                                              R-07 (diferido: 3ª fuente FDSN)
```

R-01 primero porque hace reproducible todo lo demás. R-04 al final porque es el único con
riesgo real de regresión y se beneficia de que R-02 y R-11 ya hayan reforzado la red.

## Seguimiento

| Ítem | Prioridad | Dueño | Verificación | Estado |
|---|---|---|---|---|
| R-01 Lockfile versionado | P2 | | `git ls-files uv.lock` no vacío | pendiente |
| R-02 Marker de integración | P2 | | `pytest -m integration` selecciona ≥5 | pendiente |
| R-03 Suite headless | P2 | | `pytest -q` sin `DISPLAY` → 0 failed | pendiente |
| R-04 Extraer cableado | P2 | | `app.py` < 300 líneas, cobertura no baja | pendiente |
| R-05 Gate de complejidad | P3 | | `lizard --CCN 12 -w` sin avisos | pendiente |
| R-06 `ruff format --check` | P3 | | hook en verde | pendiente |
| R-07 Unificar pollers FDSN | P3 | | diferido a la 3ª fuente | diferido |
| R-08 Ignorar artefactos generados | P3 | | `gitleaks` → 0 en árbol | pendiente |
| R-09 Quitar sleep de test | P3 | | 20 ejecuciones estables | pendiente |
| R-10 Aserciones en 4 tests | P3 | | fallan con la función vaciada | pendiente |
| R-11 Tests de logging | P3 | | ≥4 tests nuevos | pendiente |

## Riesgos aceptados

| Riesgo | Razón |
|---|---|
| FUNVISIS se consume por HTTP plano `[VERIFY: src/vigia_eew/config.py:79]` | La fuente no ofrece HTTPS válido para ese endpoint. El dato es público y de solo lectura, no cruzan credenciales ni datos del usuario, y la alternativa es perder la cobertura sísmica local de Venezuela. Documentado en ADR-015. **Revisar periódicamente** si FUNVISIS habilita TLS |
| La IP de origen queda expuesta a `ipapi.co` `[VERIFY: src/vigia_eew/geoloc.py:39]` | Única excepción de privacidad del proyecto. Se dispara solo por *ausencia* de configuración, ocurre una vez y se cachea, y se desactiva por completo definiendo `[reference]`. Documentado en ADR-011 |
| Semgrep no verificado en esta auditoría | El registry está bloqueado por la política de red de **este entorno**, no del proyecto. `security.yml` lo ejecuta en cada PR a `main`. Sin acción |
