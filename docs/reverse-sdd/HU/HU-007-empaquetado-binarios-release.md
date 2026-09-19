# HU-007: Instalar el agente sin saber Python

> **Cluster de origen:** C-09 · **Commits:** 5 `[COMMITS: b6413e3, 7b1c71c, c38d9f6, bdc2a9d, a02607f]`
> **Período:** 2026-07-03 → 2026-07-04 · **Era:** v0.1.0 → v0.1.3

## Historia

**Como** usuario final sin entorno de desarrollo
**Quiero** descargar un ejecutable para mi sistema operativo, o instalarlo con pip
**Para** usar el agente sin instalar Python ni gestionar dependencias

## Contexto de la implementación original

484 líneas: spec de PyInstaller `[VERIFY: packaging/vigia-eew.spec:1]`, tres scripts de build
`[VERIFY: packaging/build_linux.sh:1]`, `[VERIFY: packaging/build_macos.sh:1]`,
`[VERIFY: packaging/build_windows.ps1:1]`, entrypoint congelado
`[VERIFY: packaging/entrypoint.py:1]` y el workflow de release
`[VERIFY: .github/workflows/build.yml:1]`. Los cuatro commits posteriores son correcciones de
empaquetado, no de producto — este cluster concentra la mayor densidad de fixes del repositorio.

## Criterios de aceptación

### CA-007.1: El paquete se publica en PyPI y expone un comando
```gherkin
Dado un tag de versión vX.Y.Z
Cuando se ejecuta el workflow de release
Entonces se construye el wheel con hatchling y se publica en PyPI
Y el paquete instalado expone el comando vigia-eew
```
*Fuente: código `[VERIFY: pyproject.toml:52]`, `[VERIFY: .github/workflows/build.yml:1]`; fix `[COMMITS: f51da9c]` — el token de PyPI solo resolvía atado al environment*

### CA-007.2: Los recursos de terceros viajan dentro del binario
```gherkin
Dado un binario congelado con PyInstaller
Cuando el agente envía un toast
Entonces los recursos de desktop_notifier están disponibles dentro del binario
```
*Fuente: fix `[COMMITS: bdc2a9d]` — `desktop_notifier.resources` faltaba en el binario y el toast fallaba en tiempo de ejecución*

### CA-007.3: Los assets de empaquetado son válidos para la herramienta de build
```gherkin
Dado un ícono de aplicación usado por el empaquetador
Cuando se construye el AppImage en Linux
Entonces el ícono tiene un formato y una resolución que linuxdeploy acepta
Y el build no se interrumpe
```
*Fuente: fixes `[COMMITS: 7b1c71c]` y `[COMMITS: c38d9f6]` — un ícono placeholder de resolución inválida rompió dos releases consecutivas (v0.1.1 y v0.1.2). **Sin test automatizado hoy**.*

### CA-007.4: El binario onefile no contamina los subprocesos del sistema
```gherkin
Dado el agente corriendo como binario onefile
Cuando lanza un reproductor de sonido o un editor del sistema
Entonces esos procesos reciben un entorno sin las librerías empaquetadas
```
*Fuente: fix `[COMMITS: a02607f]`; tests `[VERIFY: tests/test_subprocess_env.py:23]`*

### CA-007.5: El binario congelado arranca por su propio entrypoint
```gherkin
Dado el ejecutable congelado
Cuando se invoca
Entonces delega en el CLI del paquete y acepta los mismos flags
```
*Fuente: código `[VERIFY: packaging/entrypoint.py:1]`, `[VERIFY: src/vigia_eew/cli.py:56]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-007.1 | CA-007.1 | feliz | tag de release | `v0.6.0` | wheel publicado | No — escribir smoke de publicación en v2 |
| TC-007.2 | CA-007.1 | borde | instalación desde PyPI | `pip install` | comando disponible | No — escribir test de instalación en v2 |
| TC-007.3 | CA-007.2 | negativo | toast desde binario | ejecutable congelado | recursos presentes | No — escribir smoke de binario en v2 |
| TC-007.4 | CA-007.3 | negativo | ícono inválido | PNG mal dimensionado | **el build debe fallar rápido con mensaje claro** | No — **hueco P1**, causó 2 releases rotas |
| TC-007.5 | CA-007.4 | negativo | subproceso desde onefile | `LD_LIBRARY_PATH` empaquetado | env saneado | `[VERIFY: tests/test_subprocess_env.py:23]` |
| TC-007.6 | CA-007.4 | borde | macOS | `DYLD_LIBRARY_PATH` | eliminado | `[VERIFY: tests/test_subprocess_env.py:42]` |
| TC-007.7 | CA-007.5 | feliz | ejecutable con `--simulate` | flag | alerta simulada | No — escribir e2e de binario en v2 |

## Dependencias

- **Requiere**: HU-005, HU-006
- **Habilita**: distribución de todas las demás HUs

## Notas para la v2

Este es el cluster **peor cubierto por tests** del proyecto: cuatro de sus cinco criterios
dependen de artefactos de build que solo se validan al publicar. La v2 debe añadir una etapa de CI
que verifique el formato de los assets antes de invocar al empaquetador (CA-007.3) y un smoke test
que ejecute el binario producido con `--simulate` (CA-007.5). Ambas cosas habrían evitado tres de
los cuatro fixes de este cluster.
