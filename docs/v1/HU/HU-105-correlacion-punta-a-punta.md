# HU-105 · Un sismo se sigue de punta a punta

> Épica **EP-5** · Prioridad **P1** · Esfuerzo M · Fase **F3**
> Ítem: B-22 · Requisito: REQ-OBS-002

**Como** persona que investiga por qué una alerta apareció —o por qué no apareció—,
**quiero** poder reconstruir el recorrido completo de un sismo con una sola búsqueda,
**para** no tener que correlacionar registros a mano por marca de tiempo.

## Contexto

Un mismo sismo puede llegar por EMSC y por GEOFON con segundos de diferencia, normalizarse dos
veces, filtrarse, deduplicarse y presentarse una vez. Eso son cinco etapas que hoy dejan registros
**que no se pueden enlazar entre sí**.

El caso que más duele es el negativo: cuando una alerta **no** aparece, hay que averiguar si el
evento no llegó, si el filtro lo descartó por radio, por magnitud, por país o por frescura, o si el
deduplicador lo consideró repetido. Hoy eso se hace comparando marcas de tiempo.

El identificador debe sobrevivir **la deduplicación**, que es justo donde dos flujos se convierten
en uno: la llegada descartada tiene que quedar enlazada con la que sobrevivió, o la búsqueda pierde
precisamente la información que se buscaba.

## Criterios de aceptación

```gherkin
Escenario: CA-105.1 · El recorrido completo se recupera con una búsqueda
  Dado un sismo que entra por una fuente y termina presentándose
  Cuando se busca en los registros por su identificador de correlación
  Entonces se obtienen las entradas de ingesta, normalización, filtro, veredicto de deduplicación y presentación

Escenario: CA-105.2 · Dos llegadas del mismo sismo comparten identificador
  Dado un sismo reportado por dos fuentes distintas dentro de la ventana de deduplicación
  Cuando el deduplicador las une
  Entonces ambas llegadas quedan enlazadas al mismo identificador de correlación

Escenario: CA-105.3 · Un descarte queda explicado
  Dado un evento que el filtro descarta por estar fuera del radio
  Cuando se busca por su identificador de correlación
  Entonces el registro nombra el filtro que lo descartó y el motivo

Escenario: CA-105.4 · Una actualización se sigue como el mismo flujo
  Dado un evento que llega y después recibe una actualización de la misma fuente
  Cuando se busca por su identificador de correlación
  Entonces la actualización aparece en el mismo recorrido, no como un flujo nuevo

Escenario: CA-105.5 · El identificador no se propaga fuera del proceso
  Cuando se inspecciona lo que el sistema envía a servicios externos
  Entonces el identificador de correlación no aparece en ninguna petición saliente
```

## Definición de hecho

- [ ] Campo de correlación en el contrato interno, propagado por las cinco etapas
- [ ] El deduplicador enlaza la llegada descartada con la superviviente
- [ ] Una prueba de integración recorre las cinco etapas y verifica el enlace
- [ ] CA-105.5 verificado: es un dato interno de diagnóstico, no telemetría

## Trazabilidad

| Requisito | Criterios | Ítem | Evidencia de origen |
|---|---|---|---|
| REQ-OBS-002 | CA-105.1..105.5 | B-22 | `arch-eval/` atributo 6 y P3-1 |

**Por qué subió a P1.** No es una mejora nueva: es una **capacidad ya documentada** —REQ-OBS-002 del
PRD base— que nunca se implementó. El criterio de prioridad del backlog trata eso igual que un
hallazgo medido.
