# Kit SDD v1.0 — Vigía-eew

> 2026-09-06 · Commit base: `c3a2c29` (**v0.6.0**) · Destino: **v1.0.0**
> Insumo único de alcance: [`docs/BACKLOG-PRIORIZADO.md`](../BACKLOG-PRIORIZADO.md) rev. 3, 43 ítems.
> Nivel de rigor: **spec-anchored** — estas especificaciones viven en el repositorio, se versionan
> con Git y se actualizan en el mismo cambio que el código (Art. 9).

Esta carpeta es **la guía de implementación**: qué se construye, por qué, en qué orden y con qué
criterio de "hecho". No es un informe de diagnóstico —esos ya existen— sino el plan ejecutable que
sale de ellos.

## Por qué v1 y no v2

El proyecto está en **0.6.0** y **nunca ha publicado una 1.0.0** (`git tag`: v0.3.1 … v0.6.0). Lo
que el backlog describe no es una segunda generación del producto: es **lo que falta para que la
primera esté completa**.

Eso no es una cuestión de etiqueta. Cambia qué significa "terminado":

| Con la etiqueta "v2" | Con la etiqueta correcta, v1.0 |
|---|---|
| Wayland es una mejora para la siguiente generación | Wayland es **la promesa central sin cumplir** en el escritorio Linux más común |
| El gate incompleto es deuda heredada de la v1 | El gate incompleto es **una v1 que aún no se puede declarar estable** |
| Los rangos de dependencias son higiene continua | Son **la garantía de reproducibilidad que un 1.0.0 publica** |

**Criterio de corte de la v1.0.0**, derivado de esa lectura: se publica cuando la alerta cumple su
promesa en los tres escritorios objetivo, el gate mide las ocho dimensiones, y una instalación
limpia resuelve exactamente las mismas versiones que el desarrollador probó. Los tres se traducen
en requisitos verificables en [02-PRD-DELTA.md](02-PRD-DELTA.md).

**A ese criterio se le suman tres capacidades nuevas por decisión del mantenedor**: configuración
gráfica, prioridad de redes e histórico consultable con mapa. Son de otra naturaleza —no cierran
deuda ni una promesa incumplida— y conviene no confundirlas al discutir el alcance: **si hubiera que
recortar para publicar, es por ahí por donde se recorta**. La lista completa de las 10 condiciones
de corte está en [06-IMPLEMENTATION-PLAN §5](06-IMPLEMENTATION-PLAN.md).

> **Nota de consistencia (hallazgo V-01).** Los documentos generados en las etapas anteriores usan
> la etiqueta "v2" en **177 apariciones repartidas en 49 archivos**. Están equivocados por la misma
> razón que lo estaba esta carpeta antes de renombrarse. No se corrigen aquí —es un cambio mecánico
> pero amplio, y hacerlo en silencio dentro de otra tarea es justo lo que la metodología prohíbe—
> sino que queda registrado en [08-ANALYZE.md §V-01](08-ANALYZE.md) con su alcance medido.

## Los artefactos

| # | Artefacto | Qué responde |
|---|---|---|
| 00 | [Enmiendas a la constitución](00-ENMIENDAS-CONSTITUCION.md) | Qué principios cambian, y con qué changelog |
| 01 | [Funcionalidades](01-FUNCIONALIDADES.md) | Los 43 ítems agrupados en 11 épicas, con alcance y no-alcance |
| 02 | [PRD delta (EARS)](02-PRD-DELTA.md) | Los 52 requisitos en alcance, con criterio verificable |
| 03 | [API Spec delta](03-API-SPEC-DELTA.md) | Los tres contratos nuevos: configuración, histórico y teselas |
| 04 | [Technical Design delta](04-TECHNICAL-DESIGN-DELTA.md) | ADR-019 a ADR-027 |
| 05 | [Data Model delta](05-DATA-MODEL-DELTA.md) | La configuración, el esquema del histórico y la caché de teselas |
| 06 | [Implementation Plan](06-IMPLEMENTATION-PLAN.md) | Las 9 fases, su grafo de dependencias y su riesgo |
| 07 | [Tasks](07-TASKS.md) | 49 tareas ejecutables, cada una con REQ y "Done" |
| 08 | [Analyze](08-ANALYZE.md) | La validación cruzada antes de escribir código |
| 09 | [Estimación](09-ESTIMACION.md) | Cuánto cuesta, con sus supuestos y su rango |
| — | [Historias de Usuario](HU/INDICE-HU.md) | 12 HU con 86 criterios Gherkin |

Orden de lectura para implementar: **01 → 02 → 06 → 07**. El resto se consulta cuando una tarea lo
cita.

## Cómo se evita duplicar lo ya escrito

Este kit es un **delta sobre lo que ya está especificado**, no una reescritura. La regla es que cada
hecho vive en un solo sitio y los demás lo enlazan.

| Contenido | Dónde vive | Qué hace este kit |
|---|---|---|
| Los 42 RF de la v0.6.0 | [`docs/PRD.md`](../PRD.md) | Nada: están implementados y verificados |
| Los 56 requisitos EARS y sus criterios | [`docs/sdd/specs/01-PRD.md`](../sdd/specs/01-PRD.md) | Hereda 11 por referencia; añade 41 nuevos |
| Las 17 HU reconstruidas de la v0.6.0 | [`docs/reverse-sdd/HU/`](../reverse-sdd/HU/INDICE-HU.md) | Enlaza; las 12 HU de aquí son capacidades **nuevas** |
| ADR-001 a ADR-018 | [`docs/TECHNICAL-DESIGN.md`](../TECHNICAL-DESIGN.md) | Enmienda dos, añade nueve |
| La evidencia medida de los hallazgos | `docs/code-audit/`, `docs/arch-eval/`, `docs/PAQUETERIA-VERSIONADO.md` | Cita, nunca reproduce |
| La prioridad y el reparto en olas | [`docs/BACKLOG-PRIORIZADO.md`](../BACKLOG-PRIORIZADO.md) | Es el insumo; aquí se convierte en fases y tareas |

**Relación con [`docs/sdd/`](../sdd/README.md), que hay que entender antes de usar cualquiera de los
dos.** Aquel kit especifica el producto **como si se reconstruyera desde cero** —su Fase 0 empieza
por el esqueleto del proyecto y su T-001 crea el `pyproject.toml`. Este kit especifica **el trabajo
sobre el código que ya existe**: parte de `c3a2c29` y solo describe lo que cambia. Son
complementarios y no compiten:

- Para **construir la v1.0 sobre el repositorio actual** → esta carpeta.
- Para **entender qué debería contener el producto completo**, o para rehacerlo en otro lenguaje o
  entorno → `docs/sdd/`.

Los identificadores están separados a propósito para que nunca colisionen: aquí las HU van de
**HU-101** en adelante (las de reverse-sdd son HU-001..HU-017), las tareas de **T-101** (las de
`docs/sdd/` son T-001..T-017) y los ADR de **ADR-019** (los del proyecto llegan a ADR-018).

## Estado

| | |
|---|---|
| **Especificaciones** | Completas y validadas cruzadamente (08-ANALYZE) |
| **Enmiendas a la constitución** | **6** — E-01 a E-06. Cinco aprobadas; **E-01 espera a D-3** |
| **Decisiones pendientes** | **4** — D-1 a D-4 del backlog §5. **D-1 bloquea la Fase 4** |
| **Implementación** | No iniciada. Ningún ítem del backlog está aplicado sobre `c3a2c29` |
| **Verificado contra el sistema de archivos** | `requires-python = ">=3.11"`, `uv.lock` en `.gitignore`, sin `.devcontainer/`, sin `CONTRIBUTING.md` |

## Primera tanda de ejecución

La regla del método es **3-5 tareas, revisar, ajustar, y solo entonces escalar** — nunca soltar las
49 de golpe. La primera tanda propuesta es **T-101 a T-105** (Fase 0), porque son independientes
entre sí, ninguna toca lógica de producto y las cinco se verifican con un comando:

```bash
git ls-files uv.lock          # T-101
uv run lint-imports           # T-102
uv run pytest -m "not gui"    # T-104
uv run ruff format --check .  # T-105
```

Si esas cinco pasan, el gate ya muerde y el resto del plan se apoya en él.
