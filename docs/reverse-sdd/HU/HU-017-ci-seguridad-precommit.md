# HU-017: Que ningún cambio rompa el agente sin que nos enteremos

> **Cluster de origen:** C-19 · **Commits:** 6 `[COMMITS: 97b2a8e, 5ee3b1d, f51da9c, 27e4b45, 0e707a1, 559f077]`
> **Período:** 2026-07-05 · **Era:** v0.3.0 → v0.4.1

## Historia

**Como** mantenedor del proyecto
**Quiero** que cada cambio pase automáticamente lint, tipado, pruebas y análisis de seguridad antes de integrarse
**Para** no publicar una versión rota de una herramienta de la que alguien depende para su seguridad física

## Contexto de la implementación original

Seis commits, todos del 5 de julio, que instalan la red de seguridad de proceso: workflows de CI y
seguridad más hooks de pre-commit `[COMMITS: 97b2a8e]`, publicación a PyPI
`[COMMITS: 5ee3b1d, f51da9c]` y tres iteraciones sobre el entorno del runner
`[COMMITS: 0e707a1, 27e4b45, 559f077]`.

`ci.yml` `[VERIFY: .github/workflows/ci.yml:27]` corre lint, tipado y pruebas con cobertura;
`security.yml` añade bandit, pip-audit, gitleaks, semgrep y trivy;
`.pre-commit-config.yaml` `[VERIFY: .pre-commit-config.yaml:1]` reparte las comprobaciones rápidas
por commit y las pesadas en pre-push.

## Criterios de aceptación

### CA-017.1: El gate de calidad corre en cada PR
```gherkin
Dado un pull request hacia develop
Cuando se ejecuta la CI
Entonces se ejecutan ruff, mypy en modo estricto y pytest con cobertura
Y el PR no puede integrarse si alguno falla
```
*Fuente: código `[VERIFY: .github/workflows/ci.yml:27]`, `[VERIFY: pyproject.toml:93]`*

### CA-017.2: El análisis de seguridad corre antes de publicar
```gherkin
Dado un pull request hacia main
Cuando se ejecuta el workflow de seguridad
Entonces se ejecutan escaneo SAST, auditoría de dependencias, detección de secretos y análisis de contenedores
Y los hallazgos de severidad alta o crítica bloquean
```
*Fuente: código `[VERIFY: .github/workflows/security.yml:1]`; fix `[COMMITS: 559f077]` — la CI no corría en PRs a main hasta ese commit*

### CA-017.3: El runner dispone de las dependencias del sistema que el agente necesita
```gherkin
Dado un runner de CI
Cuando se prepara el entorno de Python
Entonces tkinter está disponible
Y el paquete se importa correctamente sin display
```
*Fuente: fixes `[COMMITS: 0e707a1]` — hubo que usar Python gestionado por uv para tener tkinter; `[COMMITS: 651c024]` — el agente no era import-safe en host headless. Test `[VERIFY: tests/test_tray.py:139]`*

### CA-017.4: La caché de dependencias es válida
```gherkin
Dado que uv.lock no está versionado
Cuando la CI calcula la clave de caché
Entonces la deriva de pyproject.toml y no del lockfile ausente
```
*Fuente: fix `[COMMITS: 27e4b45]`*

### CA-017.5: La publicación a PyPI resuelve sus credenciales
```gherkin
Dado un job de publicación a PyPI
Cuando se ejecuta
Entonces está asociado al environment que expone el token
Y solo se ejecuta después de que todos los paquetes se hayan construido
```
*Fuente: fixes `[COMMITS: f51da9c]`, `[COMMITS: 5ee3b1d]`*

### CA-017.6: Las mismas comprobaciones se pueden ejecutar localmente
```gherkin
Dado un desarrollador con los hooks instalados
Cuando hace commit
Entonces se ejecutan las comprobaciones rápidas
Y las pesadas se ejecutan antes de hacer push
```
*Fuente: código `[VERIFY: .pre-commit-config.yaml:1]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-017.1 | CA-017.1 | feliz | PR limpio | código válido | los 3 jobs en verde | `[VERIFY: .github/workflows/ci.yml:27]` (verificado por la propia CI) |
| TC-017.2 | CA-017.1 | negativo | error de tipado | anotación incorrecta | mypy falla, PR bloqueado | idem |
| TC-017.3 | CA-017.2 | negativo | dependencia con CVE alta | paquete vulnerable | pip-audit/trivy bloquean | `[VERIFY: .github/workflows/security.yml:1]` |
| TC-017.4 | CA-017.2 | negativo | secreto en el diff | token en claro | gitleaks bloquea | idem |
| TC-017.5 | CA-017.3 | negativo | runner sin tkinter | Python del sistema | debe fallar rápido y claro | No — escribir job de verificación de entorno en v2 |
| TC-017.6 | CA-017.4 | borde | caché sin lockfile | `uv.lock` ausente | clave por `pyproject.toml` | No — verificado manualmente |
| TC-017.7 | CA-017.5 | feliz | tag de release | `vX.Y.Z` | publicación exitosa | No — escribir dry-run de publicación en v2 |

## Dependencias

- **Requiere**: HU-005 (existe un paquete que probar), HU-007 (existe algo que publicar)
- **Habilita**: mantenimiento seguro de todas las demás HUs

## Notas para la v2

Dos cambios concretos: **versionar `uv.lock`** — su ausencia obligó al workaround de caché
(CA-017.4) y hoy hay saltos de versión mayores entre los rangos declarados y las versiones
resueltas (ver `02-STACK-TECNOLOGICO.md` §7) — y **añadir un chequeo de código inalcanzable** al
gate, que habría detectado el `prune()` sin llamadas de HU-016 el primer día.
