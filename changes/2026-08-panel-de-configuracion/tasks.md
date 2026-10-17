# Tasks — Panel de configuración y selección de redes

> Specs de origen: `proposal.md`, `delta-spec.md` (RF-43 … RF-52), `specs/constitution.md`
> Generado: 2026-08-16 · Estados: `[ ]` pendiente · `[~]` en curso · `[x] fecha` hecha ·
> `[!]` bloqueada

## Orden de ejecución sugerido

Las tres primeras tareas son la primera tanda: escriben y validan la **escritura de
configuración**, que es la pieza de la que todo lo demás depende y la única con riesgo
real de pérdida de datos del usuario. Revisar antes de escalar.

## Tareas

### T-001 · Escritor quirúrgico de `config.toml`
- **Qué**: función pura que, dado el texto del archivo, una sección, una clave y un valor
  nuevo, devuelve el texto con **solo ese valor sustituido** — comentarios, orden y claves
  no gestionadas intactos byte a byte. Si la clave no existe, la añade al final de su
  sección; si la sección no existe, la crea.
- **REQ**: RF-44 · **ADR**: ADR-023
- **Archivos**: `src/vigia_eew/config_writer.py`, `tests/test_config_writer.py`
- **Depende de**: —
- **Done**: round-trip sobre `config.toml.example` cambiando `radius_km` → el diff es
  exactamente una línea; todos los comentarios se conservan.

### T-002 · Guardado transaccional y validado
- **Qué**: `save_settings(path, changes)` que aplica T-001 sobre una copia temporal, la
  valida con `load_config`, y solo entonces hace `os.replace`. Ante fallo de validación,
  no toca el archivo original.
- **REQ**: RF-44, RF-45 · **Constitución**: Art. 2
- **Archivos**: `src/vigia_eew/config_writer.py`, `tests/test_config_writer.py`
- **Depende de**: T-001
- **Done**: guardar un `radius_km` negativo deja el archivo original sin modificar y
  devuelve el error del campo.

### T-003 · Recarga en caliente de la configuración aplicable
- **Qué**: `Application.apply_settings(new)` que sustituye el objeto de configuración
  usado por `GeoFilter` y por la presentación. **No** toca las tareas de ingesta.
- **REQ**: RF-46, RF-47 · **Constitución**: Art. 6
- **Archivos**: `src/vigia_eew/app.py`, `tests/test_app.py`
- **Depende de**: T-002
- **Done**: test que cambia `min_magnitude` y comprueba que el **siguiente** evento se
  filtra con el valor nuevo, sin reiniciar nada.

--- *revisar aquí antes de continuar* ---

### T-004 · Modelo de red disponible [P]
- **Qué**: estructura que describe cada red para la UI: nombre, cobertura, tipo de canal,
  si está activa. Deriva de la configuración, sin hardcodear la lista en la vista.
- **REQ**: RF-48
- **Archivos**: `src/vigia_eew/networks.py`, `tests/test_networks.py`
- **Depende de**: —
- **Done**: devuelve las 4 redes con su metadato correcto a partir de un `Settings`.

### T-005 · Regla "no dejar el agente ciego" [P]
- **Qué**: validación que rechaza una configuración sin ninguna red activa.
- **REQ**: RF-50 · **Constitución**: Art. 2
- **Archivos**: `src/vigia_eew/config.py`, `tests/test_config.py`
- **Depende de**: —
- **Done**: desactivar las 4 redes falla la validación con mensaje explícito.

### T-006 · Panel de configuración (vista)
- **Qué**: diálogo Tkinter con los campos de RF-43, la fábrica inyectada como el resto de
  efectos. Marca visualmente los ajustes que exigen reinicio.
- **REQ**: RF-43, RF-47 · **Constitución**: Art. 3, Art. 6
- **Archivos**: `src/vigia_eew/notify/settings_panel.py`, `tests/test_settings_panel.py`
- **Depende de**: T-003
- **Done**: tests headless con dobles verifican los campos, el marcado de "requiere
  reinicio" y que un fallo al construir el panel no propaga.

### T-007 · Sección de redes dentro del panel
- **Qué**: lista de redes con su metadato y casilla de activación; aviso de reinicio al
  cambiar.
- **REQ**: RF-48, RF-49
- **Archivos**: `src/vigia_eew/notify/settings_panel.py`, `tests/test_settings_panel.py`
- **Depende de**: T-004, T-006
- **Done**: activar/desactivar persiste y muestra el aviso; la última red no se puede
  desactivar (T-005).

### T-008 · Entrada del menú de bandeja
- **Qué**: añadir "Configuración…" al menú, **conservando** "Abrir config.toml". El
  callback se reprograma al hilo de Tk con `root.after(0, ...)`.
- **REQ**: RF-43 · **Modifica**: RF-34
- **Archivos**: `src/vigia_eew/tray.py`, `src/vigia_eew/app.py`, `tests/test_tray.py`
- **Depende de**: T-006
- **Done**: el test del menú encuentra ambas entradas y verifica el salto de hilo.

--- *fin de la primera funcionalidad; la segunda continúa* ---

### T-009 · Poller FDSN genérico (unificación)
- **Qué**: extraer `FdsnPoller` parametrizado por formato (`geojson` | `text`) a partir de
  `RESTReconciler` y `GEOFONPoller`, que comparten cursor, piso de consulta, `Retry-After`
  y bucle. USGS y GEOFON pasan a ser instancias configuradas.
- **REQ**: RF-51 · **ADR**: ADR-024 · Cierra `code-audit` R-07 y `arch-eval` DEB-P3
- **Archivos**: `src/vigia_eew/ingest/fdsn.py`, `rest_usgs.py`, `rest_geofon.py`, sus tests
- **Depende de**: —
- **Done**: los 31 tests de `test_rest_usgs.py` y `test_rest_geofon.py` pasan sin cambios
  de comportamiento; `jscpd src --min-tokens 70` → 0 clones en `ingest/`.

### T-010 · Configuración de redes FDSN registradas
- **Qué**: `[[sources.fdsn]]` en el modelo, y `cursor_fdsn_ms: dict[str, int]` en
  `AppState`, con un cursor por nombre de red.
- **REQ**: RF-51 · **Data Model**: §3
- **Archivos**: `src/vigia_eew/config.py`, `src/vigia_eew/models.py`,
  `src/vigia_eew/state.py`, tests correspondientes
- **Depende de**: T-009
- **Done**: cargar un TOML con dos redes FDSN produce dos fuentes con cursores
  independientes que persisten por separado.

### T-011 · Cableado de redes registradas en el supervisor
- **Qué**: `_build_supervisor` registra una tarea por red FDSN activa.
- **REQ**: RF-51, RF-52 · **Constitución**: Art. 3
- **Archivos**: `src/vigia_eew/app.py`, `tests/test_app.py`
- **Depende de**: T-010
- **Done**: con dos redes registradas se crean dos tareas; si una falla siempre, la otra y
  las cuatro base siguen vivas.

### T-012 · Alta de red desde el panel
- **Qué**: formulario de nombre + URL + formato, con validación de URL y prueba de
  conexión **opcional y explícita** (nunca automática, Art. 7).
- **REQ**: RF-51, RF-52
- **Archivos**: `src/vigia_eew/notify/settings_panel.py`, tests
- **Depende de**: T-007, T-010
- **Done**: una URL inválida se rechaza sin guardar; una válida aparece en la lista tras
  reiniciar.

### T-013 · Actualizar specs, ADRs y capa de intención
- **Qué**: plegar el delta a `docs/PRD.md`, `DATA-MODEL.md` y `TECHNICAL-DESIGN.md`
  (ADR-023 y ADR-024, más las notas de reemplazo en ADR-007 y ADR-016); añadir la sección
  de `lat.md/` sobre por qué la escritura es quirúrgica; backlinks `# @lat:`.
- **REQ**: todos · **Constitución**: Art. 8
- **Depende de**: T-012
- **Done**: `lat check` en verde; `docs/PRD.md` llega hasta RF-52; la carpeta
  `changes/2026-08-panel-de-configuracion/` se marca como implementada.

## Matriz de trazabilidad

| REQ | Tareas | Test que lo verificará |
|---|---|---|
| RF-43 | T-006, T-008 | `test_settings_panel_shows_common_fields` |
| RF-44 | T-001, T-002 | `test_save_preserves_comments`, `test_save_is_atomic` |
| RF-45 | T-002 | `test_invalid_value_leaves_file_untouched` |
| RF-46 | T-003 | `test_hot_reload_applies_to_next_event` |
| RF-47 | T-006, T-007 | `test_panel_marks_restart_required` |
| RF-48 | T-004, T-007 | `test_lists_networks_with_metadata` |
| RF-49 | T-007 | `test_toggle_network_persists_and_warns` |
| RF-50 | T-005 | `test_cannot_disable_last_network` |
| RF-51 | T-009, T-010, T-011, T-012 | `test_registered_fdsn_source_polls_independently` |
| RF-52 | T-011, T-012 | `test_failing_registered_network_does_not_affect_others` |

Los 10 RF tienen ≥1 tarea y ≥1 test previsto. Ningún RF queda diferido.

## Riesgos de ejecución

| Riesgo | Mitigación |
|---|---|
| T-001 corrompe el `config.toml` de un usuario | Escritura atómica (T-002) + validación previa; el archivo original solo se reemplaza si la copia valida |
| T-009 es un refactor sobre 31 tests existentes | Hacerlo **sin cambiar comportamiento**: los tests actuales son la red. Si alguno necesita cambiar, es señal de que el refactor se pasó de alcance |
| El panel crece hasta convertirse en un editor TOML completo | El alcance está cerrado en la propuesta: lo avanzado se queda en el archivo |
