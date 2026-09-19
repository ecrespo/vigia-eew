# Delta Specs

Propuestas de cambio activas sobre capacidades ya especificadas en `../specs/`.

Un Delta Spec entra aquí cuando, al implementar, se descubre que la especificación está mal o
incompleta. **La regla es parar, escribir el delta, y solo entonces continuar** (Constitución,
Art. 9): nunca dejar que el código y la spec diverjan en silencio.

Estructura por propuesta:

```
AAAA-MM-nombre-del-cambio/
├── proposal.md      # qué se quiere cambiar y por qué
├── delta-spec.md    # el diff sobre los requisitos afectados, con sus REQ-ID
└── tasks.md         # tareas para ejecutarlo
```

Al aprobarse, el delta se pliega a `../specs/` y este directorio queda limpio.

**Ninguna propuesta activa**: la v2 no ha comenzado.
