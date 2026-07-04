# Changelog

Todas las versiones siguen [Versionado Semántico](https://semver.org/lang/es/) (`MAYOR.MENOR.PARCHE`).
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Ver el procedimiento
de publicación en `packaging/RELEASING.md`.

## [Sin publicar]

### Agregado
- Detección automática del punto de referencia geográfico por geolocalización de IP
  (`geoloc.py`, RF-33) cuando el usuario no define `[referencia]` en `config.toml`. Se
  detecta una sola vez y se cachea en `state.json`; si falla (sin red, timeout, etc.) se
  usa el default (Caracas) sin bloquear el arranque. No se activa en `--simulate` (RF-21
  sigue funcionando sin red).
- `config.toml.example` documenta cómo bajar `magnitud_minima` a un umbral más estricto
  (ej. `3.0`) y cómo desactivar la detección automática fijando `[referencia]` a mano.

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

[Sin publicar]: https://github.com/ecrespo/vigia-eew/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/ecrespo/vigia-eew/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/ecrespo/vigia-eew/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ecrespo/vigia-eew/releases/tag/v0.1.0
