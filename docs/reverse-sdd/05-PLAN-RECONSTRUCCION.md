# Plan de reconstrucción (v2) — Vigía-eew

> Insumos: `00-INVENTARIO`, `01-ARQUITECTURA`, `02-STACK-TECNOLOGICO`, `03-EVOLUCION`,
> `HU/*`, `04-MATRIZ-PRUEBAS`.
> El orden de fases sigue el grafo de dependencias de las HUs, corrigiendo la cronología
> original donde el historial demostró que estaba mal (ver Fase 1).

## 1. Alcance de la v2

### 1.1 Se reconstruye a paridad (17 HUs)

La arquitectura de este sistema **se validó en la práctica**: nació completa en la Era 0 y
absorbió dos fuentes nuevas, dos frontends y tres filtros sin cambiar de forma. Se
reconstruye tal cual:

HU-001, HU-002, HU-003, HU-005, HU-006, HU-007, HU-008, HU-009, HU-012, HU-013, HU-014,
HU-016, HU-018, HU-019, HU-020, HU-021, HU-022.

Decisiones a preservar **literalmente**, porque son contraintuitivas y están bien
fundamentadas:

- **Block-list, no allow-list**, en el filtro de país (HU-020). Invertirlo suprimiría los
  sismos offshore, que son los más peligrosos de Venezuela.
- **Día local, no UTC**, en el filtro de frescura (HU-009).
- **`--simulate` sin red jamás** (HU-013).
- **Efectos inyectados como callbacks** (HU-012): es lo que permite 348 tests sin I/O real.
- **Filtros fail-safe en una sola dirección**: ante la duda, no suprimir (HU-009, HU-020).
- **Seen-set sembrado sin alertar** en FUNVISIS (HU-021).

### 1.2 Se rediseña (5 HUs)

| HU | Qué se rediseña | Por qué |
|---|---|---|
| **HU-011** Alerta no descartable | **Decidir el frontend antes de escribir código** | Bajo Wayland, Tkinter no puede forzar topmost/focus de forma confiable. ADR-010 propuso D-Bus + extensión GNOME y nunca se implementó. Es el mayor riesgo abierto (RR-3, TC-011.13) |
| **HU-015** Empaquetado | **Mover a la Fase 1 y validar el artefacto en CI** | 4 de los fixes del historial son de artefacto; ninguno lo habría detectado el suite (TC-015.11) |
| **HU-004** Logging | **Escribir sus tests** | Módulo sin cobertura; TC-004.6 (log no escribible) contradice el patrón de aislamiento |
| **HU-006 + HU-022** Pollers FDSN | **Unificar tras un parser parametrizable** | ADR-016 lo difirió "hasta una tercera fuente"; la v2 arranca con dos escritas y estructura idéntica (DT-2) |
| **HU-017** Bandeja | **Validar en macOS o declararlo no soportado** | `pystray` exige hilo principal en Cocoa, lo que choca con Tkinter; nunca se probó en hardware real (RR-4) |

### 1.3 Se descarta

- **Nada del código actual.** No se detectaron features abandonadas o muertas: el único
  código muerto que hubo (`StateStore.prune()`) ya se cableó en `b0f832c`.
- **ADR-010 como plan latente**: o se implementa en la v2 o se retira del diseño. Un ADR
  documentado a fondo y no ejecutado durante 15 releases es deuda documental que sugiere
  una cobertura que no existe.

## 2. Decisiones de stack para la v2

| Área | Stack actual | Stack v2 | Justificación |
|---|---|---|---|
| Lenguaje | Python ≥3.11 | **Python ≥3.12** | 3.11 se eligió por `tomllib`; 3.12 ya es la base de las distros objetivo y da mejor asyncio |
| Dependencias | Rangos `>=` abiertos, **sin lockfile versionado** | Rangos con techo mayor + **`uv.lock` versionado** | RR-1/RR-2: lo resuelto ya divergió mucho de lo declarado (websockets 12→17, textual 0.60→8.2) |
| UI alerta | Tkinter | **Decisión abierta**: Tkinter + puente D-Bus, o TUI como primario | Depende de resolver TC-011.13; no comprometerse antes |
| TUI | Textual | **Textual, promovida a frontend de primera clase** | Mejor relación cobertura/esfuerzo del repo: 13 tests headless en el suite por defecto |
| Bandeja | pystray + Pillow | pystray, **con soporte macOS declarado explícitamente** | RR-4 |
| HTTP / WS | httpx + websockets | Igual | Sin fricción observada en todo el historial |
| Validación | pydantic v2 | Igual | mypy strict pasa sobre 40 módulos con una sola excepción |
| Persistencia | JSON atómico | Igual | Sin base de datos; el volumen no la justifica |
| Geocodificación | Natural Earth 1:110m embebido | Igual, con **1:50m** como opción configurable | El margen de ±decenas de km en frontera es el límite conocido (TC-020.14) |
| Empaquetado | PyInstaller + fpm + linuxdeploy | Igual, **con humo del artefacto en CI** | La lección más cara del historial |
| Idioma del código | Inglés + i18n | **Inglés + i18n desde el commit 1** | La migración tardía fue un breaking change que tocó todo el árbol |

## 3. Fases de construcción

### Fase 0 — Specs y andamiaje
- **HUs**: ninguna (fase de artefactos)
- **Prerequisitos**: este kit
- **Done**: artefactos SDD de §4 aprobados; repo con `uv.lock` versionado, ruff, mypy
  strict, pytest y CI **bajo xvfb** desde el primer commit
- **Riesgos**: reproducir el error de la v1 de dejar el lockfile fuera del control de
  versiones (RR-1)

### Fase 1 — Núcleo de dominio **y empaquetado**
- **HUs**: [HU-001](HU/HU-001-contrato-evento-sismico.md),
  [HU-002](HU/HU-002-estado-persistente.md),
  [HU-003](HU/HU-003-configuracion-validada.md),
  [HU-004](HU/HU-004-logging-estructurado.md),
  [HU-015](HU/HU-015-empaquetado-distribucion.md)
- **Prerequisitos**: Fase 0
- **Done**: TC-001.\*, TC-002.\*, TC-003.\*, TC-004.\* en verde **y** un artefacto
  construido que arranca (TC-015.11)
- **Riesgos**: RR-1, RR-2

> **Esta es la corrección más importante al orden original.** En la v1, el empaquetado fue
> la Fase 8 y produjo tres releases de parche consecutivas. Adelantarlo a la Fase 1
> —aunque el binario todavía no haga nada útil— convierte cuatro fallos de producción en
> fallos de CI del primer día.

### Fase 2 — Ingestión y resiliencia
- **HUs**: [HU-005](HU/HU-005-canal-push-emsc.md),
  [HU-006](HU/HU-006-reconciliacion-usgs.md),
  [HU-007](HU/HU-007-supervision-resiliente.md)
- **Prerequisitos**: Fase 1
- **Done**: TC-005.\*, TC-006.\*, TC-007.\* en verde, incluido TC-007.10 (hueco actual)
- **Riesgos**: RR-7 (contratos externos inestables) — introducir aquí los tests de
  contrato contra respuestas grabadas

### Fase 3 — Pipeline
- **HUs**: [HU-008](HU/HU-008-normalizacion-multifuente.md),
  [HU-009](HU/HU-009-filtrado-radio-magnitud-frescura.md),
  [HU-010](HU/HU-010-deduplicacion.md)
- **Prerequisitos**: Fase 2
- **Done**: TC-008.\*, TC-009.\* (los 4 P1 incluidos), TC-010.\* en verde
- **Riesgos**: la heurística de dedup fusiona sismos distintos en enjambres (TC-010.13);
  evaluar incorporar la profundidad a la firma

> La frescura (HU-009) llegó en la v1 como Fase 15, tras un bug reportado. Aquí entra con
> el pipeline, que es su sitio lógico.

### Fase 4 — Decisión de frontend ⚠️ **puerta de decisión**
- **HUs**: [HU-011](HU/HU-011-alerta-no-descartable.md),
  [HU-012](HU/HU-012-sonido-toast-presentacion.md),
  [HU-019](HU/HU-019-dashboard-tui-headless.md)
- **Prerequisitos**: Fase 3
- **Done**: TC-011.\* y TC-019.\* en verde, **incluido TC-011.13 bajo GNOME/Wayland real**
- **Riesgos**: **RR-3 es bloqueante.** Antes de escribir la UI, correr una prueba de
  concepto de topmost + robo de foco bajo Wayland. Si falla, decidir entre implementar
  ADR-010 (D-Bus + extensión GNOME) o promover la TUI a frontend primario. No avanzar a la
  Fase 5 sin esa decisión tomada y verificada.

### Fase 5 — Ensamblaje y despliegue
- **HUs**: [HU-013](HU/HU-013-cli-y-simulacion.md),
  [HU-014](HU/HU-014-autoarranque-multiplataforma.md),
  [HU-017](HU/HU-017-icono-bandeja.md),
  [HU-018](HU/HU-018-internacionalizacion.md)
- **Prerequisitos**: Fase 4
- **Done**: TC-013.\*, TC-014.\*, TC-017.\*, TC-018.\* en verde; paridad de catálogos
  verificada en CI (TC-018.11)
- **Riesgos**: RR-4 (bandeja en macOS) — resolver aquí, no dejar como best-effort

### Fase 6 — Contexto del usuario y precisión
- **HUs**: [HU-016](HU/HU-016-ubicacion-automatica-ip.md),
  [HU-020](HU/HU-020-filtro-pais.md)
- **Prerequisitos**: Fase 5
- **Done**: TC-016.\*, TC-020.\* en verde
- **Riesgos**: la excepción de privacidad (IP visible a un tercero) debe hacerse explícita
  al usuario en el `config.toml` sembrado

### Fase 7 — Redundancia de fuentes
- **HUs**: [HU-021](HU/HU-021-fuente-funvisis.md),
  [HU-022](HU/HU-022-fuente-geofon.md)
- **Prerequisitos**: Fase 3 (pipeline), Fase 2 (patrón de poller)
- **Done**: TC-021.\*, TC-022.\* en verde, incluidos TC-022.2 y TC-022.16
- **Riesgos**: RR-5 (FUNVISIS sin HTTPS), RR-7 (formato de GEOFON sin contrato versionado)
- **Nota**: aquí se materializa el parser FDSN unificado del §1.2, con GEOFON y USGS como
  sus dos primeras instancias

### Fase 8 — Capas de conocimiento
- **HUs**: ninguna
- **Done**: `.codegraph/`, `graphify-out/` y `lat.md/` instalados, con `lat check` como
  gate de CI
- **Nota**: en este repo se añadieron al final; en la v2 conviene desde la Fase 1, porque
  su valor es acumulativo — la capa de intención se escribe mejor **cuando la decisión se
  toma**, no reconstruida después

## 4. Artefactos SDD pendientes

El skill `spec-driven-design` **está disponible** en este entorno y puede generar los
artefactos usando este kit como insumo. No se han generado en esta ejecución porque no se
solicitaron; la tabla queda como backlog inmediato.

| Artefacto SDD | Insumo desde este kit | Estado |
|---|---|---|
| Constitution | Decisiones a preservar (§1.1) + convenciones del repo actual | Pendiente |
| PRD (con criterios EARS) | Las 22 HUs + `03-EVOLUCION` (contexto y lecciones) | Pendiente |
| API Spec | `01-ARQUITECTURA` §1-3 (integraciones y flujos) + `docs/API-SPEC.md` actual | Pendiente |
| Technical Design | `01-ARQUITECTURA` §5-8 + decisiones de stack (§2) | Pendiente |
| Data Model | `01-ARQUITECTURA` §4 + esquemas citados | Pendiente |
| Implementation Plan | §3 de este documento | Pendiente |
| Tasks | `04-MATRIZ-PRUEBAS` (cada TC es una tarea verificable) | Pendiente |

**Ventaja poco habitual**: el repo actual ya tiene `docs/PRD.md`, `docs/API-SPEC.md`,
`docs/TECHNICAL-DESIGN.md` (18 ADRs), `docs/DATA-MODEL.md` e
`docs/IMPLEMENTATION-PLAN.md`. La v2 no parte de cero: parte de specs existentes
**validados contra el código** por este ejercicio.

## 5. Qué NO sabemos

Lista honesta de lo inferido y lo opaco. La v2 **no debe tratar esto como requisitos
confirmados**.

| Área | Qué no sabemos | Qué lo resolvería |
|---|---|---|
| **Personas/roles** | Las 22 HUs marcan su persona `[INFERIDO]`: los commits describen capacidades, nunca a quién sirven. "Usuario en zona sísmica" es una reconstrucción razonable, no un hecho documentado | Entrevista con el autor o usuarios reales |
| **Comportamiento bajo Wayland** | Si la alerta cumple su promesa en GNOME/Wayland. Ni el código ni los tests ni los ADRs lo responden | Prueba en sesión Wayland real (bloquea la Fase 4) |
| **Comportamiento en macOS** | Bandeja y ventana de alerta nunca se validaron en hardware macOS; los ADRs lo declaran explícitamente | Acceso a una máquina macOS |
| **Umbrales de dedup en campo** | Si 100 km/90 s/0,5 mag acierta durante enjambres reales. Los valores son razonados, no medidos | Telemetría opt-in, o replay contra un catálogo histórico de un enjambre conocido |
| **Estabilidad de FUNVISIS y GEOFON** | Ninguno de los dos publica un contrato versionado; el formato podría cambiar sin aviso | Tests de contrato + monitoreo del ratio de filas descartadas |
| **Uso real de las releases** | No hay tags git en el repo, aunque `build.yml` se dispara con ellos. No se puede saber desde aquí qué se distribuyó realmente | Acceso al remoto y a las estadísticas de PyPI |
| **Por qué el reporte "solo alerta FUNVISIS"** | El commit `b0f832c` menciona el reporte que originó la investigación, pero no su origen ni si el diagnóstico lo resolvió del todo | Issue tracker o el reportante |

**Proporción de inferencia**: por debajo del 5 % de las afirmaciones del kit, concentrada
casi por completo en las personas de las HUs. El resto está anclado a código o a un hash
de commit. Esa cifra tan baja se debe a tres propiedades poco comunes del repo: 97,9 % de
conventional commits, 348 tests que documentan el comportamiento esperado, y 18 ADRs que
ya registraban el *porqué* junto a sus alternativas rechazadas.
