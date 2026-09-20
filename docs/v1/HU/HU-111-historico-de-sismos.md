# HU-111 · El agente deja de olvidar

> Épica **EP-11** · Prioridad **P2** · Esfuerzo L · Fases **F6** y **F7**
> Ítems: B-41, B-42 · Requisitos: REQ-HIS-001..006, REQ-MAP-004
> **Requiere la enmienda [E-05](../00-ENMIENDAS-CONSTITUCION.md)**

**Como** usuario que quiere entender el comportamiento del agente y de la sismicidad de su zona,
**quiero** consultar los sismos que el agente ha evaluado, con el veredicto de cada uno,
**para** saber cuántos me afectaron y, sobre todo, **por qué no me avisó de aquel del que me
enteré por las noticias**.

## Contexto

El agente hoy **recuerda solo lo justo para no repetirse**: qué identificadores ya alertó, podados a
24 horas `[VERIFY: src/vigia_eew/state.py:61]`. Pasado ese plazo no queda rastro.

**La pregunta que esto deja sin respuesta es la que más importa cuando el producto parece fallar.**
Si un sismo ocurrió y no hubo alerta, hoy no hay forma de saber si el evento no llegó, si el filtro
lo descartó por radio, por magnitud, por país o por frescura, o si el deduplicador lo consideró
repetido.

Por eso se guardan **también los descartes, con su motivo**. Con el veredicto registrado, esa
investigación pasa a ser una consulta.

Encaja con **HU-105**: el identificador de correlación es lo que enlaza las llegadas de un mismo
sismo por redes distintas, y es la clave natural del histórico.

### El obstáculo: la constitución decía que no hay base de datos

*"Persistencia: JSON atómico en disco. **Sin base de datos**"*, con este argumento: *"el estado son
unos KB en memoria consultados por pertenencia"*. **Cierto del estado operativo, falso del
histórico** — son dos problemas distintos que hasta ahora no hacía falta separar.

La enmienda E-05 **acota, no deroga**: el estado operativo sigue en JSON, sin excepción. Y lo que la
hace defendible es que **SQLite es biblioteca estándar**: cero dependencias nuevas, sin servicio que
administrar, un archivo junto al que ya existe.

## Criterios de aceptación

```gherkin
Escenario: CA-111.1 · Un sismo alertado queda registrado
  Dado un evento que supera el filtro y produce alerta
  Cuando el pipeline termina de procesarlo
  Entonces aparece en el historico marcado como alertado
  Y conserva su identificador de correlacion

Escenario: CA-111.2 · Un sismo descartado queda registrado con su motivo
  Dado un evento que el filtro descarta por estar fuera del radio
  Cuando el pipeline termina de procesarlo
  Entonces aparece en el historico marcado como descartado
  Y el motivo registrado nombra el filtro que lo descarto

Escenario: CA-111.3 · Un duplicado queda enlazado, no perdido
  Dado un sismo reportado por dos redes que el deduplicador une
  Cuando ambas llegadas se registran
  Entonces la llegada descartada consta como duplicada
  Y queda enlazada con la que produjo la alerta

Escenario: CA-111.4 · Un fallo del historico no impide la alerta
  Dado que el archivo del historico no se puede escribir
  Cuando llega un evento relevante
  Entonces la alerta se presenta con normalidad
  Y el fallo queda anotado en el registro de la aplicacion

Escenario: CA-111.5 · El historico no retrasa la presentacion
  Dado un evento relevante
  Cuando se mide el tiempo entre su llegada y su presentacion
  Entonces el registro en el historico no forma parte de ese camino

Escenario: CA-111.6 · Un historico de esquema anterior migra solo
  Dado un archivo de historico de la version de esquema anterior
  Cuando el agente arranca
  Entonces el esquema se migra sin intervencion del usuario
  Y ninguna fila se pierde

Escenario: CA-111.7 · El historico se mantiene acotado
  Dado un historico con entradas mas antiguas que la retencion configurada
  Cuando se ejecuta la poda
  Entonces las entradas anteriores a la retencion desaparecen
  Y las posteriores permanecen

Escenario: CA-111.8 · La consulta filtra por lo que importa
  Dado un historico con entradas de distintas fechas, magnitudes, distancias y redes
  Cuando se consulta por magnitud minima y rango de fechas
  Entonces se devuelven exactamente las entradas que cumplen ambos criterios
  Y se pueden ordenar por cualquiera de esos campos

Escenario: CA-111.9 · El historico no sale del equipo
  Cuando se inspecciona el trafico saliente del agente
  Entonces ninguna peticion contiene datos del historico
```

## Definición de hecho

- [ ] Esquema SQLite versionado, con su migración probada desde la versión anterior
- [ ] Registro desde el pipeline **fuera del camino de presentación** (CA-111.5)
- [ ] Retención configurable, con su valor por defecto declarado, y poda probada
- [ ] Vista de listado con filtros y ordenación por los cinco criterios
- [ ] Prueba de CA-111.4 con el archivo en solo lectura

## Trazabilidad

| Requisito | Criterios | Ítem |
|---|---|---|
| REQ-HIS-001 | CA-111.1, CA-111.2, CA-111.3 | B-41 |
| REQ-HIS-002 | CA-111.4, CA-111.5 | B-41 |
| REQ-HIS-003 | CA-111.6 | B-41 |
| REQ-HIS-004 | CA-111.7 | B-41 |
| REQ-HIS-005 | CA-111.8 | B-42 |
| REQ-HIS-006 | CA-111.9 | B-41 |

**El criterio que no hay que perder de vista es CA-111.4.** El histórico es una **consecuencia** de
la alerta, nunca una condición: Art. 1 y Art. 3. Un agente que no puede escribir su histórico sigue
siendo un agente que alerta.
