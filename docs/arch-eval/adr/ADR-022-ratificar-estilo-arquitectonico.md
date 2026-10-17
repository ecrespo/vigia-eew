# ADR-022: Ratificar el estilo arquitectónico y nombrarlo

> **Estado**: propuesto · **Fecha**: 2026-08-16
> **Origen**: análisis con el skill `arch-patterns` — ver `03-ESTILO-ARQUITECTONICO.md`
> **Numeración**: continúa la serie de `docs/TECHNICAL-DESIGN.md`, que llega hasta ADR-018.

## Contexto

El proyecto tiene 18 ADRs que documentan decisiones **puntuales** —por qué WebSocket y no
polling, por qué Tkinter y no Qt, por qué dedup heurístico— y ninguno que diga **qué estilo
arquitectónico es el conjunto**.

En la práctica el sistema ya implementa una combinación coherente y bien elegida:
Monolito Modular como base, Pipes & Filters en el pipeline
`[VERIFY: src/vigia_eew/pipeline/processor.py:54]`, Ports & Adapters en la notificación
`[VERIFY: src/vigia_eew/notify/controller.py:35]` y el patrón Supervisor para resiliencia
`[VERIFY: src/vigia_eew/supervisor.py:80]`.

El problema es que **eso no está escrito en ninguna parte**, así que no se puede defender
ni contra una propuesta de rediseño ni contra una erosión gradual. Un contribuidor nuevo no
puede deducir el estilo del árbol de directorios — de hecho el árbol lo contradice, porque
el paquete raíz mezcla núcleo y composición (DEB-01).

## Decisión

Ratificar formalmente el estilo y registrarlo:

> **Vigía-eew es un Monolito Modular de un solo proceso, con Pipes & Filters en el
> pipeline de eventos y Ports & Adapters en la capa de notificación, supervisado por un
> Supervisor que reinicia hijos con backoff.**

Con dos compromisos que se derivan de ratificarlo:

1. **Los puertos se adaptan, no se amplían.** Al añadir un frontend, se escribe un
   adaptador que cumple `create_window(data, severity, on_acknowledge)`; no se cambia la
   firma del puerto para acomodar el toolkit. Ya hay dos adaptadores reales (Tkinter y
   Textual), así que la regla está probada.
2. **Los contratos entre etapas son `RawMessage` y `SeismicEvent`, y solo ellos.** Es la
   mitigación del anti-patrón clásico de Pipes & Filters (acoplamiento implícito por
   formatos intermedios).

## Alternativas consideradas

### Alternativa A: ratificar y nombrar el estilo actual (la propuesta)

- **Ventajas**: cuesta un documento. Da un criterio para decir que **no** a propuestas
  futuras, que es donde un ADR de estilo se paga. Hace explícitas las dos reglas que hoy se
  cumplen por intuición.
- **Desventajas**: un ADR que no cambia código puede leerse como burocracia. Y nombrar un
  estilo tienta a aplicarlo con pureza donde no hace falta — el catálogo llama a eso
  *hexágono anémico*, y este proyecto hoy está sano justamente porque no lo persiguió.
- **Costo**: ~2 horas.

### Alternativa B: adoptar Hexagonal/Clean completo en todo el sistema

Puertos y adaptadores explícitos también para la ingesta y la persistencia, con
`core/{domain,ports,use_cases}` y `adapters/` como el catálogo describe.

- **Ventajas**: uniformidad conceptual; el dominio quedaría formalmente aislado de las
  cuatro integraciones.
- **Desventajas**: **es sobreingeniería medible aquí**. El hexágono paga cuando la
  infraestructura *varía*, y en este sistema no varía: las cuatro fuentes son HTTP/WS de
  solo lectura y el estado es un JSON local que nadie ha propuesto cambiar en 15 releases.
  Añadiría un puerto y un adaptador por integración a cambio de cero variación real, y el
  dominio **ya** está aislado sin ellos `[METRIC: pipeline fan-out 2, sin infraestructura]`.
- **Costo**: 1-2 semanas, y complejidad permanente.

### Alternativa C: no hacer nada

- **Qué cuesta convivir con el problema**: el sistema funciona igual de bien sin nombre.
  En 49 commits, la falta de un ADR de estilo no ha causado ni una decisión equivocada —
  porque el autor que lo diseñó es el mismo que lo mantiene. El coste es puramente
  **potencial**: aparece el día que alguien proponga "esto debería ser microservicios" o
  "metamos un broker", y no haya un documento que responda con el análisis ya hecho.
- **Cuándo sería razonable elegirla**: si el proyecto sigue con un autor y sin
  contribuciones externas, es defendible — el conocimiento ya está en `lat.md/` y en los
  18 ADRs, aunque disperso. El argumento a favor de escribirlo es que **el análisis ya está
  hecho** (`03-ESTILO-ARQUITECTONICO.md`); no registrarlo desperdicia trabajo terminado.

## Consecuencias

- **Positivas**: existe un criterio explícito para evaluar propuestas futuras, con los
  triggers de revisión ya definidos (5.ª fuente FDSN, 2.º desarrollador, alertas para una
  organización). Las dos reglas de los puertos y los contratos pasan de tácitas a escritas.
- **Negativas**: un documento más que mantener. Y el riesgo, real, de que nombrar el estilo
  invite a perseguir pureza arquitectónica donde el pragmatismo actual funciona mejor —
  este ADR debe leerse como descripción, no como aspiración.
- **Neutrales**: no cambia una sola línea de código.

## Reversibilidad

**Total**: es un documento. Si una necesidad futura exige otro estilo, se reemplaza con un
ADR nuevo, que es exactamente para lo que sirve la serie.

## Guardas anti-sobreingeniería

- [x] **No introduce capas ni abstracciones**: describe lo que existe. Rechaza
      explícitamente la Alternativa B (hexágono completo) por falta de variación real.
- [x] **No extrae servicios**: ratifica ADR-008 (un agente por máquina, sin relay) tras
      re-evaluarlo contra las alternativas distribuidas.
- [x] **Existe una versión más aburrida y se explicó**: no escribir nada (Alternativa C).
      Se elige escribirlo solo porque el análisis ya está hecho y registrarlo es marginal.
- [x] **Declara qué NO se toca**: ningún archivo de `src/`. No obliga a reorganizar nada
      —esa es la decisión de ADR-019, independiente— ni a introducir puertos donde hoy
      hay llamadas directas.
