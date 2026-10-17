# HU-107 · El empaquetado se verifica solo

> Épica **EP-7** · Prioridad **P1** · Esfuerzo ≈ 1 jornada · Fases **F0** y **F4**
> Ítems: B-14, B-15, B-23 · Requisitos: REQ-OPS-007, REQ-OPS-008, REQ-OPS-009

**Como** persona que publica una versión,
**quiero** que el pipeline detecte un binario roto antes de publicarlo,
**para** no enterarme por un usuario de que la release no arranca.

## Contexto

**Ya ocurrió dos veces seguidas.** Los commits `7b1c71c` y `c38d9f6` corrigen releases rotas por
recursos de empaquetado inválidos, y el commit `bdc2a9d` corrige un recurso que faltaba dentro del
binario. Los tres comparten causa: **lo que falta en un binario solo se descubre ejecutándolo**, y
el pipeline no lo ejecutaba.

Un tercer riesgo se añadió sin que nadie lo decidiera: el binario de Linux se construye en
`ubuntu-latest` y **hereda su glibc**. La versión mínima de sistema que el binario soporta cambia
cuando GitHub actualiza sus ejecutores — un cambio de compatibilidad que no aparece en ningún diff
del repositorio.

Las tres verificaciones son baratas comparadas con lo que evitan, y dos de ellas son requisitos que
ya estaban escritos y sin implementar.

## Criterios de aceptación

```gherkin
Escenario: CA-107.1 · Un recurso inválido detiene el build antes de empaquetar
  Dado un recurso de empaquetado con formato o dimensiones inválidas
  Cuando se ejecuta el pipeline de construcción
  Entonces falla con un mensaje que nombra el recurso
  Y falla antes de invocar al empaquetador

Escenario: CA-107.2 · Los recursos válidos no producen falsos positivos
  Dado el conjunto actual de recursos de empaquetado
  Cuando se ejecuta la validación
  Entonces pasa sin señalar ninguno

Escenario: CA-107.3 · El binario producido se ejecuta antes de publicarse
  Dado un binario recién construido
  Cuando el pipeline lo ejecuta en modo simulación
  Entonces presenta y acusa una alerta
  Y el pipeline solo publica si esa comprobación pasa

Escenario: CA-107.4 · Un recurso ausente en el binario se detecta en el pipeline
  Dado un binario al que le falta un recurso en tiempo de ejecución
  Cuando el pipeline lo ejecuta en modo simulación
  Entonces la ejecución falla y la publicación se detiene

Escenario: CA-107.5 · La base del binario de Linux está declarada
  Cuando se inspecciona la construcción del binario de Linux
  Entonces declara explícitamente su imagen base con versión
  Y no depende de la versión por defecto del ejecutor de integración

Escenario: CA-107.6 · Actualizar el ejecutor no cambia la compatibilidad del binario
  Dado que el ejecutor de integración cambia de versión
  Cuando se vuelve a construir el binario de Linux
  Entonces su versión mínima de sistema soportada no cambia
```

## Definición de hecho

- [ ] Validación de recursos ejecutándose antes del empaquetador, con prueba de recurso inválido
- [ ] Ejecución del binario en modo simulación dentro del pipeline, bloqueando la publicación
- [ ] Imagen base declarada con versión para la construcción de Linux
- [ ] Las tres comprobaciones corren en los tres jobs de construcción

## Trazabilidad

| Requisito | Criterios | Ítem | Evidencia de origen |
|---|---|---|---|
| REQ-OPS-007 | CA-107.1, CA-107.2 | B-14 | 2 releases rotas: `7b1c71c`, `c38d9f6` |
| REQ-OPS-008 | CA-107.3, CA-107.4 | B-15 | `bdc2a9d` · caso de prueba TC-007.7 |
| REQ-OPS-009 | CA-107.5, CA-107.6 | B-23 | Riesgo nuevo, permitido por la enmienda E-03 |

**B-14 va en la Fase 0** aunque su épica sea de producto: es una S, no depende de nada y cubre un
fallo que ya se materializó dos veces. Esperar a la fase de release sería aceptar un tercer
incidente evitable.
