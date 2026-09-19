# Data Model — Vigía-eew v2

> Versión 1.0 · 2026-09-06 · Complementa `docs/DATA-MODEL.md`.

## 1. Alcance

El modelo de datos de la v0.6.0 está especificado en [`docs/DATA-MODEL.md`](../../DATA-MODEL.md):
entidades, campos, tipos e invariantes. **Se hereda íntegro.** Aquí solo los cambios de la v2 y las
invariantes que se elevan de convención a requisito.

**No hay base de datos.** La persistencia es un único documento JSON escrito de forma atómica en la
ruta por sistema operativo. No hay migraciones de esquema en el sentido habitual, pero sí una
**migración de estado** entre versiones (§4).

## 2. Cambios en las entidades

### 2.1 `SeismicEvent` — campo nuevo

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `correlation_id` | `str` ULID, 26 caracteres | sí | Identifica el **sismo**; se hereda al deduplicar entre fuentes (API Spec §2) |

Todos los demás campos y sus invariantes se mantienen. `time_utc` sigue siendo tz-aware en UTC y
rechazando valores naive (Art. 4); `distance_km` y `severity` siguen siendo **derivados**, nunca
tomados del origen (REQ-PIP-001).

### 2.2 `AlertedId` — campo nuevo

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `correlation_id` | `str` ULID | sí | Permite reconstruir en los registros qué fuente reportó primero un sismo ya alertado |

### 2.3 `AppState` — sin cambios estructurales

Las cuatro colecciones se mantienen: `alerted_ids`, `recent_signatures`, cursores por fuente y
ubicación detectada. **El cambio es de garantía, no de forma**: la poda deja de ser una función
existente sin llamador y pasa a ser invariante verificada (REQ-CFG-003).

## 3. Invariantes elevadas a requisito

Estas ya eran ciertas en el código de la v0.6.0, pero ninguna estaba enunciada como invariante del
modelo. La v2 las hace verificables.

| # | Invariante | REQ | Verificación |
|---|---|---|---|
| INV-1 | Todo `datetime` persistido o en tránsito es tz-aware en UTC | Art. 4 | Validador de esquema que rechaza naive |
| INV-2 | `alerted_ids` y `recent_signatures` no contienen entradas anteriores a la ventana de retención tras cualquier escritura | REQ-CFG-003 | Test que registra con estado envejecido y comprueba el archivo |
| INV-3 | Los cursores por fuente son monótonos no decrecientes | REQ-CFG-004 | Test de retroceso |
| INV-4 | El archivo de estado es siempre un JSON válido y completo, o no existe | REQ-CFG-002 | Test de escritura atómica: nunca quedan temporales |
| INV-5 | Un `correlation_id` identifica un sismo, no un mensaje: dos eventos deduplicados comparten el suyo | REQ-OBS-002 | Test de deduplicación entre fuentes que compara el campo |
| INV-6 | El conjunto de vistos de la fuente local no se persiste | REQ-ING-005 | Ausencia del campo en el esquema de estado |

### Limitación conocida y aceptada de INV-2

Si el agente pasa un periodo largo **sin alertas nuevas**, no se poda nada hasta el siguiente
registro. Es inocuo —tampoco se añade nada— pero significa que el enunciado correcto es *"podado
siempre que crece"*, no *"siempre acotado"*. Se documenta aquí para que nadie construya sobre la
lectura fuerte. Origen: [HU-016](../../reverse-sdd/HU/HU-016-frescura-backlog-poda.md), notas para la v2.

## 4. Migración de estado v0.6.0 → v2

El estado persistido de la v0.6.0 **no tiene** `correlation_id` en sus `alerted_ids`.

| Situación | Comportamiento exigido |
|---|---|
| Estado de v0.6.0 presente | EL SISTEMA DEBERÁ cargarlo, asignar `correlation_id` nulo a las entradas antiguas y seguir operando |
| Entrada sin `correlation_id` | NO DEBERÁ impedir la comprobación de "ya alertado" — el id y la firma siguen siendo la clave |
| Estado ilegible | Arrancar vacío (REQ-CFG-002) |

**No se escribe migración con versionado de esquema:** el estado es un caché reconstruible cuyo
único propósito es evitar re-alertas dentro de una ventana de 24 h. Tratarlo como base de datos
sería sobreingeniería. **Consecuencia aceptada:** un downgrade a v0.6.0 ignora el campo nuevo, que
es exactamente el comportamiento deseado.

## 5. Datos que el sistema NO almacena

Se enuncia explícitamente porque acota la superficie de privacidad y seguridad (atributo 7 en verde):

- Ningún dato personal más allá de una coordenada aproximada obtenida por IP, **solo si** el usuario
  no configuró una manual.
- Ninguna credencial: las cuatro fuentes son públicas y de solo lectura.
- Ningún histórico sísmico: el estado retiene 24 h y solo identificadores y firmas, no eventos.

## 6. Índices y consultas

**No aplica.** No hay motor de consultas: el estado se carga entero en memoria al arrancar (unos
pocos KB tras la poda) y se consulta por pertenencia a conjunto. Si alguna vez la ventana de
retención creciera hasta hacer esto costoso, sería la señal para reconsiderar el almacenamiento —
no antes.

## 7. Constitution check

| Artículo | Cumplimiento |
|---|---|
| Art. 2 (nada se repite) | INV-2, INV-3, INV-4 y la migración §4 preservan la garantía de no re-alertar |
| Art. 4 (UTC) | INV-1, elevada de convención a invariante verificada |
| Art. 8 (gate) | Las seis invariantes tienen test asociado en [Tasks](06-TASKS.md) |

**Excepciones solicitadas:** ninguna.
