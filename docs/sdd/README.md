# Kit SDD v2 — Vigía-eew

Especificación de la **v2** en Spec-Driven Design v2. Nivel de rigor: **spec-anchored**.

> **No reemplaza** a `docs/PRD.md`, `docs/API-SPEC.md`, `docs/TECHNICAL-DESIGN.md`,
> `docs/DATA-MODEL.md` ni `docs/IMPLEMENTATION-PLAN.md`, que siguen siendo la especificación del
> sistema **en producción (v0.6.0)** y no fueron modificados. Dos juegos con alcance temporal
> distinto y declarado: no compiten.

| # | Artefacto | Qué aporta |
|---|---|---|
| 00 | [Constitution](specs/00-CONSTITUTION.md) | 9 artículos no negociables, cada uno destilado de evidencia medida |
| 01 | [PRD](specs/01-PRD.md) | **56 requisitos EARS** con ID estable; 46 heredan sus criterios Gherkin de las HU |
| 02 | [API Spec](specs/02-API-SPEC.md) | Solo los deltas: correlación, registro de fuentes, contrato D-Bus, transporte, hilos |
| 03 | [Technical Design](specs/03-TECHNICAL-DESIGN.md) | 16 ADRs heredados por referencia; 2 cambian de estado; 5 decisiones nuevas |
| 04 | [Data Model](specs/04-DATA-MODEL.md) | 2 campos nuevos, 6 invariantes elevadas a requisito, migración de estado |
| 05 | [Implementation Plan](specs/05-IMPLEMENTATION-PLAN.md) | 9 fases; **reconcilia y sustituye a los dos planes previos** |
| 06 | [Tasks](specs/06-TASKS.md) | 17 tareas ejecutables (fases 0-2), con matriz de trazabilidad |
| 07 | [Analyze](specs/07-ANALYZE.md) | Validación cruzada de solo lectura: **8 hallazgos, 0 críticos** |
| 08 | [Consistencia global](08-CONSISTENCIA.md) | Pasada sobre los 62 documentos del repositorio: 5 correcciones aplicadas |

`changes/` está reservado para los Delta Specs: todo cambio a una capacidad ya especificada entra
por ahí antes de plegarse a `specs/` (Art. 9).

## Cómo se evita duplicar contenido

```
PRD (aquí)          = requisito EARS con REQ-ID
   ↓ enlaza
HU (reverse-sdd)    = escenarios Gherkin + casos de prueba, reconstruidos del código
```

Lo mismo con el resto: la API Spec solo especifica lo que cambia respecto a `docs/API-SPEC.md`; el
Technical Design hereda 16 de los 18 ADRs por referencia; el Plan absorbe el de reconstrucción y
reparte con el de migración arquitectónica en vez de competir con ellos.

## Estado

**Ningún artefacto ha sido aprobado ni implementado.** El SDD exige punto de control humano entre
fases; este kit se generó completo en una pasada, así que la revisión está pendiente.

**Veredicto del Analyze:** corregir los dos hallazgos ALTO primero. Uno ya está corregido (la
dependencia faltante de T-003); el otro, **REQ-ALE-004 como `[MUST]` condicional, necesita una
decisión de alcance** que no puede tomarse por defecto: define si la garantía de alerta bajo
Wayland bloquea el release.

## Primera tanda de ejecución

T-001 a T-005 (Fase 0, guardrails). Tres de las cinco llevan **comprobación negativa obligatoria**:
el gate no está hecho hasta demostrar que falla cuando debe.
