# ADR-019: Separar el núcleo compartido de la raíz de composición

> **Estado**: propuesto · **Fecha**: 2026-08-16 · **Debilidad que ataca**: DEB-01 (y DEB-04)
> **Numeración**: continúa la serie de `docs/TECHNICAL-DESIGN.md`, que llega hasta ADR-018.

## Contexto

`src/vigia_eew/` cumple hoy dos roles opuestos dentro del mismo directorio: es el
**núcleo compartido** que los cuatro subpaquetes importan, y es la **raíz de composición**
que importa a esos subpaquetes. `[METRIC: dep_graph → fan-in 6, fan-out 4, 1773 LOC,
único candidato a god-module]`.

La consecuencia visible es que ninguna herramienta de grafos puede expresar la
arquitectura real: el script reporta un ciclo SCC que **no existe** a nivel de archivo
(cero ciclos con Tarjan sobre el AST). La consecuencia práctica es que cada feature nueva
aterriza en `app.py`, hotspot #1 con 11 toques y cobertura del 64 %.

Restricción importante: **la arquitectura funciona**. Absorbió dos fuentes y dos frontends
sin deformarse. Esto no es un rediseño; es hacer que la estructura de directorios diga lo
que el código ya hace.

## Decisión

Mover a `src/vigia_eew/core/` los nueve módulos que los subpaquetes importan, y llevar
`RawMessage` allí también. El resto del paquete raíz queda como composición y frontends.

**La costura, derivada del grafo (no de intuición)** — estos y solo estos módulos raíz son
importados por algún subpaquete:

| Módulo → `core/` | Quién lo importa |
|---|---|
| `models.py` | `notify`×5, `pipeline`×4 |
| `config.py` | `ingest`×4, `pipeline`×3 |
| `state.py` | `ingest`×2, `pipeline/dedup` |
| `timeutil.py` | `ingest`×2, `pipeline/filter` |
| `geo.py` | `pipeline`×2 |
| `i18n.py` | `notify`×4 |
| `agent_state.py` | `ingest/ws_emsc`, `notify/controller` |
| `backoff.py` | `ingest/ws_emsc` |
| `subprocess_env.py` | `autostart`×3, `notify/sound` |
| `RawMessage` (desde `ingest/__init__.py:18`) | `pipeline`×2 — **única razón de la arista `pipeline → ingest`** (DEB-04) |

**Qué NO se toca**: `app.py`, `cli.py`, `simulation.py`, `logging_conf.py`, `geocode.py`,
`geoloc.py`, `tray.py`, `tui.py` se quedan donde están — ningún subpaquete los importa, así
que no son núcleo. Los cuatro subpaquetes (`ingest`, `pipeline`, `notify`, `autostart`)
tampoco cambian de sitio ni de contenido. **No se parte `app.py` en este ADR.**

## Alternativas consideradas

### Alternativa A: mover el núcleo a `core/` (la propuesta)

- **Ventajas**: la dirección de dependencias queda expresada en el árbol de directorios y
  se vuelve verificable por herramienta (habilita ADR-020 con una regla trivial:
  `core` no puede importar nada del paquete). Elimina el falso ciclo y la arista
  `pipeline → ingest`. Es puramente mecánico: mover archivos y actualizar imports.
- **Desventajas**: toca los imports de casi todos los archivos, lo que ensucia el `git
  blame` de una línea por archivo. Cualquier rama abierta entra en conflicto.
- **Costo**: ~medio día, casi todo automatizable con `ruff --fix` tras un renombrado.

### Alternativa B: dejar los archivos donde están y declarar el núcleo solo con una regla de lint

- **Ventajas**: cero movimiento de código, cero conflictos, `git blame` intacto. Se
  obtiene el 80 % del beneficio (la frontera se vuelve verificable) por el 10 % del costo.
- **Desventajas**: la regla tendría que enumerar los nueve módulos por nombre en vez de
  usar el paquete, así que hay que mantenerla a mano cada vez que se añada un módulo al
  núcleo — justo el tipo de disciplina que este ADR intenta eliminar. Y el falso ciclo del
  grafo persiste, con lo que la próxima auditoría vuelve a tropezar con él.
- **Costo**: ~1 hora.

### Alternativa C: no hacer nada

- **Qué cuesta convivir con el problema**: hoy, poco. El proyecto tiene un autor, la
  convención se respeta al 100 % y no hay ninguna violación real de dirección de
  dependencias. El costo se paga en dos monedas concretas: `app.py` seguirá acumulando
  cableado (11 toques ya, y cada feature de las eras 2-5 pasó por él), y cada herramienta
  de análisis que se ejecute sobre el repo seguirá reportando un ciclo falso que alguien
  tendrá que volver a descartar a mano.
- **Cuándo sería razonable elegirla**: si el proyecto va a permanecer con un solo autor y
  sin crecer, es una elección perfectamente defendible. El diseño *funciona*; esto es
  legibilidad y enforcement, no corrección. **Si se elige C, adoptar al menos la
  Alternativa B**: sin ninguna regla, la fortaleza #1 del sistema depende de la memoria.

## Consecuencias

- **Positivas**: `[METRIC]` verificable — ciclos SCC reportados 1→0, aristas del grafo
  15→14 (desaparece `pipeline → ingest`), y `src/vigia_eew` deja de ser candidato a
  god-module al repartirse entre `core` (fan-in alto, fan-out 0) y raíz (fan-out alto,
  fan-in bajo), que es la forma sana. Habilita ADR-020 con una regla de dos líneas.
- **Negativas**: un commit grande y ruidoso que toca ~40 archivos por sus imports.
  Conflictos garantizados con cualquier trabajo en curso. El `git blame` de la línea de
  import se pierde (no el del código).
- **Neutrales**: los tests no cambian de contenido, solo de import. La API pública del
  paquete (`vigia_eew.cli:main`) no cambia, así que el entry point y el empaquetado son
  indiferentes.

## Reversibilidad

**Totalmente reversible**: es mover archivos. Un `git revert` del commit deja el árbol
exactamente como estaba. No hay migración de datos, ni de esquema, ni cambio de contrato
externo. Por eso el estándar de evidencia exigible es bajo — y aun así se cumple, porque
la costura salió del grafo y no de una opinión.

## Guardas anti-sobreingeniería

- [x] **No introduce una capa/abstracción "por flexibilidad"**: no crea interfaces,
      protocolos ni indirecciones. Mueve archivos existentes a una carpeta.
- [x] **No extrae ningún servicio**: el proceso sigue siendo uno solo (ADR-008 intacto).
- [x] **Existe una versión más aburrida y se explicó**: la Alternativa B (solo la regla de
      lint). Se descarta porque exige mantener una lista a mano, pero es una elección
      legítima si el equipo prefiere no mover código.
- [x] **Declara qué NO se toca**: `app.py` (explícitamente **no** se parte aquí), `cli.py`,
      los cuatro subpaquetes, los frontends y todo el contenido de los tests.
