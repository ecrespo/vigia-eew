# HU-106 · La alerta llega también en Wayland

> Épica **EP-6** · Prioridad **P1** · Esfuerzo L, sin estimar · Fase **F4**
> Ítems: B-19, B-20 · Requisitos: REQ-ALE-003, REQ-ALE-004
> **Bloqueada por la decisión D-1**

**Como** persona que usa GNOME sobre Wayland —el escritorio Linux más común—,
**quiero** que la alerta sísmica aparezca por encima de todo igual que en los demás escritorios,
**o al menos saber que en el mío no está garantizada**,
**para** no confiar en una protección que no tengo.

## Contexto

**Es la brecha más importante del proyecto y la más antigua.**

El producto se define por una promesa: una alerta imposible de ignorar. Bajo Wayland la ventana
`topmost` de Tkinter **no tiene garantía** de quedar por encima —el compositor decide— y el ícono de
bandeja depende de una extensión que el usuario puede no tener instalada.

ADR-010 diseñó la solución en la **v0.1.0**: un servicio D-Bus con extensión de shell, y caída a
Tkinter donde no esté disponible. Se profundizó en un commit propio (`230b0b8`). **Nunca se escribió
una línea de código.** Las tres etapas de auditoría lo señalaron desde ángulos distintos.

**Son dos capacidades, no una**, y esa separación es lo que hace la épica manejable:

| | B-19 · Declarar | B-20 · Cumplir |
|---|---|---|
| Qué hace | Acota la promesa a lo que el producto cumple | Extiende la promesa a Wayland |
| Esfuerzo | S | L, empieza por un spike |
| Riesgo | Ninguno | El más alto del plan |
| Valor si el otro no se hace | **Alto**: deja de prometer de más | Alto, pero tardío |

**La recomendación es hacer B-19 primero e independientemente.** Es barato, es honesto, y evita que
el producto siga afirmando algo que no cumple durante todo el tiempo que dure el spike.

## Criterios de aceptación

```gherkin
Escenario: CA-106.1 · El alcance de la garantía está declarado
  Cuando se consulta la documentación del producto
  Entonces declara en qué entornos de escritorio la presentación por encima de todo está garantizada
  Y declara explícitamente en cuáles no lo está y por qué

Escenario: CA-106.2 · El usuario ve la limitación en su propia máquina
  Dado un agente ejecutándose en una sesión donde la garantía no se puede cumplir
  Cuando el usuario consulta el estado del agente
  Entonces el estado indica que la presentación no está garantizada en ese entorno

Escenario: CA-106.3 · La detección de entorno no rompe nada
  Dado un entorno de escritorio que el sistema no reconoce
  Cuando el agente arranca
  Entonces arranca igualmente y trata la garantía como no confirmada
  Y no falla ni se queda sin presentar alertas

Escenario: CA-106.4 · La alerta se presenta por el servicio de escritorio
  Dado un entorno Wayland con el servicio de presentación disponible
  Cuando llega un evento relevante
  Entonces la alerta se presenta por encima de las demás ventanas
  Y no puede descartarse con las acciones habituales de cierre

Escenario: CA-106.5 · La caída al camino conocido es automática
  Dado un entorno Wayland sin el servicio de presentación disponible
  Cuando llega un evento relevante
  Entonces la alerta se presenta por el camino existente
  Y el registro nombra la degradación

Escenario: CA-106.6 · La degradación nunca deja al usuario sin alerta
  Dado que el servicio de presentación falla durante la presentación
  Cuando el sistema detecta el fallo
  Entonces presenta la alerta por el camino existente
  Y el evento no se pierde

Escenario: CA-106.7 · La paridad entre frontends se mantiene
  Dado un mismo evento relevante
  Cuando se presenta en el frontend gráfico y en el de terminal
  Entonces ambos comunican la misma severidad, distancia y magnitud
```

## Definición de hecho

- [ ] **D-1 resuelta**, y REQ-ALE-004 marcado `[MUST]` o `[SHOULD]` en consecuencia
- [ ] Matriz de entornos publicada: dónde está garantizada la alerta y dónde no
- [ ] Spike cerrado con un veredicto escrito: viable, viable con condiciones, o no viable
- [ ] Si es viable: presentación por servicio de escritorio con caída automática y probada

## Trazabilidad

| Requisito | Criterios | Ítem | Evidencia de origen |
|---|---|---|---|
| REQ-ALE-003 | CA-106.1, 106.2, 106.3 | B-19 | Art. 1 de la constitución |
| REQ-ALE-004 | CA-106.4, 106.5, 106.6, 106.7 | B-20 | **ADR-010**, v0.1.0 · `230b0b8` |

**El spike va antes que la implementación y tiene derecho a decir que no.** Si el veredicto es que
la garantía no es alcanzable con esfuerzo razonable, **CA-106.1 y CA-106.2 siguen siendo
obligatorias**: el producto no puede seguir prometiendo lo que no cumple, aunque no pueda cumplirlo.
