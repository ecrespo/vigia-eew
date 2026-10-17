# HU-112 · El histórico en un mapa

> Épica **EP-11** · Prioridad **P2** · Esfuerzo L · Fase **F7**
> Ítem: B-43 · Requisitos: REQ-MAP-001..005
> **Requiere la enmienda [E-06](../00-ENMIENDAS-CONSTITUCION.md)**

**Como** usuario que quiere entender la sismicidad de su región,
**quiero** ver el histórico sobre un mapa, con la magnitud representada visualmente,
**para** reconocer de un vistazo dónde se concentran los sismos y cuáles me afectaron.

## Contexto

Un listado ordenado responde *"¿qué pasó?"*. Un mapa responde *"¿dónde?"*, que en sismología es la
mitad de la pregunta: dos sismos de magnitud 4 a 50 y a 250 km significan cosas distintas, y una
tabla de coordenadas no comunica eso.

**Sobre teselas de OpenStreetMap**, por decisión del mantenedor.

### No añade ninguna dependencia

`httpx` ya está para las fuentes REST, `Pillow` ya está por la bandeja, y el lienzo es Tk de la
biblioteca estándar. Descargar la tesela, decodificarla y pintarla se hace con lo que el proyecto ya
tiene.

> **Efecto lateral que conviene registrar:** el mapa convierte a Pillow en dependencia de primera
> clase **pase lo que pase con D-2**. Hasta ahora estaba en el árbol solo porque `pystray` lo exige;
> si la bandeja se retirara, saldría. Con el mapa, no. Eso **refuerza** B-02 —el piso de seguridad de
> Pillow— en lugar de debilitarlo.

### Lo que es nuevo para este producto

El agente hablaba con fuentes sísmicas y, una sola vez, con un servicio de geolocalización. El mapa
introduce **un tipo de destino nuevo**. La enmienda E-06 lo declara y, de paso, añade la regla que no
existía: los destinos de red se declaran, y uno nuevo exige enmienda.

**La consecuencia honesta:** pedir teselas revela al proveedor, aproximadamente, qué zona mira el
usuario. La caché lo reduce y el carácter bajo demanda lo acota. **No lo elimina.** Está declarado en
REQ-MAP-001 en lugar de descubrirse leyendo el código.

## Criterios de aceptación

```gherkin
Escenario: CA-112.1 · Sin el mapa abierto no hay peticiones de teselas
  Dado un agente en funcionamiento con el mapa cerrado
  Cuando se observa su trafico saliente durante su operacion normal
  Entonces no hay ninguna peticion al proveedor de teselas

Escenario: CA-112.2 · Sin red y sin cache, el listado sigue funcionando
  Dado que no hay conectividad ni teselas en cache
  Cuando el usuario abre la vista del historico
  Entonces se indica que el mapa no esta disponible
  Y el listado responde con normalidad

Escenario: CA-112.3 · La cache evita repetir peticiones
  Dado que el usuario ya visito una zona del mapa
  Cuando vuelve a esa misma zona y nivel de zoom
  Entonces no se solicitan de nuevo las teselas ya descargadas

Escenario: CA-112.4 · La magnitud se lee por el tamano del simbolo
  Dado dos sismos de magnitud 3 y 6 en el historico
  Cuando se muestran en el mapa
  Entonces el simbolo del de magnitud 6 es visiblemente mayor
  Y el orden de tamanos se corresponde con el de magnitudes

Escenario: CA-112.5 · Alertados y descartados se distinguen
  Dado un historico con sismos alertados y descartados
  Cuando se muestran en el mapa
  Entonces unos y otros se distinguen visualmente
  Y la leyenda explica la diferencia

Escenario: CA-112.6 · Los filtros valen para el mapa y para la tabla
  Dado un filtro por magnitud minima
  Cuando el usuario lo aplica
  Entonces las filas del listado y los simbolos del mapa se reducen al mismo conjunto

Escenario: CA-112.7 · La atribucion esta visible
  Cuando el mapa esta en pantalla
  Entonces se muestra la atribucion "© OpenStreetMap contributors"

Escenario: CA-112.8 · El cliente se identifica ante el proveedor
  Cuando el mapa solicita una tesela
  Entonces la peticion se identifica con el nombre y la version de la aplicacion
  Y no se solicitan teselas de forma masiva ni anticipada
```

## Definición de hecho

- [ ] Mapa sobre lienzo Tk con teselas descargadas bajo demanda y cacheadas en disco
- [ ] Atribución visible y cliente identificado
- [ ] Símbolo escalado por magnitud, con distinción entre alertados y descartados, y leyenda
- [ ] Filtros compartidos entre listado y mapa
- [ ] Degradación probada sin red y sin caché
- [ ] Prueba de CA-112.1: el agente en reposo no genera tráfico hacia el proveedor

## Riesgo de empaquetado que conviene anticipar

Pintar teselas usa el puente entre Pillow y Tk. **Ese módulo es exactamente el tipo de recurso que
falta en un binario y solo se descubre al ejecutarlo** — el proyecto ya rompió una release así
(`bdc2a9d`). El smoke del binario (HU-107, CA-107.3) es lo que lo detecta, y por eso conviene que la
fase de mapa vaya **después** de que ese smoke exista.

## Trazabilidad

| Requisito | Criterios | Ítem |
|---|---|---|
| REQ-MAP-001 | CA-112.1, CA-112.3 | B-43 |
| REQ-MAP-002 | CA-112.2 | B-43 |
| REQ-MAP-003 | CA-112.4, CA-112.5 | B-43 |
| REQ-MAP-004 | CA-112.6 | B-42, B-43 |
| REQ-MAP-005 | CA-112.7, CA-112.8 | B-43 |

**Alternativas evaluadas y descartadas:** un juego de teselas empaquetado —son gigabytes—, un
servidor de teselas propio —un servicio que administrar—, y exportar a HTML para el navegador
—sacaría la funcionalidad fuera del producto y rompería la operación headless.
