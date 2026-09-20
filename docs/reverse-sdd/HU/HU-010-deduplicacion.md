# HU-010: Deduplicación intra e inter-fuente

> **Cluster de origen:** Fase 3 · **Commits:** 1 `[COMMITS: b40c20b]`
> **Período:** 2026-06-28 · **Era:** Era 0 — Fundación

## Historia

**Como** usuario con cuatro redes sísmicas vigilando `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** una sola alerta por sismo, aunque lo reporten las cuatro
**Para** que la redundancia me proteja sin convertirse en ruido

## Contexto de la implementación original

`Deduplicator` `[VERIFY: src/vigia_eew/pipeline/dedup.py:31]` resuelve tres casos:
repetición del mismo id, revisión (`update`) del mismo id, y el mismo sismo llegando de
fuentes distintas con ids no relacionados.

El tercero es el difícil: **no existe identificador compartido** entre EMSC, USGS,
FUNVISIS y GEOFON, y el emparejamiento exacto es inviable porque redes independientes
producen soluciones genuinamente distintas para la misma ruptura. De ahí la heurística
≤100 km, ≤90 s, ≤0,5 mag `[VERIFY: src/vigia_eew/pipeline/dedup.py:72]`, que codifica
cuánto pueden diferir dos soluciones del mismo evento.

La heurística es **agnóstica al número de fuentes**, razón por la cual añadir GEOFON como
cuarta red no la modificó.

## Criterios de aceptación

### CA-010.1: Un evento nuevo se clasifica como nuevo
```gherkin
Dado un evento nunca visto
Cuando se clasifica
Entonces el resultado es "new"
```
*Fuente: test `[VERIFY: tests/test_dedup.py:49]`*

### CA-010.2: El mismo id no alerta dos veces
```gherkin
Dado un evento cuyo id ya fue alertado
Cuando llega de nuevo como create
Entonces se clasifica como duplicado
```
*Fuente: test `[VERIFY: tests/test_dedup.py:54]`*

### CA-010.3: Un `update` de un id ya alertado refresca, no re-alerta
```gherkin
Dado un evento ya alertado
Cuando llega un update del mismo id con magnitud revisada
Entonces se clasifica como "update" y la alerta se refresca en sitio
```
*Fuente: tests `[VERIFY: tests/test_dedup.py:60]`, `[VERIFY: tests/test_processor.py:92]`
— las revisiones de magnitud son rutinarias tras un sismo; alertar por cada una
entrenaría al usuario a descartar alertas por reflejo*

### CA-010.4: Un `update` de un id nunca alertado se trata como nuevo
```gherkin
Dado un update cuyo id no fue alertado antes
Cuando se clasifica
Entonces el resultado es "new"
```
*Fuente: test `[VERIFY: tests/test_dedup.py:66]` — si el create original se perdió, el
update es la primera noticia del sismo y debe alertar*

### CA-010.5: El mismo sismo desde dos fuentes produce una sola alerta
```gherkin
Dado un evento ya alertado por una fuente
Cuando otra fuente reporta uno dentro de 100 km, 90 s y 0,5 de magnitud
Entonces se considera duplicado
```
*Fuente: tests `[VERIFY: tests/test_dedup.py:75]`, `[VERIFY: tests/test_dedup.py:86]`
(GEOFON sobre fuente previa), end-to-end `[VERIFY: tests/test_resilience.py:107]`*

### CA-010.6: Fuera de cualquiera de los tres umbrales, es otro sismo
```gherkin
Dado un evento de otra fuente que excede la distancia, la ventana temporal
     o la tolerancia de magnitud
Cuando se clasifica
Entonces se considera un sismo distinto y se alerta
```
*Fuente: tests `[VERIFY: tests/test_dedup.py:106]`, `[VERIFY: tests/test_dedup.py:113]`,
`[VERIFY: tests/test_dedup.py:123]`, control negativo end-to-end
`[VERIFY: tests/test_resilience.py:121]`*

### CA-010.7: Una fuente nueva sin coincidencia previa no se suprime
```gherkin
Dado un evento que solo GEOFON reporta
Cuando no hay firma previa compatible
Entonces se alerta normalmente
```
*Fuente: test `[VERIFY: tests/test_dedup.py:100]` — evita que la lógica de dedup
silencie la cobertura extra que justifica tener cuatro fuentes*

### CA-010.8: El registro persiste id y firma
```gherkin
Dado un evento que se va a alertar
Cuando se registra
Entonces su id y su firma quedan persistidos
```
*Fuente: test `[VERIFY: tests/test_dedup.py:133]`*

### CA-010.9: El dedup sobrevive un reinicio
```gherkin
Dado un evento alertado antes de reiniciar
Cuando el agente arranca de nuevo y lo recibe
Entonces no vuelve a alertar
```
*Fuente: tests `[VERIFY: tests/test_dedup.py:143]`,
`[VERIFY: tests/test_resilience.py:138]`*

### CA-010.10: El registro poda entradas caducadas antes de guardar
```gherkin
Dado un estado con entradas de más de 24 h
Cuando se registra una alerta
Entonces se podan antes de persistir
```
*Fuente: fix `[COMMITS: b0f832c]`, test `[VERIFY: tests/test_dedup.py:157]` — ver HU-002*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-010.1 | CA-010.1 | feliz | Evento nuevo | id nuevo | "new" | `[VERIFY: tests/test_dedup.py:49]` |
| TC-010.2 | CA-010.2 | negativo | Id repetido | mismo id | duplicado | `[VERIFY: tests/test_dedup.py:54]` |
| TC-010.3 | CA-010.3 | feliz | update de alertado | mismo unid | "update" | `[VERIFY: tests/test_dedup.py:60]` |
| TC-010.4 | CA-010.4 | borde | update sin create previo | id no visto | "new" | `[VERIFY: tests/test_dedup.py:66]` |
| TC-010.5 | CA-010.5 | feliz | Dos fuentes, mismo sismo | 50 km/30 s/0.2 | duplicado | `[VERIFY: tests/test_dedup.py:75]` |
| TC-010.6 | CA-010.6 | borde | Distancia excedida | 300 km | nuevo | `[VERIFY: tests/test_dedup.py:106]` |
| TC-010.7 | CA-010.6 | borde | Ventana excedida | 200 s | nuevo | `[VERIFY: tests/test_dedup.py:113]` |
| TC-010.8 | CA-010.6 | borde | Magnitud excedida | Δ1.0 | nuevo | `[VERIFY: tests/test_dedup.py:123]` |
| TC-010.9 | CA-010.7 | feliz | Solo GEOFON | sin previo | alerta | `[VERIFY: tests/test_dedup.py:100]` |
| TC-010.10 | CA-010.8 | feliz | Registro | evento | id+firma persistidos | `[VERIFY: tests/test_dedup.py:133]` |
| TC-010.11 | CA-010.9 | borde | Reinicio | estado previo | sin re-alerta | `[VERIFY: tests/test_dedup.py:143]` |
| TC-010.12 | CA-010.10 | borde | Poda al registrar | entradas viejas | podadas | `[VERIFY: tests/test_dedup.py:157]` |
| TC-010.13 | CA-010.5 | negativo | **Enjambre**: dos sismos reales dentro de los umbrales | 2 eventos distintos a 60 km / 40 s / Δ0.3 | Hoy se fusionan en uno (falso positivo conocido) | **escribir en v2** |

## Dependencias

- **Requiere**: HU-001, HU-002, HU-008, HU-009
- **Habilita**: HU-011, HU-021, HU-022

## Notas para la v2

TC-010.13 documenta el límite conocido y no cubierto: durante un **enjambre sísmico**
ocurren sismos genuinamente distintos dentro de los tres umbrales, y la heurística los
fusiona. Los umbrales son configurables precisamente por eso, pero no hay test que fije
el comportamiento en ese escenario ni telemetría que revele con qué frecuencia ocurre.

Para la v2, la mejora de mayor valor sería incorporar la **profundidad** a la firma (dos
sismos con epicentro cercano pero profundidad muy distinta son eventos distintos), algo
que el modelo ya captura pero la heurística ignora.
