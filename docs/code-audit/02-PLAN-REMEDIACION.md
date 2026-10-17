# Plan de remediación — vigia-eew

**Base:** `01-INFORME-AUDITORIA.md` (commit `c3a2c29`, 2026-09-06).
**0 hallazgos P1 · 5 P2 · 8 P3.** El plan es de endurecimiento, no de rescate: el repositorio no
tiene deuda de seguridad, tiene **huecos de gate**.

Esfuerzo: **S** ≤ 1 h · **M** ≤ media jornada · **L** > 1 jornada.

---

## Fase 0 — Guardrails (antes de tocar código)

Aplicar `.pre-commit-config.yaml.propuesto` (en este mismo directorio), que **añade** hooks al
config existente sin quitar ninguno. Congela el estado actual: nada nuevo entra peor de lo que
está. Todo lo demás del plan depende de esta fase.

```bash
cp docs/code-audit/.pre-commit-config.yaml.propuesto .pre-commit-config.yaml
uv run pre-commit install                       # instala pre-commit y pre-push
uv run pre-commit run --all-files               # primera pasada: fallará en R-02
```

**Verificación:** `uv run pre-commit validate-config .pre-commit-config.yaml` → sin errores, y
`uv run pre-commit run --all-files --hook-stage pre-push` termina describiendo qué falla.

---

## Fase 1 — P1

**Vacía.** No se encontró ningún hallazgo P1: sin secretos en árbol ni historia, sin SAST HIGH,
sin CVE alcanzable en runtime.

---

## Fase 2 — P2 (5 ítems)

### R-01 · Exigir un umbral de cobertura por módulo (P2-1)

- **Fix:** añadir el gate a la CI, no solo la medición. En `.github/workflows/ci.yml:53`, tras
  `--cov-report=term-missing`, añadir `--cov-fail-under=70`. Y en `pyproject.toml`, umbrales
  diferenciados con `[tool.coverage.report]`:

  ```toml
  [tool.coverage.report]
  fail_under = 70
  exclude_also = ["if TYPE_CHECKING:", "raise NotImplementedError"]
  ```

  Antes de fijar el número, ejecutar una vez `uv run pytest --cov=vigia_eew --cov-branch
  --cov-report=term-missing` y **calibrar con el valor real** — este informe no pudo medirlo
  (Python 3.10 en el entorno de auditoría). Aplicar los mínimos por criticidad: `pipeline/` y
  `state.py` (lógica que decide si alertar) ≥ 85 % con *branch coverage*; `ingest/` ≥ 70 %;
  `tray.py`, `alert_window.py`, `sound.py` (adaptadores de E/S) ≥ 40 %.
- **Esfuerzo:** S · **Riesgo del fix:** que la CI empiece a fallar si algún módulo está por
  debajo. Es el objetivo; calibrar el umbral inicial al valor medido y subirlo por escalones.
- **Verificación:** `uv run pytest --cov=vigia_eew --cov-branch --cov-fail-under=70` → exit 0, y
  bajar `fail_under` a un valor imposible debe hacerlo fallar (prueba de que el gate muerde).

### R-02 · Poner `ruff format` en el gate y formatear los 19 archivos (P2-2)

- **Fix:** añadir el hook `ruff-format` (incluido en el config propuesto) y ejecutar una vez
  `uv run ruff format .` en un commit **aislado**, sin cambios funcionales, para que el ruido de
  diff no contamine ningún PR de producto.
- **Esfuerzo:** S · **Riesgo del fix:** ninguno funcional; el commit tocará 19 archivos y hará
  ruido en `git blame`. Registrarlo en `.git-blame-ignore-revs`.
- **Verificación:** `uv run ruff format --check .` → `79 files already formatted`, exit 0.

### R-03 · Separar unitarias de integración con markers (P2-3)

- **Fix:** declarar los markers en `pyproject.toml:81` y etiquetar los tests e2e:

  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  asyncio_mode = "auto"
  markers = [
      "integration: cruza componentes reales (pipeline completo, supervisor + ingestores)",
      "gui: requiere Tkinter real (VIGIA_GUI_TESTS=1)",
  ]
  ```

  Marcar con `@pytest.mark.integration` los 5 de `tests/test_resilience.py` y con
  `@pytest.mark.gui` los tres `test_smoke_*` de `tests/test_alert_window.py:139,157,174`
  (hoy usan `skipif` sobre una variable de entorno; el marker es explícito y componible).
  Luego: pre-commit corre `pytest -m "not integration and not gui"`, CI corre todo.
- **Esfuerzo:** S · **Riesgo del fix:** ninguno; los markers no cambian el comportamiento.
- **Verificación:** `uv run pytest -m integration --collect-only -q` → 5 tests;
  `uv run pytest -m "not integration" --collect-only -q` → 339.

### R-04 · Cubrir DRY y complejidad en el gate (P2-4)

- **Fix:** el config propuesto añade tres hooks locales: `jscpd` (umbral 3 %), `lizard`
  (`--CCN 15 --length 200`) y `flake8 --select=CCR001 --max-cognitive-complexity=12`. Ninguno
  bloquea hoy salvo CCR001, que fallaría en los dos casos de P3-5 — arreglarlos en la Fase 3 o
  subir temporalmente el umbral a 16 con un TODO fechado.
- **Esfuerzo:** S · **Riesgo del fix:** el gate se vuelve más lento (~5 s con jscpd). Si molesta,
  mover jscpd a la etapa pre-push.
- **Verificación:** `npx jscpd src --min-tokens 70 --threshold 3` → exit 0;
  `uv run lizard src --CCN 15 --length 200 -w` → sin avisos.

### R-05 · Actualizar `pip` en el entorno de desarrollo (P2-5)

- **Fix:** no es dependencia declarada del proyecto, sino transitiva de `pip-audit` vía `pip-api`.
  Basta con `uv lock --upgrade-package pip` y confirmar que el lock resuelve `pip>=26.2`.
  Alternativamente, esperar a la próxima actualización de `pip-audit`.
- **Esfuerzo:** S · **Riesgo del fix:** ninguno; no toca runtime ni artefactos distribuidos.
- **Verificación:** `grep -A1 'name = "pip"' uv.lock` → `version = "26.2"` o superior; y
  `uv run pip-audit --skip-editable` → sin `CVE-2026-13346`.
- **Alternativa aceptable:** riesgo aceptado y documentado, dado que `pip` no viaja en el wheel ni
  en los binarios PyInstaller. Si se elige esta vía, dejarlo escrito con fecha de revisión.

---

## Fase 3 — P3 (batch)

| # | Fix | Esfuerzo | Verificación |
|---|---|---|---|
| P3-1 | Extraer el constructor y el bucle de cursor comunes de `rest_usgs.py`/`rest_geofon.py` a una base `FDSNCursorPoller`. **Solo si entra una tercera fuente FDSN** — con dos, ADR-016 ya descartó la abstracción y el clon es de 39 líneas sobre 9.186 | M | `npx jscpd src` → clones de producción en 0 |
| P3-2 | Reducir `Application`: extraer las fábricas (`_build_supervisor`, `_build_controller`, `_build_tray`, `_build_geo_filter`) a un módulo `wiring.py`, dejando `Application` como orquestador de los tres modos | M | `lizard src/vigia_eew/app.py` → NLOC < 300; `mypy src` sigue limpio |
| P3-3 | Sustituir la escalera de `normalize.py:55` por un registro `dict[Source, Callable]` poblado en el módulo. Reduce de ≥5 a 3 los archivos a tocar por fuente nueva | S | Añadir una fuente ficticia en un test y comprobar que solo requiere el mapper y el `Literal` |
| P3-4 | Agrupar los 12 métodos públicos de `StateStore` en vistas cohesivas (alertas / cursores / ubicación) o documentar explícitamente que es una fachada deliberada sobre un único documento | S | `solid-signals.txt` → sin clases con >10 públicos, o nota de diseño en `lat.md/state.md` |
| P3-5 | Bajar la complejidad cognitiva de `cli.py:56` (13) y `rest_geofon.py:133` (16). En el segundo, extraer el parseo de fila a una función pura `_parse_row` — mejora además el testeo del caso "fila corrupta" | S | `flake8 --select=CCR001 --max-cognitive-complexity=12 src/` → exit 0 |
| P3-6 | Reemplazar `asyncio.sleep(0.05)` por espera sobre un `asyncio.Event` o el reloj inyectado que ya usa el resto de la suite | S | `grep -n 'asyncio.sleep(0\.' tests/` → sin resultados |
| P3-7 | Dar assert real a los tres tests de "no lanza": comprobar el efecto observable (que se registró el warning, que el estado no cambió), no solo la ausencia de excepción | S | Los tres tests fallan si se vacía el cuerpo de la función bajo prueba |
| P3-8 | Extraer el fixture duplicado de `test_resilience.py:157` / `test_ws_emsc.py:43` a `conftest.py` | S | `npx jscpd tests` → 1 clon menos |
| — | Sustituir los dos `assert` de `models.py:99,129` por `if ... raise ValueError`, para que sobrevivan a `python -O` | S | `bandit -r src --severity-level=low` → sin B101 |

---

## Fase 4 — Cerrar los gaps de tooling del propio informe

Estos no son defectos del repo: son datos que esta auditoría no pudo producir.

| Gap | Acción | Verificación |
|---|---|---|
| Cobertura sin medir | Ejecutar la suite en Python ≥3.11 y anotar el valor real en este plan (entrada R-01) | `coverage.xml` con `line-rate` por paquete |
| Semgrep no ejecutado | Descargar el SARIF del último run de `security.yml` en `main` y revisar los hallazgos | artefacto `semgrep-sarif` sin findings de severidad ERROR |
| Gitleaks no ejecutado | Revisar el artefacto `gitleaks-sarif` del último run | 0 hallazgos, coincidiendo con detect-secrets |
| Trivy no ejecutado | Revisar el artefacto `trivy-fs` del último run | 0 HIGH/CRITICAL |

---

## Seguimiento

| Ítem | Prioridad | Esfuerzo | Verificación | Estado |
|---|---|---|---|---|
| Fase 0 · pre-commit propuesto | — | S | `pre-commit validate-config` | pendiente |
| R-01 · umbral de cobertura | P2 | S | `pytest --cov-fail-under` muerde | pendiente |
| R-02 · `ruff format` en gate | P2 | S | `ruff format --check .` exit 0 | pendiente |
| R-03 · markers unit/integration | P2 | S | `pytest -m integration` → 5 | pendiente |
| R-04 · DRY + complejidad en gate | P2 | S | `jscpd --threshold 3` exit 0 | pendiente |
| R-05 · actualizar `pip` | P2 | S | `pip-audit` sin CVE-2026-13346 | pendiente |
| Fase 3 · P3 batch (9 ítems) | P3 | M | ver tabla | pendiente |
| Fase 4 · cerrar gaps del informe | — | S | artefactos de CI revisados | pendiente |

**Ruta crítica realista:** Fases 0 a 2 son **cinco tareas de tamaño S**. Una tarde de trabajo
cierra los cinco P2 y deja las ocho dimensiones con gate propio.
