# HU-014: Enterarme también de los temblores pequeños de mi país

> **Cluster de origen:** C-16 · **Commits:** 1 `[COMMITS: 10bb72d]`
> **Período:** 2026-07-05 · **Era:** v0.4.0

## Historia

**Como** usuario en Venezuela
**Quiero** recibir también los sismos locales pequeños que las redes internacionales no catalogan
**Para** tener el mismo aviso que da la red sísmica nacional, que es la que sí los registra

## Contexto de la implementación original

EMSC y USGS sub-catalogan los sismos venezolanos de M2–3, que son precisamente los que se sienten.
FUNVISIS es la autoridad para esos, pero no ofrece canal push: solo el `maravilla.json` que consume
su propio mapa web. `FUNVISISPoller` `[VERIFY: src/vigia_eew/ingest/rest_funvisis.py:40]` lo
sondea cada 60 s.

A diferencia de USGS, **no hay cursor**: el endpoint no acepta `starttime` y devuelve siempre el
lote actual. La novedad se sigue con un *seen-set* en memoria sembrado en el primer sondeo
`[VERIFY: src/vigia_eew/ingest/rest_funvisis.py:60]`.

> **Nota de trazabilidad:** el asunto del commit cita `(RF-05)`, pero el requisito que implementa
> es **RF-38** según ADR-015. Discrepancia del mensaje, no del código.

## Criterios de aceptación

### CA-014.1: El primer sondeo siembra, no alerta
```gherkin
Dado un agente recién arrancado
Cuando ejecuta su primer sondeo a FUNVISIS
Entonces no emite ningún evento
Y registra todos los eventos devueltos como ya vistos
```
*Fuente: test `[VERIFY: tests/test_rest_funvisis.py:84]` (`test_first_poll_emits_nothing_but_seeds`)*

### CA-014.2: Solo se emite lo nuevo desde el arranque
```gherkin
Dado un primer sondeo ya sembrado
Cuando un sondeo posterior devuelve eventos nuevos junto a los ya vistos
Entonces solo se emiten los nuevos
Y un mismo evento no se reemite en sondeos sucesivos
```
*Fuente: tests `[VERIFY: tests/test_rest_funvisis.py:92]`, `[VERIFY: tests/test_rest_funvisis.py:110]`*

### CA-014.3: Los eventos reciben un identificador determinista
```gherkin
Dado un evento de FUNVISIS sin identificador propio
Cuando se ingiere
Entonces se le asigna un id derivado de sus datos, estable entre sondeos
```
*Fuente: test `[VERIFY: tests/test_rest_funvisis.py:127]`; código `[VERIFY: src/vigia_eew/ingest/rest_funvisis.py:120]`*

### CA-014.4: La hora local venezolana se convierte a UTC
```gherkin
Dado un evento de FUNVISIS con su hora en zona local
Cuando se normaliza
Entonces el instante interno queda en UTC consciente de zona
Y una fecha o profundidad malformada descarta el evento sin romper el lote
```
*Fuente: tests `[VERIFY: tests/test_normalize.py:196]`, `[VERIFY: tests/test_normalize.py:248]`, `[VERIFY: tests/test_normalize.py:206]`*

### CA-014.5: Ningún fallo del endpoint detiene la ingesta
```gherkin
Dado un endpoint que falla por red, responde distinto de 200, devuelve JSON inválido o una estructura inesperada
Cuando el poller ejecuta su ciclo
Entonces el error se absorbe y el sondeo continúa en el siguiente ciclo
```
*Fuente: tests `[VERIFY: tests/test_rest_funvisis.py:141]`, `[VERIFY: tests/test_rest_funvisis.py:149]`, `[VERIFY: tests/test_rest_funvisis.py:156]`, `[VERIFY: tests/test_rest_funvisis.py:162]`*

### CA-014.6: Los eventos locales no requieren lógica especial aguas abajo
```gherkin
Dado un usuario fuera de Venezuela
Cuando llega un evento de FUNVISIS
Entonces se descarta por el filtro de radio ordinario, sin ninguna regla específica de fuente
```
*Fuente: código `[VERIFY: src/vigia_eew/pipeline/filter.py:52]`; configuración `[VERIFY: tests/test_config.py:53]`*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-014.1 | CA-014.1 | feliz | primer sondeo | 20 eventos | 0 emitidos, 20 sembrados | `[VERIFY: tests/test_rest_funvisis.py:84]` |
| TC-014.2 | CA-014.2 | feliz | segundo sondeo | 1 nuevo | 1 emitido | `[VERIFY: tests/test_rest_funvisis.py:92]` |
| TC-014.3 | CA-014.2 | borde | tercer sondeo idéntico | sin novedades | 0 emitidos | `[VERIFY: tests/test_rest_funvisis.py:110]` |
| TC-014.4 | CA-014.3 | feliz | id derivado | mismos datos | id estable | `[VERIFY: tests/test_rest_funvisis.py:127]` |
| TC-014.5 | CA-014.4 | feliz | hora local VET | `-04:00` implícito | UTC correcto | `[VERIFY: tests/test_normalize.py:196]` |
| TC-014.6 | CA-014.4 | negativo | fecha malformada | texto inválido | evento descartado | `[VERIFY: tests/test_normalize.py:248]` |
| TC-014.7 | CA-014.5 | negativo | JSON inválido | cuerpo roto | absorbido | `[VERIFY: tests/test_rest_funvisis.py:156]` |
| TC-014.8 | CA-014.5 | negativo | `features` no es lista | estructura inesperada | absorbido | `[VERIFY: tests/test_rest_funvisis.py:162]` |
| TC-014.9 | CA-014.6 | borde | usuario en México | evento VE | descartado por radio | `[VERIFY: tests/test_filter.py:40]` |

## Dependencias

- **Requiere**: HU-002 (patrón de poller), HU-003 (normalización y filtro)
- **Habilita**: cobertura local; ninguna HU depende de ésta

## Notas para la v2

El *seen-set* no se persiste, y es correcto: la siembra del primer sondeo cumple la misma función
tras reiniciar. El endpoint es HTTP sin TLS válido; aceptado por ser público y de solo lectura,
pero conviene reevaluarlo si FUNVISIS publica HTTPS.
