# HU-021: Fuente local FUNVISIS (cobertura Venezuela)

> **Cluster de origen:** RF-38 · **Commits:** 1 `[COMMITS: 10bb72d]`
> **Período:** 2026-07-05 · **Era:** Era 4 — Redundancia de fuentes

## Historia

**Como** usuario en Venezuela `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** enterarme también de los sismos locales pequeños
**Para** tener el mismo nivel de información que la red sismológica de mi país

## Contexto de la implementación original

EMSC y USGS **sub-catalogan** los sismos venezolanos pequeños (M2–3): se enfocan en
eventos regional o globalmente significativos. FUNVISIS, la red nacional, es la autoridad
para esos, pero no ofrece canal push — solo el archivo `maravilla.json` que consume su
propio mapa web.

`FUNVISISPoller` `[VERIFY: src/vigia_eew/ingest/rest_funvisis.py:40]` espeja la forma de
`RESTReconciler` pero más simple: sin distinción create/update y **sin cursor persistido**,
porque el endpoint no admite `starttime` y siempre devuelve el lote actual. La novedad se
rastrea con un **seen-set en memoria**
`[VERIFY: src/vigia_eew/ingest/rest_funvisis.py:86]`, sembrado en el primer poll **sin
alertar**.

Ese sembrado es la decisión crítica: sin él, cada reinicio reproduciría el historial ya
publicado de FUNVISIS como una ráfaga de alertas — el peor fallo posible para esta fuente.
Que el set viva solo en memoria significa que reiniciar **olvida deliberadamente** el
historial, en vez de arriesgar la ráfaga.

## Criterios de aceptación

### CA-021.1: El primer poll siembra sin emitir nada
```gherkin
Dado un arranque del agente
Cuando se completa el primer poll a FUNVISIS
Entonces no se emite ningún evento y el seen-set queda sembrado
```
*Fuente: test `[VERIFY: tests/test_rest_funvisis.py:84]` — evita la ráfaga de alertas
históricas en cada reinicio*

### CA-021.2: A partir del segundo poll, solo se emiten los nuevos
```gherkin
Dado un seen-set ya sembrado
Cuando un poll devuelve eventos nuevos junto a los ya vistos
Entonces solo se emiten los nuevos
```
*Fuente: test `[VERIFY: tests/test_rest_funvisis.py:92]`*

### CA-021.3: Un evento ya visto no se reemite entre polls
```gherkin
Dado un evento emitido en un poll anterior
Cuando vuelve a aparecer en el lote actual
Entonces no se reemite
```
*Fuente: test `[VERIFY: tests/test_rest_funvisis.py:110]`*

### CA-021.4: Se inyecta un id determinista
```gherkin
Dado un evento de FUNVISIS sin identificador propio estable
Cuando se procesa
Entonces se le asigna un id determinista derivado de sus campos
```
*Fuente: test `[VERIFY: tests/test_rest_funvisis.py:127]`, código
`[VERIFY: src/vigia_eew/ingest/rest_funvisis.py:121]` — el id debe ser reproducible para
que el dedup por id funcione entre polls*

### CA-021.5: Todo fallo de red o formato se absorbe
```gherkin
Dado un error de red, un status distinto de 200, un JSON inválido
     o una carga que no es una lista
Cuando ocurre durante el poll
Entonces se registra y el bucle continúa
```
*Fuente: tests `[VERIFY: tests/test_rest_funvisis.py:141]`,
`[VERIFY: tests/test_rest_funvisis.py:149]`,
`[VERIFY: tests/test_rest_funvisis.py:156]`,
`[VERIFY: tests/test_rest_funvisis.py:162]`*

### CA-021.6: El bucle poll-espera es perpetuo
```gherkin
Dado el poller corriendo
Cuando termina un poll
Entonces espera el intervalo y vuelve a consultar, hasta ser cancelado
```
*Fuente: test `[VERIFY: tests/test_rest_funvisis.py:168]`*

### CA-021.7: La hora local de FUNVISIS se convierte a UTC
```gherkin
Dado un evento con hora en zona de Venezuela
Cuando se normaliza
Entonces time_utc queda en UTC
```
*Fuente: test `[VERIFY: tests/test_normalize.py:196]` — ver HU-008*

### CA-021.8: La fuente se puede habilitar y configurar
```gherkin
Dado la sección [sources.funvisis] en config
Cuando se carga la configuración
Entonces se aplican sus valores; y si no se define, se usan los defaults
```
*Fuente: tests `[VERIFY: tests/test_config.py:53]`,
`[VERIFY: tests/test_config.py:61]`, `[VERIFY: tests/test_app.py:64]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-021.1 | CA-021.1 | feliz | Primer poll | 20 eventos | 0 emitidos, set sembrado | `[VERIFY: tests/test_rest_funvisis.py:84]` |
| TC-021.2 | CA-021.2 | feliz | Segundo poll | 2 nuevos | Solo 2 emitidos | `[VERIFY: tests/test_rest_funvisis.py:92]` |
| TC-021.3 | CA-021.3 | borde | Repetido | mismo evento | No reemitido | `[VERIFY: tests/test_rest_funvisis.py:110]` |
| TC-021.4 | CA-021.4 | feliz | Id determinista | campos | Id reproducible | `[VERIFY: tests/test_rest_funvisis.py:127]` |
| TC-021.5 | CA-021.5 | negativo | Error de red | ConnectError | Absorbido | `[VERIFY: tests/test_rest_funvisis.py:141]` |
| TC-021.6 | CA-021.5 | negativo | Status 500 | 500 | Absorbido | `[VERIFY: tests/test_rest_funvisis.py:149]` |
| TC-021.7 | CA-021.5 | negativo | JSON inválido | roto | Absorbido | `[VERIFY: tests/test_rest_funvisis.py:156]` |
| TC-021.8 | CA-021.5 | negativo | No es lista | `{}` | Absorbido | `[VERIFY: tests/test_rest_funvisis.py:162]` |
| TC-021.9 | CA-021.6 | feliz | Bucle | corriendo | Poll + espera | `[VERIFY: tests/test_rest_funvisis.py:168]` |
| TC-021.10 | CA-021.7 | borde | Hora VET | UTC-4 | Convertida | `[VERIFY: tests/test_normalize.py:196]` |
| TC-021.11 | CA-021.8 | feliz | Config FUNVISIS | TOML | Aplicada | `[VERIFY: tests/test_config.py:61]` |
| TC-021.12 | CA-021.1 | negativo | **Reinicio con eventos recientes reales**: sismo publicado 2 min antes del arranque | evento nuevo en el primer lote | Hoy se pierde por el sembrado (compromiso aceptado) | **escribir en v2** |

## Dependencias

- **Requiere**: HU-007, HU-008
- **Habilita**: cobertura local de Venezuela

## Notas para la v2

TC-021.12 documenta el compromiso real del seen-set: como el sembrado no alerta, un sismo
publicado **poco antes** del arranque del agente no genera alerta. Es el precio de evitar
la ráfaga histórica y está bien elegido, pero en la v2 podría refinarse cruzando el
sembrado con el filtro de frescura (HU-009): sembrar sin alertar solo los eventos
anteriores a, digamos, 10 minutos, y alertar los más recientes.

También revisable: el endpoint es **HTTP plano** porque FUNVISIS no ofrece HTTPS válido
(RR-5). Aceptable por ser dato público y de solo lectura, pero conviene re-verificar.
