# HU-009: Filtrado por radio, magnitud y frescura

> **Cluster de origen:** Fase 3 + Fase 15 · **Commits:** 2 `[COMMITS: b40c20b, b0f832c]`
> **Período:** 2026-06-28 → 2026-07-17 · **Era:** Era 0 + Era 5

## Historia

**Como** usuario en una ubicación concreta `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** recibir alerta solo de sismos cercanos, relevantes y de hoy
**Para** que la alerta conserve su valor y no me acostumbre a ignorarla

## Contexto de la implementación original

`GeoFilter.accepts` `[VERIFY: src/vigia_eew/pipeline/filter.py:52]` encadena cuatro
comprobaciones —radio, magnitud, país (HU-020) y frescura— y corre **antes** del
deduplicador, para que un evento rechazado no contamine el estado de dedup con una firma
que luego suprimiría un reporte legítimo del mismo sismo.

Todas las comprobaciones opcionales son **fail-safe en la misma dirección**: si no se
pueden evaluar, dejan pasar `[VERIFY: src/vigia_eew/pipeline/filter.py:73]`. Una alerta
perdida es un fallo de seguridad; una de más, una molestia.

El reloj se **inyecta** `[VERIFY: src/vigia_eew/pipeline/filter.py:37]`, que es lo que
permite congelar "hoy" en los tests sin tocar el reloj del sistema.

## Criterios de aceptación

### CA-009.1: Se acepta lo que está dentro de radio y magnitud
```gherkin
Dado un evento dentro del radio y con magnitud suficiente
Cuando se evalúa el filtro
Entonces se acepta
```
*Fuente: test `[VERIFY: tests/test_filter.py:36]`*

### CA-009.2: Se descarta lo que excede el radio o no llega a la magnitud
```gherkin
Dado un evento fuera del radio, o con magnitud menor a la mínima
Cuando se evalúa el filtro
Entonces se descarta
```
*Fuente: tests `[VERIFY: tests/test_filter.py:40]`, `[VERIFY: tests/test_filter.py:44]`*

### CA-009.3: Los límites de radio y magnitud son inclusivos
```gherkin
Dado un evento exactamente en el radio límite o en la magnitud mínima
Cuando se evalúa el filtro
Entonces se acepta
```
*Fuente: tests `[VERIFY: tests/test_filter.py:48]`, `[VERIFY: tests/test_filter.py:52]`
— el comportamiento en el borde está fijado explícitamente, no dejado al azar*

### CA-009.4: Solo se alertan sismos del día local en curso
```gherkin
Dado un evento cuyo día local, según el timezone configurado, es hoy
Cuando se evalúa el filtro
Entonces se acepta; y si es de ayer o de mañana, se descarta
```
*Fuente: fix `[COMMITS: b0f832c]` — previene que un cursor rancio tras días apagado
surface un backlog de sismos viejos como alertas; tests
`[VERIFY: tests/test_filter.py:121]`, `[VERIFY: tests/test_filter.py:128]`,
`[VERIFY: tests/test_filter.py:135]`*

### CA-009.5: El día es local, no UTC
```gherkin
Dado un sismo a las 21:00 hora local en una zona UTC-4
Cuando se evalúa la frescura
Entonces cuenta como "hoy", no como "ayer"
```
*Fuente: test `[VERIFY: tests/test_filter.py:144]` — con día UTC, el corte caería a las
20:00 local y descartaría eventos reales durante cuatro horas cada noche*

### CA-009.6: La frescura se puede desactivar
```gherkin
Dado today_only en false
Cuando llega un evento antiguo
Entonces se acepta
```
*Fuente: test `[VERIFY: tests/test_filter.py:154]`*

### CA-009.7: Una zona horaria inválida deja el filtro inerte (fail-safe)
```gherkin
Dado un timezone inválido en configuración
Cuando se evalúa la frescura
Entonces el filtro no suprime nada y registra una advertencia
```
*Fuente: test `[VERIFY: tests/test_filter.py:161]` — misma filosofía que RF-33/RF-37:
ante la duda, no suprimir*

### CA-009.8: La frescura nunca relaja radio ni magnitud
```gherkin
Dado un evento de hoy pero fuera del radio o bajo la magnitud mínima
Cuando se evalúa el filtro
Entonces se descarta igualmente
```
*Fuente: test `[VERIFY: tests/test_filter.py:168]` — evita que una comprobación nueva
debilite una preexistente*

### CA-009.9: El filtro corre antes del dedup
```gherkin
Dado un evento que el filtro rechaza
Cuando pasa por el pipeline
Entonces no se registra en el estado de deduplicación
```
*Fuente: código `[VERIFY: src/vigia_eew/pipeline/processor.py:54]`, test
`[VERIFY: tests/test_processor.py:70]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-009.1 | CA-009.1 | feliz | Dentro de todo | 50 km, M5 | Acepta | `[VERIFY: tests/test_filter.py:36]` |
| TC-009.2 | CA-009.2 | negativo | Fuera de radio | 500 km | Descarta | `[VERIFY: tests/test_filter.py:40]` |
| TC-009.3 | CA-009.2 | negativo | Magnitud baja | M1.5 | Descarta | `[VERIFY: tests/test_filter.py:44]` |
| TC-009.4 | CA-009.3 | borde | Radio exacto | =radius_km | Acepta | `[VERIFY: tests/test_filter.py:48]` |
| TC-009.5 | CA-009.3 | borde | Magnitud exacta | =min_magnitude | Acepta | `[VERIFY: tests/test_filter.py:52]` |
| TC-009.6 | CA-009.4 | feliz | Evento de hoy | hoy local | Acepta | `[VERIFY: tests/test_filter.py:121]` |
| TC-009.7 | CA-009.4 | negativo | Evento de ayer | ayer | Descarta | `[VERIFY: tests/test_filter.py:128]` |
| TC-009.8 | CA-009.4 | borde | Evento de mañana | futuro | Descarta | `[VERIFY: tests/test_filter.py:135]` |
| TC-009.9 | CA-009.5 | borde | 21:00 local en UTC-4 | 01:00 UTC día+1 | Cuenta como hoy | `[VERIFY: tests/test_filter.py:144]` |
| TC-009.10 | CA-009.6 | feliz | today_only=false | evento viejo | Acepta | `[VERIFY: tests/test_filter.py:154]` |
| TC-009.11 | CA-009.7 | negativo | TZ inválida | `"Bad/Zone"` | Inerte, no suprime | `[VERIFY: tests/test_filter.py:161]` |
| TC-009.12 | CA-009.8 | borde | Hoy pero lejos | hoy, 900 km | Descarta | `[VERIFY: tests/test_filter.py:168]` |
| TC-009.13 | CA-009.9 | borde | Rechazado no ensucia dedup | fuera de radio | Sin registro | `[VERIFY: tests/test_processor.py:70]` |

## Dependencias

- **Requiere**: HU-001, HU-003, HU-008
- **Habilita**: HU-010, HU-011, HU-020

## Notas para la v2

La combinación de reloj inyectado + fail-safe uniforme es el patrón a replicar en
cualquier filtro nuevo. Nótese la asimetría deliberada de defaults: `today_only` viene en
**true** (regla de producto siempre deseada) mientras que el filtro de país viene en
**false** (restricción opt-in). En la v2, documentar esa diferencia junto a la config para
que no se "uniformice" por error.
