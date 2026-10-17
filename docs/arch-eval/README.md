# Evaluación de arquitectura — vigia-eew

Diagnóstico arquitectónico con evidencia determinista, sobre el commit `c3a2c29` (2026-09-06).

| Archivo | Contenido |
|---|---|
| [01-INFORME-EVALUACION.md](01-INFORME-EVALUACION.md) | Scorecard de 8 atributos, 7 fortalezas, debilidades P1–P3 y **5 hallazgos de las herramientas descartados** con su verificación |
| [adr/ADR-001](adr/ADR-001-extraer-cableado-de-application.md) | Extraer el cableado de `Application` (cierra P1-1 y P2-4) |
| [adr/ADR-002](adr/ADR-002-sincronizar-estado-compartido-de-application.md) | Sincronizar el estado compartido entre hilos (cierra P2-1) |
| [adr/ADR-003](adr/ADR-003-fronteras-ejecutables-con-import-linter.md) | Fronteras ejecutables con import-linter (cierra P2-2) |
| [02-PLAN-MIGRACION.md](02-PLAN-MIGRACION.md) | 5 fases con métrica de "Done" y rollback, más las fases **descartadas** |
| `analysis/` | `dep_graph.{json,md}`, `arch_signals.{json,md}` y `file_level_graph.txt` |

## Scorecard

| Atributo | Peso | | Atributo | Peso | |
|---|---|---|---|---|---|
| 1 · Acoplamiento y fronteras | alto | 🟡 | 5 · Datos y consistencia | bajo | 🟡 |
| 2 · Cohesión y responsabilidad | alto | 🟡 | 6 · Observabilidad | medio | 🟡 |
| 3 · Testabilidad | alto | 🟢 | 7 · Seguridad | bajo | 🟢 |
| 4 · Resiliencia | **crítico** | 🟢 | 8 · Evolutividad | **crítico** | 🔴 |

## Los dos hallazgos que importan

**P1-1 · `app.py` es raíz de composición y god-module a la vez.** Importa **25 de los 40 módulos**
del sistema (62,5 %); el segundo mayor fan-out es 5. Arrastra a `config.py` (7 co-cambios,
confianza 0,70) y a `cli.py` (6, 0,67): las siete features posteriores a la v0.1.0 lo tocaron.
No es un problema de tamaño — es que **es la única costura por la que entra toda feature nueva**.

**P2-1 · Estado compartido entre hilos sin sincronizar.** `Application._loop` y `._sup` se escriben
desde el hilo de asyncio y se leen desde el de Tk sin lock. Si el usuario sale antes de que el
trabajador termine de asignarlos, `request_stop()` no se invoca y el apagado no es limpio. El
mismo proyecto **ya resuelve esto bien** en `AgentState`, con `threading.Lock`.

## Lo que las herramientas dijeron y no era cierto

El script `dep_graph.py` reporta **1 ciclo de dependencias marcado "evidencia P1"**. Verificado en
Fase 1 con un análisis a nivel de archivo sobre los mismos 40 módulos: **0 ciclos**. El SCC es un
artefacto de agrupar por directorio — los subpaquetes importan *hacia arriba* al núcleo estable
(`models`, `config`, `state`, que viven en el paquete raíz) y `app.py`, que también vive ahí,
importa *hacia abajo*. Ningún archivo participa en un ciclo.

Igualmente descartados: el "god-module" `src/vigia_eew` (reformulado con la métrica correcta),
los 15 pares de co-cambio "entre módulos" (todos son fuente↔su test o doc↔doc) y el hotspot #1
`CHANGELOG.md`. El informe los documenta uno a uno para que la próxima auditoría no los relitigue.

## Balance del plan

De las 5 fases, **tres retiran complejidad** (`app.py` 450→~200 líneas, escalera→registro,
carrera→invariante explícita), una añade una dependencia de desarrollo (import-linter) y una añade
un campo de correlación. **No se propone ninguna capa, servicio ni tecnología nueva en runtime**;
cinco propuestas alternativas —incluida la reestructuración en `core/`+`adapters/`— están
explícitamente descartadas con su razón.

## Relación con el resto de `docs/`

- [`../code-audit/`](../code-audit/) — coincide en `Application` (allí P3-2 por tamaño, aquí P1-1
  por acoplamiento) y en la duplicación FDSN. Ninguno contradice al otro.
- [`../reverse-sdd/`](../reverse-sdd/) — su Fase 5 ya anticipaba "un registro declarativo de fuentes
  y flags"; ADR-001 le aporta la costura concreta y la métrica. §Conciliación del plan reparte qué
  entra aquí como cambio incremental y qué se difiere a la v2.
- [`../CONTEXT_REPORT.md`](../CONTEXT_REPORT.md) — Graphify sitúa `Application` como segundo nodo de
  mayor intermediación (0,136), corroborando P1-1 desde el grafo semántico.
