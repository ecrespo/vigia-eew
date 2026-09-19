# HU-110 · El usuario decide qué red manda

> Épica **EP-10** · Prioridad **P2** · Esfuerzo L · Fase **F5**
> Ítem: B-40 · Requisitos: REQ-ING-011, REQ-PIP-010, REQ-GUI-008

**Como** usuario que sabe qué red sísmica es más fiable para su región,
**quiero** elegir cuáles uso y en qué orden de preferencia,
**para** que la magnitud que veo sea la de la red en la que confío, y no la de la que resultó ser
más rápida.

## Contexto

Las cuatro redes viven hoy en cuatro secciones separadas del archivo, cada una con su `enabled`, y
**sin ninguna jerarquía entre ellas**. Cuando el mismo sismo llega por dos, el deduplicador conserva
la que llegó primero — es decir, **gana la de menor latencia**, que es un accidente de red y no una
decisión de nadie.

**El caso concreto que lo justifica es venezolano.** Un sismo local llega por EMSC con magnitud
estimada automáticamente y por FUNVISIS con magnitud revisada por el servicio nacional. Hoy se
muestra la que llegó antes. Con prioridad, el usuario decide cuál considera más fiable **para su
geografía** — que es exactamente la razón por la que FUNVISIS está en el producto.

### Tres límites deliberados

Cada uno protege algo que ya funciona, y por eso están en los criterios y no solo en el diseño:

| Límite | Qué protege | Criterio |
|---|---|---|
| La prioridad **no decide si se alerta** | Los sismos locales que solo cataloga la red nacional | CA-110.4 |
| La prioridad **no serializa las consultas** | La latencia de la alerta | CA-110.7 |
| Una red sin prioridad **se ordena al final** | Que un `config.toml` de la v0.6.0 siga siendo válido | CA-110.6 |

**Depende de HU-104.** La prioridad es un campo de la especificación de cada fuente; sin registro
declarativo habría que añadirla en cuatro sitios y leerla en un quinto.

## Criterios de aceptación

```gherkin
Escenario: CA-110.1 · Prevalece la red mas prioritaria, no la mas rapida
  Dado un sismo reportado por dos redes con magnitudes distintas
  Y que la red de mayor prioridad reporta despues que la otra
  Cuando el deduplicador une ambas llegadas
  Entonces la magnitud presentada es la de la red de mayor prioridad

Escenario: CA-110.2 · Invertir la prioridad invierte el dato mostrado
  Dado el mismo sismo reportado por dos redes con magnitudes distintas
  Cuando se invierte el orden de prioridad de esas dos redes
  Entonces la magnitud presentada pasa a ser la de la otra red

Escenario: CA-110.3 · La prioridad alcanza a epicentro y profundidad
  Dado un sismo reportado por dos redes con coordenadas ligeramente distintas
  Cuando el deduplicador une ambas llegadas
  Entonces la ubicacion y la profundidad presentadas son las de la red de mayor prioridad
  Y la distancia al punto de referencia se recalcula con esa ubicacion

Escenario: CA-110.4 · Una red de baja prioridad sigue pudiendo alertar sola
  Dado un sismo relevante reportado unicamente por la red de menor prioridad
  Cuando el pipeline lo evalua
  Entonces se presenta la alerta con normalidad

Escenario: CA-110.5 · Deshabilitar una red desde la lista la retira
  Dado que el usuario deshabilita una red en la lista
  Cuando el agente arranca
  Entonces la tarea de esa red no se crea
  Y las demas redes siguen funcionando de forma independiente

Escenario: CA-110.6 · Una configuracion sin prioridades sigue siendo valida
  Dado un archivo de configuracion escrito por una version anterior, sin prioridades declaradas
  Cuando el agente lo carga
  Entonces arranca con normalidad
  Y las redes sin prioridad declarada quedan ordenadas al final

Escenario: CA-110.7 · La prioridad no cambia el orden ni la concurrencia de las consultas
  Dado un orden de prioridad cualquiera
  Cuando el agente inicia la ingesta
  Entonces las cuatro fuentes se consultan de forma concurrente e independiente
  Y ninguna espera a otra de mayor prioridad

Escenario: CA-110.8 · La lista de la interfaz y el archivo coinciden
  Dado que el usuario reordena las redes en el panel y guarda
  Cuando se lee el archivo de configuracion
  Entonces el orden de prioridad guardado coincide con el mostrado en la interfaz
```

## Definición de hecho

- [ ] Campo de prioridad en la especificación de fuente, con valor por defecto para configuraciones antiguas
- [ ] El deduplicador resuelve por prioridad y recalcula la distancia con la ubicación que prevalece
- [ ] Lista con casillas y reordenación en el panel de configuración
- [ ] Prueba que demuestra CA-110.2 invirtiendo el orden y comprobando el cambio de magnitud

## Trazabilidad

| Requisito | Criterios | Ítem |
|---|---|---|
| REQ-ING-011 | CA-110.5, CA-110.6 | B-40 |
| REQ-PIP-010 | CA-110.1, 110.2, 110.3, 110.4, 110.7 | B-40 |
| REQ-GUI-008 | CA-110.8 | B-40 |

**Alternativas evaluadas y descartadas**, para que no se rediscutan: usar la prioridad como umbral de
confianza para decidir si se alerta —perdería los sismos locales que solo cataloga FUNVISIS— y
usarla solo como orden de consulta —en la práctica la red más rápida seguiría ganando casi siempre y
la prioridad apenas se notaría.
