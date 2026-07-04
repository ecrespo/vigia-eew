# Changelog

Todas las versiones siguen [Versionado Semántico](https://semver.org/lang/es/) (`MAYOR.MENOR.PARCHE`).
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Ver el procedimiento
de publicación en `packaging/RELEASING.md`.

## [Sin publicar]

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

[Sin publicar]: https://github.com/ecrespo/vigia-eew/compare/406cde0...HEAD
