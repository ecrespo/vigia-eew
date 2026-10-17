# Data Model delta — Vigía-eew v1.0

> Artefacto 05 del kit v1.0 · Documentos base: [`docs/DATA-MODEL.md`](../DATA-MODEL.md) y
> [`docs/sdd/specs/04-DATA-MODEL.md`](../sdd/specs/04-DATA-MODEL.md)

## 1. Alcance

**La v1.0 no cambia el modelo de datos del dominio.** El evento sísmico, el estado operativo y los
cursores de fuente conservan su forma. Lo que este delta describe es:

1. La **superficie de configuración** que el panel tiene que cubrir — medida, no estimada.
2. Los **archivos que la escritura de configuración introduce** y su ciclo de vida.
3. El **histórico de eventos**, que es el único almacén nuevo del producto.
4. Qué **no** cambia, y por qué conviene decirlo.

**El estado operativo sigue siendo JSON**, sin excepción: unos KB consultados por pertenencia y
podados a 24 h. Lo que la enmienda [E-05](00-ENMIENDAS-CONSTITUCION.md) añade es un almacén
**separado** para un problema distinto —consultar el pasado— y lo hace con SQLite, que es biblioteca
estándar y por tanto no añade dependencia.

---

## 2. Superficie de configuración

Medida sobre `src/vigia_eew/config.py` en `c3a2c29`, recorriendo el árbol de modelos.

| # | Sección | Campos | Contenido |
|---|---|---|---|
| 1 | `reference` | 3 | nombre, latitud, longitud del punto de referencia |
| 2 | `filter` | 5 | radio, magnitud mínima, filtro de país, país, solo hoy |
| 3 | `sources_emsc` | 5 | habilitada, url, intervalo y espera de latido, tope de reintento |
| 4 | `sources_usgs` | 4 | habilitada, url, intervalo de sondeo, espera |
| 5 | `sources_funvisis` | 4 | habilitada, url, intervalo de sondeo, espera |
| 6 | `sources_geofon` | 4 | habilitada, url, intervalo de sondeo, espera |
| 7 | `dedup` | 3 | distancia, ventana, diferencia de magnitud |
| 8 | `severity` | 2 | umbral informativo, umbral de aviso |
| 9 | `notification` | 5 | pantalla completa, zona horaria, sonido, ícono, idioma |
| 10 | `logging` | 4 | nivel, archivo, tamaño máximo, respaldos |
| | **Total** | **39** | |

> **Discrepancia registrada.** El backlog §4 dice *"51 campos repartidos en 10 secciones"*. El
> recuento programático da **39 campos hoja**; las 10 secciones sí coinciden. Se documenta aquí y en
> [08-ANALYZE §V-02](08-ANALYZE.md) en lugar de editar el backlog, que pertenece a otra tarea.

### 2.1 Lo que hace la superficie más difícil de lo que parece

Tres características que un panel genérico no resolvería solo, y que ADR-020 tiene que atender:

| Característica | Ejemplo | Qué exige |
|---|---|---|
| **Restricciones por campo** | El radio es mayor que cero; la latitud está entre −90 y 90 | Validación derivada del esquema, no reescrita |
| **Reglas entre campos** | El umbral informativo debe ser menor que el de aviso | Validación de sección, no de campo |
| **Valores de dominio cerrado** | Zona horaria, idioma (`auto`/`en`/`es`), nivel de registro | Lista desplegable, no texto libre — la excepción declarada de ADR-020 |

La segunda es la que hace insuficiente validar campo a campo, y por eso CA-108.4 existe como
criterio propio.

---

## 3. Archivos y su ciclo de vida

La escritura de configuración introduce dos archivos junto al que ya existe. Ninguno es un formato
nuevo: los tres son el mismo TOML.

| Archivo | Cuándo existe | Quién lo borra | Requisito |
|---|---|---|---|
| `config.toml` | Siempre tras el primer arranque | Nadie | REQ-CFG-005, 006 |
| `config.toml.bak` | Tras el primer guardado desde el panel | Se sobrescribe en cada guardado | REQ-CFG-010 |
| Temporal de escritura | Solo durante un guardado | El renombrado atómico | REQ-CFG-010 |

**El temporal nunca debe sobrevivir a un guardado.** Es el mismo criterio que ya rige el estado
`[VERIFY: src/vigia_eew/state.py:61]`, y CA-108.6 lo verifica: tras una interrupción no puede quedar
un temporal huérfano.

**Un solo respaldo, no un historial.** El archivo está pensado para versionarse con Git si al
usuario le importa el historial; duplicar esa función en el producto añadiría gestión de retención
para resolver un problema que ya tiene solución.

### 3.1 Huella de detección de cambio externo

| Dato | Para qué | Dónde vive |
|---|---|---|
| Marca de tiempo de modificación del archivo al cargarlo | Comparar antes de escribir (REQ-CFG-011) | **En memoria**, en la sesión del panel |

**No se persiste**, y esa es la decisión: persistirla obligaría a mantenerla coherente entre
ejecuciones sin ganar nada. El caso que protege —alguien edita el archivo mientras el panel está
abierto— vive enteramente dentro de una sesión del panel.

---

## 3bis. El histórico de eventos

Habilitado por la enmienda [E-05](00-ENMIENDAS-CONSTITUCION.md) y decidido en
[ADR-025](04-TECHNICAL-DESIGN-DELTA.md). **Es el único almacén nuevo del producto**, y convive con
el estado operativo sin sustituirlo.

| | Estado operativo | Histórico |
|---|---|---|
| Formato | JSON atómico | **SQLite** (biblioteca estándar) |
| Para qué | No repetir una alerta | Consultar el pasado |
| Se lee | En cada evento, en la ruta caliente | Cuando el usuario abre la vista |
| Poda | 24 h | Retención configurable |

### 3bis.1 Tabla `events`

Una fila por **llegada evaluada**, no por sismo: un sismo reportado por dos redes produce dos filas
enlazadas por su identificador de correlación.

| Columna | Tipo | Nulo | Qué es |
|---|---|---|---|
| `id` | INTEGER PK | no | Identificador de fila |
| `correlation_id` | TEXT | no | El de REQ-OBS-002. **Une las llegadas del mismo sismo** |
| `source` | TEXT | no | Red de origen |
| `source_event_id` | TEXT | no | Identificador en esa red |
| `occurred_at` | TEXT | no | Instante del sismo, **ISO-8601 UTC** |
| `recorded_at` | TEXT | no | Instante en que el agente lo evaluó, ISO-8601 UTC |
| `latitude`, `longitude` | REAL | no | Epicentro |
| `depth_km` | REAL | **sí** | No todas las fuentes la publican |
| `magnitude` | REAL | no | |
| `region` | TEXT | sí | Descripción textual de la fuente |
| `distance_km` | REAL | no | Al punto de referencia **vigente en ese momento** |
| `severity` | TEXT | sí | Solo si fue alertado |
| `verdict` | TEXT | no | `alerted` o `discarded` |
| `reason` | TEXT | sí | Motivo del descarte: radio, magnitud, país, frescura, duplicado |
| `superseded_by` | INTEGER | sí | Fila que prevaleció, cuando `reason = 'duplicate'` |

**Clave de unicidad:** `(source, source_event_id)`. Una actualización de la misma fuente sobre el
mismo evento **reemplaza la fila** en lugar de añadir otra — el mismo criterio que ya rige el
tratamiento de actualizaciones en el deduplicador.

**Tres decisiones de esta tabla que merecen justificación:**

| Decisión | Por qué |
|---|---|
| Instantes como **texto ISO-8601 UTC** | SQLite no tiene tipo de fecha. En ISO-8601 con zulú, **el orden lexicográfico es el cronológico**, así que los índices y los rangos funcionan sin conversión. Y cumple Art. 4 sin excepciones |
| `distance_km` **almacenada**, no calculada al consultar | Es la distancia al punto de referencia **de ese momento**. Si el usuario se muda, el histórico debe seguir diciendo a qué distancia estaba entonces |
| `superseded_by` en vez de borrar el duplicado | Es lo que permite responder *"llegó por dos redes, y prevaleció esta"*. Borrarlo perdería justo el dato que HU-105 quería conservar |

### 3bis.2 Índices

Cada índice responde a una consulta concreta de REQ-HIS-005; ninguno está "por si acaso".

| Índice | Consulta que sirve |
|---|---|
| `occurred_at` | Rango de fechas — **la consulta principal**, y la del orden por defecto |
| `magnitude` | Filtro por magnitud mínima |
| `verdict` | Separar alertados de descartados |
| `correlation_id` | Reunir las llegadas de un mismo sismo |
| `(latitude, longitude)` | Recuadro geográfico del mapa |

**Sobre el índice geográfico, con honestidad:** un recuadro sobre un índice compuesto de dos reales
es menos eficiente que un índice espacial de verdad. Se elige así porque **el módulo R\*Tree de
SQLite es opcional** y no se puede dar por compilado en todos los intérpretes que el producto
empaqueta. Con los volúmenes de esta tabla la diferencia no es perceptible; si algún día lo fuera,
sería un cambio interno sin efecto en el esquema visible.

### 3bis.3 Versionado del esquema y migración

La versión vive en `PRAGMA user_version`, que es el mecanismo que SQLite ofrece para esto y no
requiere tabla propia. Al arrancar: si la versión del archivo es menor que la del código, se aplican
las migraciones en orden dentro de una transacción; si es mayor —el usuario abrió un archivo de una
versión más nueva— **el agente no lo toca y lo dice** en lugar de degradarlo (REQ-HIS-003).

### 3bis.4 Volumen y retención

Se registran **también los descartes**, y en un flujo global esos son bastantes más que las alertas.

| | |
|---|---|
| Orden de magnitud estimado | **Decenas de miles de filas al año**, del orden de decenas de MB |
| Confianza en esa cifra | **Baja: es una estimación, no una medición.** Depende de la sismicidad global y de qué publica cada red |
| Cómo se acota | Retención configurable con valor por defecto declarado (REQ-HIS-004) |
| Qué hacer al respecto | **Medir en el primer uso real** y ajustar el valor por defecto con el dato, no con la estimación |

Esa incertidumbre es precisamente la razón de que la retención sea configurable desde el principio en
lugar de fijarse en el código: es el parámetro que absorbe el error de la estimación.

### 3bis.5 Caché de teselas

| | |
|---|---|
| Dónde | Directorio de caché por plataforma, **fuera del directorio de estado** |
| Formato | Archivos de imagen, uno por tesela, indexados por nivel y coordenada |
| Por qué no en SQLite | Son binarios grandes y desechables; mezclarlos con el histórico haría el archivo del usuario mucho mayor sin ganar nada |
| Tamaño | Acotado, con desalojo de las menos usadas |
| Si se borra | No pasa nada: se vuelven a descargar. **Es caché, no datos** |

Estar en el directorio de caché y no en el de estado es lo que hace que un usuario —o el sistema
operativo— pueda borrarlo sin consecuencias.

---

## 4. Cambios heredados en las entidades del dominio

Ya especificados en el modelo de datos base, **sin implementar**. Se listan para que la fase 3 sepa
qué toca; su definición vive allí.

| Entidad | Cambio | Requisito | Fase |
|---|---|---|---|
| Evento sísmico | Campo de correlación | REQ-OBS-002 | F3 |
| Identificador alertado | Campo de correlación | REQ-OBS-002 | F3 |
| Estado de la aplicación | Sin cambios estructurales | — | — |

**Migración de estado: ninguna necesaria.** El campo de correlación es opcional en la lectura: un
archivo de estado escrito por la v0.6.0 se carga sin él y el agente arranca con normalidad. Es el
mismo criterio de tolerancia que ya aplica a un estado corrupto o ausente (REQ-CFG-002).

---

## 5. Datos que el sistema sigue sin almacenar

Conviene reafirmarlo porque la v1.0 añade una interfaz que **podría** invitar a lo contrario:

- **Ningún dato personal.** La ubicación de referencia es un punto que el usuario elige o que se
  deduce una vez por IP; no se envía a ninguna parte después.
- **Ninguna telemetría.** El identificador de correlación es diagnóstico local (invariante I-4 de la
  API Spec delta), verificado por CA-105.5.
- **Ninguna credencial.** Ninguna fuente la requiere, y el proveedor de teselas tampoco.
- **Nada del histórico sale del equipo** (REQ-HIS-006): sin sincronización, sin respaldo remoto, sin
  telemetría.

**Lo que sí cambia respecto de la v0.6.0, dicho claramente:** hasta ahora el agente olvidaba todo a
las 24 horas. A partir de la v1.0 **conserva un histórico local** de los eventos evaluados durante
el periodo de retención configurado. Es un archivo en el equipo del usuario, bajo su control, que
puede borrar sin que el agente deje de funcionar.

**Y lo que el mapa introduce**, que es lo único que este delta añade al lado de la red: mientras el
mapa está abierto, el proveedor de teselas **puede inferir aproximadamente qué zona mira el
usuario**. Acotado por la caché y por ser bajo demanda; declarado en REQ-MAP-001 y en la enmienda
[E-06](00-ENMIENDAS-CONSTITUCION.md). No es telemetría —no se envía nada *sobre* el usuario— pero
tampoco es nada, y por eso está escrito.

## 6. Constitution check

| Artículo | Cómo lo cumple |
|---|---|
| Art. 1 (la alerta es el producto) | El histórico se escribe **fuera del camino de presentación**; un fallo suyo no impide una alerta (REQ-HIS-002) |
| Art. 3 (fail-safe) | El respaldo y el temporal protegen la configuración; sin teselas el listado sigue funcionando |
| Art. 4 (UTC) | Los instantes del histórico se almacenan en ISO-8601 UTC, donde el orden lexicográfico es el cronológico |
| Stack: persistencia | Los tres archivos de configuración son el mismo TOML. El histórico usa SQLite **por enmienda E-05**, y el estado operativo sigue en JSON sin excepción |
