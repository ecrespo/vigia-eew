# Matriz de gaps — code-audit Phase 0

**Repo:** `/sessions/busy-eloquent-cray/mnt/vigia-eew`
**Stacks:** python
**Dockerfiles:** 0 · **Lockfiles:** 1 · **pre-commit:** sí

**Tests:** 35 unitarios (heurística) · 0 integración

| Dimensión | ¿Tooling presente? | Herramientas encontradas |
|---|---|---|
| DRY | ❌ | — |
| SOLID | ❌ | — |
| tests_unitarias | ✅ | pytest |
| tests_integracion | ✅ | integration |
| SAST | ✅ | bandit, semgrep |
| SCA | ✅ | pip-audit |
| secretos | ✅ | gitleaks |
| contenedores | ✅ | trivy |

## Detalle de stacks
- **python** en `.` — evidencia: pyproject.toml

> Nota: la matriz detecta *configuración*, no ejecución. Un ✅ significa que la herramienta aparece en pre-commit/CI/configs escaneados; verificar en Phase 1 que realmente corre y bloquea.
