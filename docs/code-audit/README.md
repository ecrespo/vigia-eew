# Auditoría de código y seguridad — vigia-eew

Auditoría de 8 dimensiones ejecutada el **2026-09-06** sobre el commit `c3a2c29`, en una **copia
aislada** del repositorio (disco nativo, modo solo lectura, entorno virtual propio). El repositorio
no fue modificado por la auditoría: todo lo que hay aquí son artefactos nuevos bajo `docs/`.

| Archivo | Contenido |
|---|---|
| [01-INFORME-AUDITORIA.md](01-INFORME-AUDITORIA.md) | Scorecard de las 8 dimensiones, 7 fortalezas, 13 hallazgos rankeados y 11 hallazgos descartados con su razón |
| [02-PLAN-REMEDIACION.md](02-PLAN-REMEDIACION.md) | Fase 0 (guardrails) + fixes por severidad con esfuerzo y comando de verificación |
| [.pre-commit-config.yaml.propuesto](.pre-commit-config.yaml.propuesto) | El config actual **más** 9 hooks que cierran los gaps; validado con `pre-commit validate-config` |
| `analysis/` | Salida cruda de cada herramienta ejecutada |

## Veredicto de un vistazo

| Dimensión | | Dimensión | |
|---|---|---|---|
| 1 · DRY | 🟢 0,95 % | 5 · SAST | 🟢 0 HIGH |
| 2 · SOLID | 🟡 S🟡 O🟡 L🟢 I🟢 D🟢 | 6 · SCA | 🟢 1/90, no runtime |
| 3 · Unitarias | ⚪ cobertura no medible aquí | 7 · Secretos | 🟢 0 en árbol e historia completa |
| 4 · Integración | 🟡 sin separación formal | 8 · Contenedores | ⚫ fuera de alcance (0 Dockerfiles) |

**0 hallazgos P1 · 5 P2 · 8 P3.** Los cinco P2 son de tamaño S: una tarde de trabajo los cierra.

## Herramientas ejecutadas

ruff 0.15.20 (la del lockfile) y 0.16.6 · bandit 1.9.4 · mypy 2.1.0 · lizard 1.24.0 ·
flake8 7.3.0 + flake8-cognitive-complexity · pylint 4.0.8 (`duplicate-code`) · jscpd 4 ·
detect-secrets 1.5.0 (árbol + 59 commits de todas las ramas) · PyPI Advisory Database (90 paquetes).

## Herramientas NO ejecutadas — sustituciones y gaps

La regla aplicada: **si una herramienta no está disponible, se sustituye por un equivalente y el
gap se documenta; nunca se fabrica un resultado.**

| No ejecutada | Motivo verificado | Sustituto | ¿Queda gap? |
|---|---|---|---|
| Gitleaks | binario en GitHub Releases; `github.com` no resuelve | detect-secrets sobre árbol **e historia** | No — cobertura equivalente, reglas distintas |
| pip-audit (OSV) | `api.osv.dev` → HTTP 403 | PyPI Advisory Database, la misma fuente de `pip-audit -s pypi` | Parcial — OSV añade avisos de fuentes no-PyPI |
| pytest + cobertura | proyecto requiere Python ≥3.11; el entorno solo tiene 3.10 y no puede descargar otro | ninguno posible | **Sí** — dimensión 3 sin veredicto de cobertura |
| Semgrep | rulesets desde `semgrep.dev` | Bandit + revisión dirigida | Parcial — ya corre en `security.yml` |
| Trivy · Hadolint · Dockle | binarios en GitHub; **y el repo no tiene Dockerfiles** | — | No — dimensión fuera de alcance |

El único dato numérico que este informe **no** puede aportar es el porcentaje de cobertura. Está
registrado como tal en el scorecard (⚪ "no evaluado") y como Fase 4 del plan de remediación.

## Relación con el resto de `docs/`

- [`../CONTEXT_REPORT.md`](../CONTEXT_REPORT.md) — capas CodeGraph / Graphify / lat.md. El hallazgo
  P3-2 (`Application` como god node) coincide con el análisis de intermediación de Graphify.
- [`../reverse-sdd/`](../reverse-sdd/) — documentación reconstruida. El hallazgo P2-1 (cobertura
  sin umbral) se apoya en el caso histórico de `prune()` documentado en su HU-016; el P3-1
  (duplicación FDSN) corresponde a la abstracción que ADR-016 difirió deliberadamente.
