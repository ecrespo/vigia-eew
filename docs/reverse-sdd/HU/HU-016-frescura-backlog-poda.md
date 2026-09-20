# HU-016: No recibir alertas de terremotos de días pasados

> **Cluster de origen:** C-18 · **Commits:** 1 `[COMMITS: b0f832c]`
> **Período:** 2026-07-17 · **Era:** v0.6.0

## Historia

**Como** usuario que enciende el equipo tras varios días apagado
**Quiero** que el agente solo me avise de terremotos de hoy
**Para** no despertarme con una ráfaga de alertas de eventos que ya pasaron y que no puedo hacer nada por evitar

## Contexto de la implementación original

Ninguno de los cuatro ingestores filtraba por *cuándo* ocurrió el evento. De ahí dos huecos: el
primer sondeo tras una instalación nueva, o con cursor caducado, consultaba sin límite inferior; y
un evento antiguo podía alertarse simplemente por ser "nuevo" para el deduplicador.

El commit resuelve tres cosas ligadas: el filtro de frescura por día local
`[VERIFY: src/vigia_eew/pipeline/filter.py:71]`, el piso de `starttime` en medianoche local para
las consultas REST `[VERIFY: src/vigia_eew/timeutil.py:50]`, y el cableado de `prune()`
`[VERIFY: src/vigia_eew/pipeline/dedup.py:56]` — que existía con test propio desde la fase 1 pero
que **ninguna ruta de ejecución llamaba**, dejando el estado creciendo sin límite.

## Criterios de aceptación

### CA-016.1: Solo se alerta de eventos del día local actual
```gherkin
Dado today_only activo y una zona horaria configurada
Cuando llega un evento ocurrido hoy en esa zona
Entonces se acepta
Y un evento de ayer o con fecha futura se descarta
```
*Fuente: tests `[VERIFY: tests/test_filter.py:121]`, `[VERIFY: tests/test_filter.py:128]`, `[VERIFY: tests/test_filter.py:135]`*

### CA-016.2: El día se cuenta en hora local, no en UTC
```gherkin
Dado un evento a las 21:00 hora local de Venezuela, que en UTC ya es el día siguiente
Cuando se evalúa la frescura
Entonces se considera de hoy y se acepta
```
*Fuente: test `[VERIFY: tests/test_filter.py:144]` (`test_freshness_uses_local_day_not_utc_day`)*

### CA-016.3: La frescura es fail-safe ante configuración inválida
```gherkin
Dada una zona horaria inexistente o no soportada en la configuración
Cuando se evalúa la frescura
Entonces el filtro queda inerte y no suprime ningún evento
Y con today_only desactivado, un evento antiguo se conserva
```
*Fuente: tests `[VERIFY: tests/test_filter.py:161]`, `[VERIFY: tests/test_filter.py:154]`*

### CA-016.4: La frescura no relaja radio ni magnitud
```gherkin
Dado un evento de hoy pero fuera del radio o bajo la magnitud mínima
Cuando se evalúa el filtro
Entonces se descarta igualmente
```
*Fuente: test `[VERIFY: tests/test_filter.py:168]`*

### CA-016.5: Las consultas REST no arrastran backlog de días anteriores
```gherkin
Dado un cursor persistido inexistente o más antiguo que la medianoche local de hoy
Cuando se construyen los parámetros de la consulta a USGS o GEOFON
Entonces el starttime se ancla en la medianoche local de hoy
Y un cursor reciente se respeta sin modificar
Y con una zona horaria inválida se cae al cursor crudo, o se omite starttime si no hay cursor
```
*Fuente: tests `[VERIFY: tests/test_rest_usgs.py:111]`, `[VERIFY: tests/test_rest_usgs.py:121]`, `[VERIFY: tests/test_rest_usgs.py:135]`, `[VERIFY: tests/test_rest_usgs.py:149]`, `[VERIFY: tests/test_rest_usgs.py:160]`, y sus equivalentes `[VERIFY: tests/test_rest_geofon.py:109]`*

### CA-016.6: El estado persistido no crece sin límite
```gherkin
Dado un estado con entradas de más de 24 horas
Cuando se registra una nueva alerta
Entonces las entradas caducadas se podan antes de guardar
```
*Fuente: tests `[VERIFY: tests/test_dedup.py:157]` (`test_register_prunes_stale_entries_before_saving`), `[VERIFY: tests/test_state.py:72]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-016.1 | CA-016.1 | feliz | evento de hoy | hoy 10:00 local | aceptado | `[VERIFY: tests/test_filter.py:121]` |
| TC-016.2 | CA-016.1 | negativo | evento de ayer | ayer 23:00 | descartado | `[VERIFY: tests/test_filter.py:128]` |
| TC-016.3 | CA-016.1 | negativo | fecha futura | mañana | descartado | `[VERIFY: tests/test_filter.py:135]` |
| TC-016.4 | CA-016.2 | borde | 21:00 VET | UTC día siguiente | aceptado | `[VERIFY: tests/test_filter.py:144]` |
| TC-016.5 | CA-016.3 | negativo | tz inválida | `"Marte/Olimpo"` | filtro inerte | `[VERIFY: tests/test_filter.py:161]` |
| TC-016.6 | CA-016.3 | borde | `today_only=false` | evento antiguo | conservado | `[VERIFY: tests/test_filter.py:154]` |
| TC-016.7 | CA-016.4 | negativo | hoy, 900 km | fuera de radio | descartado | `[VERIFY: tests/test_filter.py:168]` |
| TC-016.8 | CA-016.5 | feliz | sin cursor | primer arranque | starttime = medianoche local | `[VERIFY: tests/test_rest_usgs.py:111]` |
| TC-016.9 | CA-016.5 | borde | cursor de hace 5 días | cursor caducado | anclado a medianoche | `[VERIFY: tests/test_rest_usgs.py:135]` |
| TC-016.10 | CA-016.5 | borde | cursor reciente | hace 2 min | respetado | `[VERIFY: tests/test_rest_usgs.py:121]` |
| TC-016.11 | CA-016.5 | negativo | tz inválida sin cursor | config rota | starttime omitido | `[VERIFY: tests/test_rest_usgs.py:160]` |
| TC-016.12 | CA-016.6 | feliz | registro con estado viejo | entradas >24 h | podadas antes de guardar | `[VERIFY: tests/test_dedup.py:157]` |

## Dependencias

- **Requiere**: HU-003 (filtro y dedup), HU-002 y HU-015 (los dos pollers con cursor)
- **Habilita**: ninguna

## Notas para la v2

Tres lecciones concentradas en un solo commit:

1. **La frescura pertenece al pipeline desde el diseño**, no como parche. Se descartó implementar
   solo el piso de consulta (RF-41) porque no cubre EMSC (push, sin `starttime`) ni FUNVISIS
   (seen-set), y dejaría un fallo del piso sin red de seguridad aguas abajo.
2. **El día local es la unidad correcta**, coherente con la hora que la propia alerta muestra.
3. **Código muerto con test verde es peor que sin test**: `prune()` pasó 14 fases con su prueba en
   verde y cero llamadas. Un chequeo de alcanzabilidad en el gate de calidad lo habría detectado.
   Limitación aceptada que persiste: si el agente pasa mucho tiempo sin alertas nuevas, no se poda
   nada hasta el siguiente `register()`.
