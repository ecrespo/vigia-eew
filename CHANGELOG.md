# Changelog

Todas las versiones siguen [Versionado Semántico](https://semver.org/lang/es/) (`MAYOR.MENOR.PARCHE`).
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Ver el procedimiento
de publicación en `packaging/RELEASING.md`.

## [Unreleased]

### Changed
- **Breaking**: the entire codebase (source, tests, docs) and `config.toml` are now in
  English (RNF-10 updated). Every Python identifier, module filename, and TOML
  key/section was renamed (e.g. `[referencia]` → `[reference]`, `magnitud_minima` →
  `min_magnitude`, `[fuentes.emsc]` → `[sources.emsc]`, `[notificacion]` →
  `[notification]`, etc. — see `config.toml.example` for the full new schema).
  Existing `config.toml` files must be rewritten with the new keys.

### Added
- Headless TUI dashboard (`--tui`, RF-36): an alternative terminal frontend to the
  desktop GUI + tray icon, for running the agent on a server over SSH with no display.
  Shows the live WS connection status and a log of recent alerts, and presents each
  relevant event as a **non-dismissable** modal inside the terminal (only ENTER
  acknowledges it; Escape is disabled — same contract as RF-19). Keys: `p`
  pause/resume, `q` quit. Combinable with `--simulate` (`--simulate --tui`). No toast or
  tray icon in this mode. New module `tui.py` (built on `textual`) and
  `Application.run_tui()`.
- Internationalization (i18n, RF-35): user-facing text (alert window, toast, tray menu)
  is now translated based on `[notification] language` (`"auto"` detects the OS locale,
  or set `"en"`/`"es"` explicitly). Falls back to English for unsupported locales.
  New module `i18n.py`.

## [Sin publicar]

### Agregado
- Ícono de bandeja del sistema (RF-34): menú con estado (WS conectado/reconectando,
  última alerta), pausar/reanudar notificaciones (sin perder eventos, solo retrasa su
  presentación), editar `config.toml` con la app asociada del SO, y salir. Nuevo toggle
  `[notificacion] icono_bandeja` (default `true`). Mejor esfuerzo: si el backend gráfico
  no está disponible (GNOME/Wayland sin extensión de bandeja, macOS sin validar, etc.),
  el agente sigue funcionando normalmente sin el ícono. No se activa en `--simulate`.
  Nuevas dependencias: `pystray` + `Pillow` (excepción documentada a RNF-06).

### Corregido
- La línea "Hora local (Venezuela): ..." de la ventana de alerta se recortaba contra el
  borde (se veía la fecha, pero la hora quedaba cortada). Causa: el `Label` de detalle no
  tenía `wraplength`, así que una línea más ancha que la ventana (fija, no redimensionable
  por RF-15) se dibujaba fuera del área visible en vez de bajar de línea. Se agregó
  `wraplength` acorde al ancho real de la ventana (fijo o pantalla completa) en
  `notify/alert_window.py`.
- Tras el fix anterior, el contenido podía quedar recortado contra el **borde inferior**
  en máquinas con otras métricas de fuente/DPI: el alto de la ventana era un número fijo
  (620px) que no reflejaba lo que el contenido realmente necesitaba. Ahora el alto se mide
  con `winfo_reqheight()` después de empaquetar el contenido (en la pantalla real del
  usuario) y la ventana se dimensiona a ese valor (con un piso visual de 620px), en vez de
  adivinar una constante.

## [0.1.3] - 2026-07-04

### Agregado
- Detección automática del punto de referencia geográfico por geolocalización de IP
  (`geoloc.py`, RF-33) cuando el usuario no define `[referencia]` en `config.toml`. Se
  detecta una sola vez y se cachea en `state.json`; si falla (sin red, timeout, etc.) se
  usa el default (Caracas) sin bloquear el arranque. No se activa en `--simulate` (RF-21
  sigue funcionando sin red).
- `config.toml.example` documenta cómo bajar `magnitud_minima` a un umbral más estricto
  (ej. `3.0`) y cómo desactivar la detección automática fijando `[referencia]` a mano.

### Corregido
- El `.deb` instalado (release v0.1.2) fallaba al arrancar con
  `ModuleNotFoundError: No module named 'desktop_notifier.resources'`. Causa:
  `desktop_notifier.common` carga su ícono default con
  `importlib.resources.files("desktop_notifier.resources")` — una referencia dinámica
  por nombre de módulo que el análisis estático de PyInstaller no detecta, así que ese
  subpaquete (con `python.png`) quedaba fuera del binario. Se agregó
  `collect_data_files("desktop_notifier")` a `datas` y `desktop_notifier.resources` a
  `hiddenimports` en `packaging/vigia-eew.spec`. Verificado localmente: el binario
  onefile de Linux reconstruido ya no lanza el error y llega a mostrar la alerta con
  `--simulate`.

## [0.1.2] - 2026-07-04

### Corregido
- El PNG 1x1 introducido en 0.1.1 era una imagen válida pero de una resolución que
  `linuxdeploy` rechaza (exige una de la lista fija 8x8..512x512). Se reemplaza por
  un PNG **64x64** sólido generado con la stdlib de Python (`struct`+`zlib`, sin
  depender de Pillow). Detectado en el run de CI del tag `v0.1.1`.

## [0.1.1] - 2026-07-04

### Corregido
- `packaging/build_linux.sh` generaba un ícono placeholder **vacío** para el AppImage,
  lo que hacía fallar a `linuxdeploy` (CImg no puede decodificar un archivo de 0 bytes
  como PNG). Se reemplazó por un PNG 1x1 transparente válido. Detectado en el primer
  run real de `.github/workflows/build.yml` (tag `v0.1.0`): PyPI, Windows y macOS
  construyeron bien; solo falló el job de Linux.

## [0.1.0] - 2026-07-04

### Agregado
- Núcleo del agente: ingestión EMSC (WebSocket, push primario) + USGS (REST, respaldo),
  pipeline de normalización/filtro/deduplicación, notificación (ventana no descartable,
  toast, sonido por severidad) y persistencia de estado (Fases 1–4).
- CLI (`vigia-eew`), ensamblaje del agente y modo `--simulate` (Fase 5).
- Autoarranque multiplataforma: systemd `--user` (Linux), LaunchAgent (macOS), tarea
  programada (Windows) vía `--install-autostart`/`--uninstall-autostart` (Fase 6).
- Verificación de resiliencia end-to-end y validación real de `--simulate` en Linux (Fase 7).
- Empaquetado: build de PyPI (wheel/sdist), especificación PyInstaller y scripts de build
  por SO, workflow de CI/CD con matriz de release (Fase 8).

[Sin publicar]: https://github.com/ecrespo/vigia-eew/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/ecrespo/vigia-eew/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/ecrespo/vigia-eew/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/ecrespo/vigia-eew/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ecrespo/vigia-eew/releases/tag/v0.1.0
