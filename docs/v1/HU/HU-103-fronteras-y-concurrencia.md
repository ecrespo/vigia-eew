# HU-103 · Fronteras y concurrencia demostradas

> Épica **EP-3** · Prioridad **P1** · Esfuerzo ≈ 1 jornada · Fases **F0**, **F2** y **F3**
> Ítems: B-06, B-07, B-08, B-24, B-27, B-28 · Requisitos: REQ-OPS-002, 003, REQ-OBS-005, 008

**Como** persona que mantiene el proyecto con más de un colaborador,
**quiero** que las fronteras entre módulos y el orden de apagado estén verificados por herramienta,
**para** que dejen de depender de que quien toca el código conozca la intención original.

## Contexto

**El hallazgo de mayor severidad de toda la auditoría de arquitectura está aquí.** `Application`
asigna `_loop` y `_sup` desde el hilo de asyncio `[VERIFY: src/vigia_eew/app.py:420,431]` y los lee
desde el hilo de Tk `[VERIFY: src/vigia_eew/app.py:443]`, sin ninguna sincronización. Si la parada
llega antes de que el hilo trabajador haya publicado ambos, **la cancelación se omite en silencio**:
el proceso termina dejando tareas vivas, y ocurre o no según el instante exacto en que se pulse
salir.

Lo notable es que **el proyecto ya tiene el patrón correcto**: `agent_state.py:18` protege su estado
compartido con un `threading.Lock` para exactamente este problema. No hay que inventar nada, hay que
aplicarlo donde falta.

El orden de trabajo importa: **primero el test que falla**, después el arreglo. Un test escrito
después del arreglo no demuestra que el problema existía.

## Criterios de aceptación

```gherkin
Escenario: CA-103.1 · La carrera de apagado queda demostrada
  Dado el código actual, sin sincronización del estado compartido de la aplicación
  Cuando se ejecuta el test que solicita la parada antes de que el hilo trabajador publique su bucle
  Entonces el test falla
  Y el fallo describe la cancelación omitida, no un tiempo de espera agotado

Escenario: CA-103.2 · El apagado deja de depender del instante
  Dado el estado compartido protegido por lock y evento de disponibilidad
  Cuando la parada llega antes de que el bucle esté publicado
  Entonces el sistema espera a que esté disponible o registra un aviso que nombra la situación
  Y ninguna tarea queda viva tras la parada

Escenario: CA-103.3 · El apagado sigue siendo correcto en el caso normal
  Dado un agente en ejecución con sus cinco tareas activas
  Cuando se solicita la parada
  Entonces todas las tareas se cancelan y el proceso termina sin tareas huérfanas

Escenario: CA-103.4 · Una importación prohibida no entra
  Dado un módulo del pipeline que importa un módulo de notificación
  Cuando se ejecuta la verificación de fronteras
  Entonces falla nombrando el contrato violado

Escenario: CA-103.5 · Un ciclo nuevo no entra
  Dado un ciclo de importación introducido deliberadamente
  Cuando se ejecuta la verificación de fronteras
  Entonces falla señalando el ciclo

Escenario: CA-103.6 · La propiedad de cada dato entre hilos está escrita
  Cuando se consulta la documentación de decisiones del proyecto
  Entonces existe una tabla que declara, por cada dato mutable accedido por más de un hilo, a qué hilo pertenece y con qué primitiva se sincroniza
  Y el estado compartido de la aplicación aparece en ella

Escenario: CA-103.7 · La deriva entre decisión y código falla como un lint
  Dado un enlace roto entre el código y la decisión que lo explica
  Cuando se ejecuta el gate
  Entonces falla igual que ante un error de estilo
```

## Definición de hecho

- [ ] El test de CA-103.1 falla contra `c3a2c29` y pasa tras el arreglo
- [ ] Cuatro contratos de frontera declarados y verificados en el gate
- [ ] Tabla de propiedad de datos por hilo publicada en la capa de intención
- [ ] Backlinks en los tres puntos de mayor valor: veredicto de deduplicación, aceptación del filtro y resolución de la referencia automática

## Trazabilidad

| Requisito | Criterios | Ítem | Evidencia de origen |
|---|---|---|---|
| REQ-OPS-002 | CA-103.1, 103.2, 103.3 | B-07, B-08 | `arch-eval/` **P2-1** · ADR-002 |
| REQ-OBS-005 | CA-103.4, CA-103.5 | B-06 | `arch-eval/` P2-2 · ADR-003 |
| REQ-OPS-003 | CA-103.6 | B-24 | Art. 6 |
| REQ-OBS-008 | CA-103.7 | B-27, B-28 | Art. 9 · `CONTEXT_REPORT.md` §6.3 |

**Dato que conviene recordar al fijar los contratos:** el análisis a nivel de archivo del grafo de
dependencias dio **0 ciclos**. Los contratos no arreglan un ciclo existente — **impiden el
primero**.
