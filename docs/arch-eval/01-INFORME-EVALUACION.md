# Evaluación de arquitectura — Vigía-eew

> Commit de referencia: `8660eea` · Fecha: 2026-08-16
> Evidencia: `analysis/dep_graph.json`, `analysis/arch_signals.json`
> **Alcance**: 79 archivos Python en 7 módulos + 49 commits de historia. Se reutilizan
> los hotspots ya derivados en `docs/reverse-sdd/analysis/history.json` y los resultados
> de herramienta de `docs/code-audit/analysis/` en vez de re-derivarlos.

## Resumen ejecutivo

**La arquitectura es sana y la recomendación de fondo es evolucionar in situ, no
reconstruir.** El diseño se validó en la práctica: nació completo y absorbió dos fuentes
sísmicas nuevas, dos frontends y tres filtros sin cambiar de forma.

El único hallazgo P1 que los scripts señalaron —un ciclo de dependencias— **es un falso
positivo** de la agregación por directorio: a nivel de archivo hay **cero ciclos**
(verificado con un Tarjan propio y corroborado por Graphify). Lo dejo documentado en
"Hallazgos descartados" para que la próxima auditoría no lo vuelva a litigar.

Las tres debilidades que sí importan son de *frontera*, no de estructura:

1. El paquete raíz mezcla dos roles distintos —núcleo compartido y raíz de composición—
   y esa ambigüedad es exactamente lo que hace fallar la métrica y lo que convierte a
   `app.py` en el hotspot #1.
2. Las fronteras entre capas existen y se respetan, pero **nada las obliga**: no hay
   import-linter ni equivalente. Hoy se cumplen por disciplina de un solo autor.
3. Añadir una clave de configuración cuesta tocar **hasta 6 archivos**, y el historial
   lo confirma con pares de co-cambio.

Ninguna requiere rediseño. Las tres se resuelven con cambios contenidos y reversibles.

## Scorecard de atributos

| Atributo | Veredicto | Evidencia clave |
|---|---|---|
| Acoplamiento y fronteras | 🟡 | `[METRIC: dep_graph → 0 ciclos a nivel de archivo]`, pero `[VERIFY: sin import-linter en pyproject.toml]`: las fronteras son convención, no regla. Dirección de dependencias correcta: el dominio no importa infraestructura |
| Cohesión y responsabilidad | 🟡 | `[METRIC: src/vigia_eew fan-in 6, fan-out 4, 1773 LOC]` — el paquete raíz cumple dos roles (núcleo + composición). Los subpaquetes sí tienen una sola razón de cambio |
| Testabilidad | 🟢 | `[METRIC: 345 tests, 89 % cobertura con branch]`. Inyección de dependencias sistemática `[VERIFY: src/vigia_eew/pipeline/filter.py:37]`; los módulos de mayor fan-in tienen test propio |
| Resiliencia e integraciones | 🟢 | Las 4 integraciones con timeout explícito `[VERIFY: src/vigia_eew/ingest/rest_usgs.py:103]`, backoff con jitter `[VERIFY: src/vigia_eew/backoff.py:18]`, supervisor que reinicia hijos `[VERIFY: src/vigia_eew/supervisor.py:80]`, y `Retry-After` honrado |
| Datos y consistencia | 🟢 | Escritura atómica `[VERIFY: src/vigia_eew/state.py:33]`; zonas horarias explícitas y validadas en el modelo `[VERIFY: src/vigia_eew/models.py:25]`; idempotencia real vía dedup por id + firma `[VERIFY: src/vigia_eew/pipeline/dedup.py:45]`. Sin dinero ni transacciones multi-tabla |
| Observabilidad | 🟡 | Logging estructurado clave=valor con UTC `[VERIFY: src/vigia_eew/logging_conf.py:23]` y el id del evento como correlación de facto `[VERIFY: src/vigia_eew/pipeline/processor.py:60]`. Pero el id **no se propaga** a toda la cadena: `normalize` loguea por fuente y el controlador no lo emite |
| Seguridad | 🟢 | `[METRIC: gitleaks → 0 secretos en 48 commits]`, `[METRIC: bandit → 0 MEDIUM/HIGH]`, `[METRIC: pip-audit → 0 CVEs]`. Sin authN/authZ por diseño: no hay superficie servidor |
| Evolutividad y despliegue | 🟡 | CI con gates reales, no decorativo `[VERIFY: .pre-commit-config.yaml:9]`. Dos lastres: `[METRIC: bus factor 100 % en todos los módulos]` y el costo de añadir una clave de config (DEB-03) |

## Fortalezas

Lo que **cualquier refactor o v2 debe preservar**:

1. **Dirección de dependencias correcta y verificada.** Ningún módulo de dominio importa
   infraestructura: `pipeline/` solo importa `config`, `geo`, `models`, `state` y
   `timeutil` `[METRIC: dep_graph → pipeline fan-out 2]`. No hay `httpx`, `websockets`,
   `tkinter` ni `subprocess` dentro de la lógica de negocio. Es la propiedad que hace
   posible el 89 % de cobertura.

2. **Cero ciclos reales.** `[METRIC: análisis Tarjan a nivel de módulo Python → ninguno]`,
   corroborado independientemente por `graphify-out/GRAPH_REPORT.md` ("Import Cycles:
   None detected"). En un proyecto con 4 integraciones y 2 frontends, eso no es casual.

3. **Costuras selladas por inyección, no por herencia.** `connect`, `sleep`, `client`,
   `runner`, `create_window`, `now` se pasan al constructor
   `[VERIFY: src/vigia_eew/ingest/rest_usgs.py:45]`. Es lo que permite testear reconexión,
   backoff y "hoy" sin red ni reloj real, y es una decisión de arquitectura, no un detalle.

4. **Resiliencia diseñada, no improvisada.** El patrón "supervisor que reinicia hijos"
   `[VERIFY: src/vigia_eew/supervisor.py:80]` más aislamiento de fallos en cada efecto
   opcional `[VERIFY: src/vigia_eew/notify/toast.py:40]` significa que ninguna caída
   parcial tumba el proceso. Para un agente de seguridad que corre semanas desatendido, es
   el atributo correcto a priorizar.

5. **La arquitectura ya demostró que absorbe cambio.** FUNVISIS `[COMMITS: 10bb72d]` y
   GEOFON `[COMMITS: ade1199]` entraron añadiendo un ingestor y un `_map_*`, sin tocar
   filtro, dedup ni presentación. La heurística de dedup no cambió porque ya era agnóstica
   al número de fuentes. Eso es un test empírico de la modularidad.

## Debilidades (rankeadas)

| ID | Sev. | Debilidad | Atributo | Módulos (fan-in) | Evidencia | Propuesta |
|---|---|---|---|---|---|---|
| DEB-01 | P2 | El paquete raíz mezcla núcleo compartido y raíz de composición | Cohesión | `src/vigia_eew` (6) | `[METRIC + VERIFY]` | ADR-019 |
| DEB-02 | P2 | Las fronteras no están obligadas por ninguna regla | Acoplamiento | todos | `[VERIFY: ausencia]` | ADR-020 |
| DEB-03 | P2 | El esquema de configuración está duplicado en hasta 6 artefactos | Evolutividad | `config` (hotspot #3) | `[METRIC + VERIFY]` | ADR-021 |
| DEB-04 | P3 | `pipeline` depende de `ingest` solo por un tipo de dato | Acoplamiento | `pipeline` (2) | `[VERIFY]` | ADR-019 (misma costura) |
| DEB-05 | P3 | El id del evento no se propaga como correlación en toda la cadena | Observabilidad | `pipeline`, `notify` | `[VERIFY]` | riesgo aceptado |
| DEB-06 | P3 | Bus factor 100 % en todos los módulos | Evolutividad | todos | `[METRIC]` | riesgo aceptado |

---

### DEB-01: El paquete raíz cumple dos roles incompatibles

- **Qué pasa**: `src/vigia_eew/` contiene a la vez el **núcleo compartido** que todos los
  subpaquetes importan (`models`, `config`, `geo`, `state`, `timeutil`, `i18n`, `backoff`,
  `agent_state`, `subprocess_env`) y la **raíz de composición** que importa a los
  subpaquetes (`app.py`, `cli.py`). Son direcciones opuestas dentro del mismo directorio.
- **Evidencia**: `[METRIC: dep_graph → src/vigia_eew fan-in 6, fan-out 4, 1773 LOC,
  score 24 — el único candidato a god-module]`. Verificado a nivel de archivo: 17 módulos
  hijos importan del raíz `[VERIFY: src/vigia_eew/pipeline/dedup.py:25]`, mientras el raíz
  importa hijos `[VERIFY: src/vigia_eew/app.py:31]`. Es también la causa del falso ciclo
  (ver descartados).
- **Por qué importa**: degrada cohesión y hace que **ninguna herramienta de grafos pueda
  expresar la arquitectura real**. En la práctica se manifiesta en `app.py`: hotspot #1 de
  código `[METRIC: 11 toques, churn 879]`, 451 líneas y la segunda cobertura más baja del
  repo (64 %).
- **Qué pasa si no se hace nada**: no se rompe nada. El costo es que cada feature nueva
  sigue aterrizando en `app.py` y que la separación núcleo/composición vive solo en la
  cabeza de quien la escribió. Con un solo autor es sostenible; con dos, no.
- **Propuesta**: ADR-019.

### DEB-02: Las fronteras se respetan por disciplina, no por regla

- **Qué pasa**: la dirección de dependencias es correcta hoy, pero **nada impide** que
  mañana `models.py` importe `httpx` o que `pipeline/` importe `tkinter`.
- **Evidencia**: `[VERIFY: pyproject.toml]` y `[VERIFY: .pre-commit-config.yaml]` — sin
  `import-linter`, `dependency-cruiser` ni equivalente. El gate corre ruff, mypy, bandit,
  pytest, pip-audit, semgrep y trivy; ninguno mira la dirección de los imports.
- **Por qué importa**: es la fortaleza #1 del sistema y no tiene red de seguridad. Una
  regresión aquí no la detecta ningún test: el código seguiría pasando los 345 tests
  mientras la testabilidad se degrada en silencio.
- **Qué pasa si no se hace nada**: probablemente nada mientras el autor sea uno. El riesgo
  se materializa justo cuando el proyecto crece — el momento en que menos se quiere
  descubrir que la arquitectura ya se erosionó.
- **Propuesta**: ADR-020. Es el cambio más barato y de mayor retorno del informe.

### DEB-03: Añadir una clave de configuración cuesta tocar hasta 6 archivos

- **Qué pasa**: cada clave existe en `config.py` (modelo pydantic), en
  `config.toml.example` (plantilla que se siembra), y descrita en hasta cuatro documentos.
- **Evidencia**: `[VERIFY]` verificado clave por clave — `today_only` y `timezone`
  aparecen en 6 artefactos (`config.py`, `config.toml.example`, `PRD.md`,
  `TECHNICAL-DESIGN.md`, `DATA-MODEL.md`, `IMPLEMENTATION-PLAN.md`); `country_filter` en 6.
  El historial lo confirma: `[METRIC: arch_signals → config.toml.example ↔
  IMPLEMENTATION-PLAN.md 3 co-cambios (0.6); ↔ PRD.md 3 (0.6); ↔ TECHNICAL-DESIGN.md 3
  (0.6)]` y `config.py` es hotspot #3 `[METRIC: 10 toques, churn 505]`.
- **Por qué importa**: es el costo real de la feature típica de este producto — casi todas
  las features de las eras 3 a 5 añadieron configuración. Seis sitios es donde la
  documentación empieza a mentir.
- **Qué pasa si no se hace nada**: la divergencia ya empezó. `radius_km` y `min_magnitude`
  **no** están en `PRD.md` aunque sí en `DATA-MODEL.md` y `README.md`; `language` no está
  en `TECHNICAL-DESIGN.md`. No es grave todavía porque el autor mantiene los seis a mano.
- **Propuesta**: ADR-021.

### DEB-04: `pipeline` depende de `ingest` solo para un tipo de dato

- **Qué pasa**: `pipeline/normalize.py` y `pipeline/processor.py` importan de `ingest`
  **exclusivamente** `RawMessage`; ningún otro símbolo.
- **Evidencia**: `[VERIFY: src/vigia_eew/pipeline/normalize.py:34]`,
  `[VERIFY: src/vigia_eew/pipeline/processor.py:23]` — ambos `from vigia_eew.ingest import
  RawMessage` y nada más. `[METRIC: dep_graph → arista pipeline → ingest]`.
- **Por qué importa**: es una arista de acoplamiento que **existe solo por la ubicación de
  una clase**, no por una dependencia real. `RawMessage` es un contrato compartido
  `[VERIFY: src/vigia_eew/ingest/__init__.py:18]`, no una pieza de ingestión.
- **Qué pasa si no se hace nada**: nada funcional. Es ruido en el grafo.
- **Propuesta**: ADR-019 — misma costura, coste marginal cero.

### DEB-05: El id del evento no atraviesa toda la cadena de logs

- **Qué pasa**: `ev.id` funciona como correlación de facto, pero solo en algunos puntos.
  `processor` lo emite al filtrar `[VERIFY: src/vigia_eew/pipeline/processor.py:60]` y
  `dedup` al deduplicar `[VERIFY: src/vigia_eew/pipeline/dedup.py:52]`; en cambio
  `normalize` loguea por fuente sin id `[VERIFY: src/vigia_eew/pipeline/normalize.py:64]`
  y el controlador de alertas no lo emite al presentar.
- **Por qué importa**: la pregunta operativa real de este sistema es "¿por qué no me
  avisó del sismo X?", y hoy no se responde solo con los logs de punta a punta.
- **Qué pasa si no se hace nada**: el diagnóstico sigue requiriendo leer código. El
  historial ya muestra un caso: la investigación de "solo alerta FUNVISIS" que destapó dos
  defectos distintos `[COMMITS: b0f832c]`.
- **Propuesta**: **riesgo aceptado por ahora.** Es un ajuste de líneas de log, no de
  arquitectura; entra mejor como tarea del backlog de observabilidad que como ADR. Se
  registra aquí para que no se pierda.

### DEB-06: Bus factor 100 % en todos los módulos

- **Qué pasa**: un único autor concentra el 100 % de los commits en los ocho módulos de
  producto.
- **Evidencia**: `[METRIC: arch_signals → bus_factor: tests 100 %, docs 100 %, packaging
  100 %, workflows 100 %, autostart 100 %, assets 100 %]`.
- **Por qué importa**: es riesgo organizacional, no técnico.
- **Qué pasa si no se hace nada**: en un proyecto personal, nada. Si el proyecto busca
  contribuciones, la mitigación ya está construida y es inusualmente buena: 18 ADRs y un
  kit SDD completo que documentan el *porqué*, ambos versionados.
- **Matiz posterior**: la capa de intención (`lat.md/`) **no se versiona** por decisión
  del autor, así que no cuenta como mitigación compartida: un contribuidor nuevo recibe
  los ADRs y el kit SDD, pero no el índice consultable que los resume. Los comentarios
  `# @lat:` del código sí viajan y siguen señalando qué decisión gobierna cada sitio.
- **Propuesta**: **riesgo aceptado.** Proponer "más autores" no es una decisión de
  arquitectura. Lo accionable ya está hecho.

## Hallazgos descartados

| Reporte del script | Razón del descarte |
|---|---|
| **🔴 Ciclo SCC** `src/vigia_eew` ↔ `autostart` ↔ `ingest` ↔ `notify` ↔ `pipeline`, y los 4 pares mutuos | **Falso positivo por agregación de directorio.** El script agrupa por carpeta, y la carpeta raíz contiene tanto el núcleo (que los hijos importan) como la composición (que importa a los hijos). A nivel de módulo Python hay **cero ciclos**, verificado con Tarjan sobre el AST y corroborado por `graphify-out/GRAPH_REPORT.md`. Lo que el ciclo señala de verdad es DEB-01, y por eso esa debilidad existe — pero como P2 de cohesión, no como P1 de acoplamiento |
| `src/vigia_eew` como god-module (score 24) | **Parcialmente descartado.** No es un god-module por responsabilidad: son 19 archivos pequeños y cohesivos con una interfaz mínima, no un archivo monolítico. El score alto viene de mezclar dos roles → recalificado como DEB-01 |
| Co-cambio `src/vigia_eew/cli.py` ↔ `tests/test_cli.py` (0.71), `app.py` ↔ `test_app.py` (0.56), `config.py` ↔ `test_config.py` (0.56), `alert_window.py` ↔ `test_alert_window.py` (0.75) | **Señal sana, no debilidad.** Que un archivo cambie junto a su propio test es exactamente lo que se quiere. El script los marca como "cruzan módulos" porque `tests/` es otro directorio |
| Co-cambio `README.md` ↔ `IMPLEMENTATION-PLAN.md` (0.67) y los pares entre documentos `docs/` | Coordinación documental de un proyecto SDD, por diseño. `docs/` no es un módulo de software |
| Co-cambio `CHANGELOG.md` ↔ `pyproject.toml` (0.71, 12 veces) y ↔ `build_linux.sh` (1.0) | Es el proceso de release: cada versión toca changelog, versión y empaquetado. Acoplamiento deseado |
| `CHANGELOG.md` como hotspot #1 (score 132) y con 5 fixes | Un changelog se toca en cada release por definición. Los "fixes" son entradas de fixes, no arreglos del changelog |
| `tests` y `packaging` con inestabilidad 1.0 | Correcto por construcción: son hojas del grafo, deben depender de todo y no ser dependidas |

## Áreas no evaluadas

- **Comportamiento en runtime bajo Wayland.** Es el mayor riesgo abierto del producto
  (ADR-010 documentado y nunca implementado), pero es una cuestión de plataforma que no se
  puede evaluar desde el grafo ni desde la historia. Ya está registrada en
  `docs/reverse-sdd/05-PLAN-RECONSTRUCCION.md` §5 y en `02-STACK-TECNOLOGICO.md` RR-3.
- **Rendimiento y consumo en operación prolongada.** No hay telemetría ni benchmarks en el
  repo; evaluarlo requeriría instrumentar una ejecución real de días.
- **Módulos no-Python.** `packaging/*.sh` y `*.ps1` (122 LOC) quedan fuera del grafo de
  dependencias; se cubren por las señales de historia, que sí los ven.
