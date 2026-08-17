# Delta — Panel de configuración y selección de redes desde la bandeja

> Criterios en notación EARS. IDs continúan la serie del proyecto (`docs/PRD.md` llega
> hasta RF-42), en lugar de abrir una serie `REQ-` paralela: la trazabilidad existente
> vale más que la convención del skill.

## ADDED

### `docs/PRD.md` → 5. Requisitos funcionales

#### Panel de configuración (RF-43 … RF-47)

- **RF-43** *(evento)*: CUANDO el usuario seleccione "Configuración…" en el menú de la
  bandeja, EL SISTEMA DEBERÁ abrir un panel con los ajustes de uso común: radio de
  interés, magnitud mínima, umbrales de severidad, sonido, idioma, zona horaria, filtro
  de país y alcance temporal ("solo hoy").

- **RF-44** *(evento)*: CUANDO el usuario guarde cambios en el panel, EL SISTEMA DEBERÁ
  validarlos con el mismo modelo `Settings` que usa el arranque, y persistirlos en
  `config.toml` **conservando byte a byte los comentarios y las claves que el panel no
  gestiona**.

- **RF-45** *(no deseado)*: SI los valores introducidos no superan la validación,
  ENTONCES EL SISTEMA DEBERÁ rechazar el guardado, mostrar qué campo falla y **mantener
  intacta** la configuración vigente, tanto en memoria como en disco.

- **RF-46** *(evento)*: CUANDO se guarde una configuración válida que solo afecte a
  filtrado, severidad o presentación, EL SISTEMA DEBERÁ aplicarla al siguiente evento
  procesado **sin reiniciar** el agente.

- **RF-47** *(ubicuo)*: EL SISTEMA DEBERÁ indicar en el panel, de forma visible, qué
  ajustes requieren reinicio para surtir efecto, y no DEBERÁ dar por aplicado un cambio
  que aún no lo está.

#### Selección de redes sísmicas (RF-48 … RF-52)

- **RF-48** *(evento)*: CUANDO el usuario abra la sección de redes del panel, EL SISTEMA
  DEBERÁ listar todas las redes disponibles indicando, por cada una: nombre, cobertura
  geográfica, tipo de canal (push o sondeo) y si está activa.

- **RF-49** *(evento)*: CUANDO el usuario active o desactive una red y guarde, EL SISTEMA
  DEBERÁ persistir el cambio y avisar de que surtirá efecto al reiniciar el agente.

- **RF-50** *(no deseado)*: SI el usuario intenta desactivar la última red activa,
  ENTONCES EL SISTEMA DEBERÁ rechazar el cambio y explicar que el agente quedaría ciego.

- **RF-51** *(opcional)*: DONDE el usuario registre una red adicional compatible con
  `fdsnws-event`, EL SISTEMA DEBERÁ aceptarla indicando URL base y nombre, y tratarla como
  una fuente de sondeo con cursor persistido, igual que USGS y GEOFON.

- **RF-52** *(no deseado)*: SI una red registrada por el usuario no responde, responde con
  un formato inesperado o falla la validación de su URL, ENTONCES EL SISTEMA DEBERÁ
  aislarla como cualquier otra fuente —registrar el fallo y continuar— sin degradar la
  cobertura de las redes restantes.

### `docs/TECHNICAL-DESIGN.md` → 11. Decisiones de diseño (ADRs)

- **ADR-023 — Escritura quirúrgica de `config.toml`.** Reemplaza parcialmente a ADR-007
  ("`tomllib` es de solo lectura; escribir no hace falta en v1"). Decisión: escribir
  sustituyendo **solo el valor de las claves gestionadas**, localizadas por sección y
  nombre, sin reserializar el documento. Alternativas rechazadas: `tomli-w` (dependencia
  nueva y **destruye los comentarios**, que en este archivo explican decisiones reales) y
  escritor propio completo (mismo problema, más código).

- **ADR-024 — Poller FDSN genérico.** ADR-016 difirió unificar `RESTReconciler` y
  `GEOFONPoller` "hasta una tercera fuente FDSN". RF-51 **es** esa tercera fuente:
  se extrae un poller FDSN parametrizado por formato de respuesta (`geojson` | `text`), y
  USGS y GEOFON pasan a ser sus dos primeras instancias configuradas.

### `docs/DATA-MODEL.md` → 3. Configuración

- Nueva sección `[[sources.fdsn]]` (lista): `name`, `url`, `format` (`geojson`|`text`),
  `enabled`, `poll_interval_s`, `timeout_s`.
- `AppState` gana `cursor_fdsn_ms: dict[str, int]` — un cursor por red registrada,
  indexado por `name`, siguiendo el patrón de `cursor_usgs_ms`/`cursor_geofon_ms`.

## MODIFIED

### `docs/PRD.md` → RF-34 (ícono de bandeja)

- **Antes**: el menú ofrece pausar/reanudar, **editar la configuración** (abrir el archivo
  con la aplicación asociada), y salir.
- **Ahora**: el menú ofrece pausar/reanudar, **"Configuración…"** (abre el panel, RF-43),
  **"Abrir config.toml"** (comportamiento actual, conservado para las claves avanzadas), y
  salir.
- *Razón*: el acceso al archivo no se retira. Es la vía para lo que el panel no cubre y la
  válvula de escape si el panel falla (Art. 3).

### `docs/PRD.md` → RF-24 (configuración)

- **Antes**: la configuración se lee y valida al arrancar; el archivo se siembra desde
  plantilla en el primer arranque.
- **Ahora**: además, la configuración **puede escribirse** desde el panel, con la misma
  validación, preservando comentarios y claves no gestionadas.

### `docs/TECHNICAL-DESIGN.md` → ADR-007

- Se marca como **parcialmente reemplazado por ADR-023** en lo relativo a "escribir
  configuración no es necesario". El resto de ADR-007 (TOML + pydantic + uv + hatchling)
  sigue vigente.

### `docs/TECHNICAL-DESIGN.md` → ADR-016

- Se marca su condición diferida como **cumplida**: llega la tercera fuente FDSN, y la
  unificación pasa a ADR-024.

### `src/vigia_eew/config.py` → `Filter`, `Notification`, `Settings`

- `Settings` gana `sources.fdsn: list[FDSNSource]`. Sin cambios en las claves existentes;
  la adición es compatible hacia atrás.

## REMOVED

Nada. La propuesta es puramente aditiva: ninguna capacidad ni ningún RF se retira, y el
acceso directo al archivo se conserva.

## Criterios que NO se especifican aquí (y por qué)

- **Reconstruir las tareas de ingesta en caliente** al cambiar de red. Sería un cambio de
  arquitectura en el supervisor con riesgo alto y beneficio marginal frente a reiniciar un
  agente que arranca en menos de un segundo. RF-47 y RF-49 lo resuelven diciendo la verdad
  al usuario.
- **Editar umbrales de dedup, endpoints o intervalos de poll desde el panel.** Son ajustes
  que pueden degradar la cobertura sin que el usuario lo perciba; se quedan en el archivo,
  donde el acto de editarlos es deliberado.
- **Descubrimiento automático de redes FDSN** (p. ej. consultando el catálogo de FDSN).
  Añadiría una llamada de red y una lista que el producto no controla. Si se quiere, entra
  como propuesta propia con su ADR (ver `docs/features/NUEVAS-FUNCIONALIDADES.md`, F-09).
