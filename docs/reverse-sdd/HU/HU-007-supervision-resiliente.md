# HU-007: Supervisión resiliente de tareas asyncio

> **Cluster de origen:** Fase 2 + Fase 7 · **Commits:** 2 `[COMMITS: fc0ca99, f49d139]`
> **Período:** 2026-06-28 → 2026-07-03 · **Era:** Era 0 — Fundación

## Historia

**Como** usuario que deja el agente corriendo en segundo plano durante semanas `[INFERIDO: los commits describen capacidades, no personas]`
**Quiero** que ningún fallo transitorio de red o de parseo mate el proceso
**Para** no quedar sin cobertura sísmica creyendo que estoy protegido

## Contexto de la implementación original

`Supervisor` `[VERIFY: src/vigia_eew/supervisor.py:28]` corre las cinco tareas de larga
vida (`ws`, `rest`, `geofon`, `funvisis`, `pipeline`) y reinicia con backoff la que falle,
sin tumbar el proceso `[VERIFY: src/vigia_eew/supervisor.py:80]`. Es la decisión de
resiliencia que sostiene todo lo demás: **un agente de seguridad que muere en silencio es
peor que no tener agente**, porque el usuario cree estar cubierto.

Instala manejadores de SIGINT/SIGTERM para un apagado limpio
`[VERIFY: src/vigia_eew/supervisor.py:109]` y comparte el cálculo de backoff con el
ingestor WS `[VERIFY: src/vigia_eew/backoff.py:18]`.

## Criterios de aceptación

### CA-007.1: Todas las tareas registradas arrancan
```gherkin
Dado varias tareas registradas en el supervisor
Cuando se ejecuta run()
Entonces todas se inician
```
*Fuente: test `[VERIFY: tests/test_supervisor.py:10]`*

### CA-007.2: Una tarea que falla se reinicia con backoff
```gherkin
Dado una tarea que lanza una excepción
Cuando el supervisor la detecta
Entonces la registra y la reinicia tras una espera creciente
```
*Fuente: test `[VERIFY: tests/test_supervisor.py:30]`*

### CA-007.3: El fallo de una tarea no afecta a las demás
```gherkin
Dado una tarea que falla repetidamente y otra sana
Cuando el supervisor gestiona el fallo
Entonces la tarea sana sigue corriendo sin interrupción
```
*Fuente: test `[VERIFY: tests/test_supervisor.py:53]` — aislamiento entre fuentes: una
caída de FUNVISIS no debe afectar la cobertura de EMSC*

### CA-007.4: La parada limpia cancela las tareas vivas
```gherkin
Dado el supervisor corriendo
Cuando se solicita la parada
Entonces todas las tareas se cancelan ordenadamente
```
*Fuente: test `[VERIFY: tests/test_supervisor.py:81]`*

### CA-007.5: El backoff crece y satura en un tope
```gherkin
Dado reintentos sucesivos
Cuando se calcula la espera
Entonces crece exponencialmente y no supera el tope configurado
```
*Fuente: tests `[VERIFY: tests/test_backoff.py:10]`,
`[VERIFY: tests/test_backoff.py:18]`*

### CA-007.6: El jitter mantiene la espera entre la mitad y el valor completo
```gherkin
Dado el backoff con jitter activado
Cuando se calcula la espera
Entonces queda entre la mitad y el valor nominal, sin superar el tope
```
*Fuente: tests `[VERIFY: tests/test_backoff.py:24]`,
`[VERIFY: tests/test_backoff.py:32]` — sin jitter, todas las instancias reconectarían
en lockstep tras una caída compartida*

### CA-007.7: Un número de intento inválido se rechaza
```gherkin
Dado un número de intento negativo o cero
Cuando se calcula el backoff
Entonces falla explícitamente
```
*Fuente: test `[VERIFY: tests/test_backoff.py:37]`*

### CA-007.8: El ingestor supervisado sobrevive una caída real end-to-end
```gherkin
Dado el WSIngestor real bajo el supervisor real
Cuando la conexión se cae
Entonces sigue entregando mensajes tras reconectar
```
*Fuente: test `[VERIFY: tests/test_resilience.py:186]` — añadido en la Fase 7
`[COMMITS: f49d139]`, es la validación integrada de toda esta HU*

## Casos de prueba

| ID | Criterio | Tipo | Escenario | Datos de entrada | Resultado esperado | ¿Test existente? |
|---|---|---|---|---|---|---|
| TC-007.1 | CA-007.1 | feliz | 3 tareas | registradas | Todas arrancan | `[VERIFY: tests/test_supervisor.py:10]` |
| TC-007.2 | CA-007.2 | negativo | Tarea que lanza | excepción | Reinicio con backoff | `[VERIFY: tests/test_supervisor.py:30]` |
| TC-007.3 | CA-007.3 | borde | Una falla, otra sana | mixto | Aislamiento | `[VERIFY: tests/test_supervisor.py:53]` |
| TC-007.4 | CA-007.4 | feliz | Parada solicitada | stop | Cancelación limpia | `[VERIFY: tests/test_supervisor.py:81]` |
| TC-007.5 | CA-007.5 | feliz | Secuencia sin jitter | 1..n | 1,2,4,8… | `[VERIFY: tests/test_backoff.py:10]` |
| TC-007.6 | CA-007.5 | borde | Muchos intentos | n grande | Satura en el tope | `[VERIFY: tests/test_backoff.py:18]` |
| TC-007.7 | CA-007.6 | borde | Jitter acotado | con jitter | Entre mitad y total | `[VERIFY: tests/test_backoff.py:24]` |
| TC-007.8 | CA-007.7 | negativo | Intento inválido | 0 o -1 | Error | `[VERIFY: tests/test_backoff.py:37]` |
| TC-007.9 | CA-007.8 | borde | Caída real end-to-end | drop del WS | Sigue entregando | `[VERIFY: tests/test_resilience.py:186]` |
| TC-007.10 | CA-007.2 | negativo | Tarea que falla al arrancar siempre | fallo inmediato en bucle | No satura CPU ni acumula tareas huérfanas | **escribir en v2** |

## Dependencias

- **Requiere**: HU-005, HU-006 (las tareas que supervisa)
- **Habilita**: HU-013, HU-019, HU-021, HU-022

## Notas para la v2

Mantener tal cual — es el componente más barato y de mayor retorno del sistema. TC-007.10
es el hueco: no hay test del caso patológico "la tarea falla inmediatamente y para
siempre", donde un backoff mal acotado podría convertirse en un bucle caliente.
