# Historias de Usuario — v1.0

> 12 historias · **86 criterios de aceptación** en Gherkin · Insumo:
> [`docs/BACKLOG-PRIORIZADO.md`](../../BACKLOG-PRIORIZADO.md) rev. 3

Estas HU describen **capacidades nuevas o documentadas y sin construir**. Las 17 historias de
[`docs/reverse-sdd/HU/`](../../reverse-sdd/HU/INDICE-HU.md) (HU-001..HU-017) describen lo que la
v0.6.0 **ya hace** y no se repiten aquí. La numeración empieza en 101 para que nunca se confundan.

| HU | Capacidad | Épica | Prio | Fase | CA | Ítems |
|---|---|---|---|---|---|---|
| [HU-101](HU-101-runtime-y-dependencias-reproducibles.md) | Resolución reproducible y runtime con soporte | EP-1 | **P0** | F0, F1 | 8 | B-01..B-05, B-13, B-16, B-17 |
| [HU-102](HU-102-gate-de-calidad-completo.md) | El gate mide las ocho dimensiones | EP-2 | P1 | F0, F2 | 7 | B-09..B-12, B-25, B-26 |
| [HU-103](HU-103-fronteras-y-concurrencia.md) | Fronteras y concurrencia demostradas | EP-3 | P1 | F0, F2, F3 | 7 | B-06, B-07, B-08, B-24, B-27, B-28 |
| [HU-104](HU-104-registro-declarativo-de-fuentes.md) | Añadir una fuente cuesta tres puntos | EP-4 | P1 | F3 | 6 | B-18, B-21 |
| [HU-105](HU-105-correlacion-punta-a-punta.md) | Un sismo se sigue de punta a punta | EP-5 | P1 | F3 | 5 | B-22 |
| [HU-106](HU-106-alerta-bajo-wayland.md) | La alerta llega también en Wayland | EP-6 | **P1** | F4 | 7 | B-19, B-20 |
| [HU-107](HU-107-empaquetado-verificable.md) | El empaquetado se verifica solo | EP-7 | P1 | F0, F4 | 6 | B-14, B-15, B-23 |
| [HU-108](HU-108-panel-de-configuracion.md) | Configurar sin editar un archivo | EP-8 | P2 | F5 | 10 | B-35..B-38 |
| [HU-109](HU-109-entorno-de-contribucion.md) | Un colaborador aporta el mismo día | EP-9 | P1 | F1 | 5 | B-34 |
| [HU-110](HU-110-prioridad-de-redes.md) | El usuario decide qué red manda | EP-10 | P2 | F5 | 8 | B-40 |
| [HU-111](HU-111-historico-de-sismos.md) | El agente deja de olvidar | EP-11 | P2 | F6, F7 | 9 | B-41, B-42 |
| [HU-112](HU-112-mapa-del-historico.md) | El histórico en un mapa | EP-11 | P2 | F7 | 8 | B-43 |

**Total: 86 criterios** sobre 37 ítems del backlog.

## Las dos que hay que leer primero

**HU-106** es la brecha entre lo que el producto promete y lo que cumple, y lleva especificada sin
construir desde la v0.1.0. Es también la única bloqueada por una decisión —**D-1**— que cambia el
criterio de corte del release.

**HU-101** es la que desbloquea a casi todas las demás: sin lockfile versionado no se puede demostrar
que una resolución cambió, y sin el runtime resuelto no tiene sentido fijar techos ni construir la
imagen de desarrollo.

## Las tres que cambian la constitución

**HU-110, HU-111 y HU-112 son capacidad nueva pedida**, no deuda: nadie las prometió por escrito.
Entran en la v1.0 por decisión del mantenedor, y las tres exigen tramitar una enmienda antes de
escribir código:

| HU | Restricción que cambia | Enmienda |
|---|---|---|
| HU-111 | *"Persistencia: sin base de datos"* | [E-05](../00-ENMIENDAS-CONSTITUCION.md) — se acota al estado operativo |
| HU-112 | *(no existía regla sobre destinos de red)* | [E-06](../00-ENMIENDAS-CONSTITUCION.md) — se **añade** una |

HU-110 no requiere enmienda propia: se apoya en el registro declarativo de fuentes que HU-104 ya
introduce.

## Convenciones

- **Gherkin** para los criterios de aceptación; **EARS** para los requisitos en
  [02-PRD-DELTA.md](../02-PRD-DELTA.md). Cada criterio verifica al menos un requisito, y cada
  requisito en alcance tiene al menos un criterio — comprobado en
  [08-ANALYZE](../08-ANALYZE.md).
- `[VERIFY: archivo:línea]` señala evidencia comprobada en el código de `c3a2c29`.
- `[COMMITS: hash]` señala evidencia en el historial.
- Los escenarios describen **comportamiento observable**, no implementación: por eso hablan de "la
  verificación de fronteras" y no de la herramienta concreta, que es una decisión del Technical
  Design y puede cambiar sin invalidar el criterio.
