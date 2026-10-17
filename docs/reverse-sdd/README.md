# Reverse-SDD — kit de documentación reconstruida

Documentación reconstruida por ingeniería inversa a partir del código y del historial de git,
suficiente para rebuild el sistema desde cero. Commit de referencia: `c3a2c29` (2026-09-06).

| Documento | Qué contiene |
|---|---|
| [00-INVENTARIO.md](00-INVENTARIO.md) | Alcance analizado, corrección del ruido del script, **origen verificado del proyecto**, 20 clusters curados, hotspots |
| [01-ARQUITECTURA.md](01-ARQUITECTURA.md) | Contexto, componentes, 5 flujos con diagramas, modelo de datos, 12 decisiones observadas, decisiones superadas, y lo diseñado pero no implementado |
| [02-STACK-TECNOLOGICO.md](02-STACK-TECNOLOGICO.md) | Lenguajes, dependencias con versiones del lockfile, persistencia, despliegue, 7 riesgos para la v2 |
| [03-EVOLUCION.md](03-EVOLUCION.md) | 5 eras narradas, patrones del historial, fixes recurrentes, 7 lecciones para la v2 |
| [HU/INDICE-HU.md](HU/INDICE-HU.md) | 17 historias de usuario, matriz de trazabilidad y grafo de dependencias |
| [04-MATRIZ-PRUEBAS.md](04-MATRIZ-PRUEBAS.md) | 157 casos consolidados + 5 e2e, con prioridad y cobertura actual |
| [05-PLAN-RECONSTRUCCION.md](05-PLAN-RECONSTRUCCION.md) | Alcance de la v2, decisiones de stack, 9 fases, reconciliación con los artefactos SDD existentes |
| `analysis/` | Salida bruta de los scripts (`inventory.json/md`, `history.json/md`) |

## Reglas de evidencia aplicadas

- Afirmación sobre el código → cita `[VERIFY: ruta:línea]`
- Afirmación histórica o historia de usuario → cita `[COMMITS: hash, …]`
- Lo que no se puede anclar → marca `[INFERIDO]` con su razón

**Resultado de la validación**: 327 citas `[VERIFY:]` únicas verificadas contra archivo y línea,
39 hashes comprobados con `git cat-file`, 2 marcas `[INFERIDO]` en todo el kit.

## Relación con la documentación existente

Este kit **no reemplaza** los artefactos SDD del proyecto (`docs/PRD.md`, `docs/API-SPEC.md`,
`docs/TECHNICAL-DESIGN.md`, `docs/DATA-MODEL.md`, `docs/IMPLEMENTATION-PLAN.md`), que están vivos
y sincronizados con el código. Los **contrasta** con lo que el código y la historia demuestran, y
`05-PLAN-RECONSTRUCCION.md` §4 dice qué reconciliar en cada uno.

Complementa además las tres capas de conocimiento de [`../CONTEXT_REPORT.md`](../CONTEXT_REPORT.md):
CodeGraph (estructura), Graphify (significado) y `lat.md/` (intención).
