# ADR-003 — Hacer ejecutables las fronteras entre paquetes con import-linter

**Estado:** propuesto · **Fecha:** 2026-09-06 · **Debilidad:** P2-2
**Atributos:** acoplamiento y fronteras

## Contexto

La arquitectura por capas de este proyecto **funciona hoy**, y la evidencia es fuerte:

- `[METRIC: analysis/file_level_graph.txt → 0 ciclos entre 40 módulos y 97 aristas]`
- `[METRIC: arch_signals → ningún par de co-cambio entre dos archivos de producción de módulos
  distintos en 47 commits]`
- `[TOOL: docs/code-audit/analysis/solid-signals.txt § DIP]` — el dominio (`models`, `pipeline`, `geo`, `timeutil`) no
  importa infraestructura

Pero nada la **obliga**. No hay import-linter, ni regla de ruff equivalente, ni test de
arquitectura `[GAP: búsqueda en pyproject.toml, .pre-commit-config.yaml y .github/workflows/]`.
La disciplina se sostiene sobre la convención y sobre tener un único autor
`[METRIC: arch_signals.json.bus_factor_by_module → 15/15 módulos al 100 % de un autor]`.

Este es el momento barato de fijarla: **cuesta casi nada escribir las reglas cuando el código ya
las cumple**. Escribirlas después de la primera violación cuesta la violación más las reglas.

## Decisión

Añadir `import-linter` como dependencia del extra `dev` y declarar cuatro contratos en
`pyproject.toml`:

1. **Capas** (`type = layers`), de más abstracto a más concreto:
   `notify` y `tui` → `pipeline` → `ingest` → núcleo (`models`, `config`, `state`, `geo`,
   `timeutil`, `backoff`, `i18n`). Un import en sentido contrario falla.
2. **Núcleo independiente** (`type = forbidden`): `models`, `geo` y `timeutil` no pueden importar
   `httpx`, `websockets`, `tkinter`, `pystray`, `textual` ni ningún módulo de `vigia_eew.ingest`,
   `vigia_eew.notify` o `vigia_eew.tui`.
3. **`app` es sumidero** (`type = forbidden`): ningún módulo salvo `vigia_eew.cli` puede importar
   `vigia_eew.app`. Fija hoy lo que el grafo ya muestra `[METRIC: analysis/file_level_graph.txt → fan-in de app.py = 1, solo desde cli.py]` y protege
   el corte de ADR-001.
4. **Ingestores independientes entre sí** (`type = independence`): `ws_emsc`, `rest_usgs`,
   `rest_geofon` y `rest_funvisis` no se importan mutuamente. Añadir una quinta fuente no puede
   acoplarla a una existente.

Se ejecuta con `lint-imports` en el hook de pre-commit (es rápido, sin red) y en `ci.yml`.

## Alternativas consideradas

**(a) No hacer nada.** El argumento serio: con un solo mantenedor y 40 módulos que caben en la
cabeza, una herramienta que verifica lo que ya se cumple es ceremonia. El coste real de una
violación futura sería detectarla en revisión, y con un solo autor la revisión es el propio autor.
Es una postura defendible **hoy**. Se descarta porque el `05-PLAN-RECONSTRUCCION.md` contempla una
v2 y porque el bus factor 1 es precisamente el escenario en el que las reglas escritas valen más:
sustituyen al conocimiento que no está distribuido.

**(b) Test de arquitectura en pytest** (recorrer los imports con `ast` y afirmar sobre el grafo).
Sin dependencia nueva y totalmente bajo control. Es una alternativa razonable, pero significa
mantener ~80 líneas de código de análisis que import-linter ya resuelve, con peores mensajes de
error. **Rechazada** por relación coste/beneficio, no por principio.

**(c) Reestructurar los paquetes primero** (crear `core/`, mover el núcleo estable fuera del
paquete raíz) y luego fijar las reglas. Eliminaría de raíz el falso positivo del ciclo a nivel de
directorio y haría la estructura autoexplicativa. Es la opción más limpia y **la más cara**: mueve
19 archivos, rompe todo import externo y contradice la regla de "no partir sin costura probada".
**Rechazada por ahora**; reconsiderar si ADR-001 se ejecuta y el resultado sugiere el corte.

## Consecuencias

**Positivas:** las fronteras pasan de convención a contrato verificable. Un contribuidor externo
recibe el error en su primer commit, no en revisión. El contrato 3 protege explícitamente la
inversión de ADR-001. El contrato 4 hace barato añadir la quinta fuente.

**Negativas:** una dependencia de desarrollo más y ~30 líneas de configuración. Cuando una regla
estorbe legítimamente habrá que negociar con ella (import-linter permite excepciones, pero cada
excepción es deuda visible — que es justamente el efecto buscado).

**Riesgo de este ADR:** que las reglas se escriban demasiado estrictas y se acaben desactivando.
Mitigación: los cuatro contratos se derivan del grafo **actual**, así que pasan en verde desde el
primer día. Si alguno falla al instalarlo, la regla está mal escrita, no el código.

## Coste y reversibilidad

**Coste:** S (≈1 h, la mayor parte redactando los contratos).
**Reversibilidad: total.** Borrar la sección de `pyproject.toml` y el hook.
**Verificación:** `lint-imports` en verde sobre el código actual sin modificar una sola línea de
`src/`. Prueba negativa obligatoria: añadir temporalmente `from vigia_eew.notify import queue` en
`src/vigia_eew/models.py` y comprobar que **falla**; si pasa, los contratos no muerden.
