# Implementation Plan — Vigía-eew

| Campo | Valor |
|---|---|
| Documento | Plan de implementación por fases, dependencias y trazabilidad |
| Versión | 1.0 (borrador para revisión) |
| Estado | 🟡 Pendiente de aprobación |
| Relacionado | `PRD.md`, `TECHNICAL-DESIGN.md`, `DATA-MODEL.md`, `API-SPEC.md`, `ARCHITECTURE.md` |

> Orden **estricto** por capas (alineado con el plan de trabajo del proyecto): SDD → estructura →
> ingestión → dedup/filtro → notificación → autoarranque → verificación `--simulate` → empaquetado/CI.
> **Puerta de fase**: la Fase 0 (este conjunto de artefactos) debe aprobarse **antes** de codificar.

---

## 1. Estructura de proyecto propuesta

```
vigia-eew/
├── pyproject.toml              # uv + hatchling, deps, entry point `vigia-eew`
├── README.md
├── ARCHITECTURE.md
├── config.toml.example
├── docs/                       # artefactos SDD (este conjunto)
│   ├── PRD.md
│   ├── API-SPEC.md
│   ├── TECHNICAL-DESIGN.md
│   ├── DATA-MODEL.md
│   └── IMPLEMENTATION-PLAN.md
├── src/vigia_eew/
│   ├── __init__.py
│   ├── cli.py                  # entry point, flags, --simulate
│   ├── config.py               # Settings (pydantic) + carga config.toml
│   ├── models.py               # SeismicEvent, AppState, firmas
│   ├── geo.py                  # haversine_km (compartido por normalize y dedup)
│   ├── backoff.py              # exponential_backoff (compartido por ws_emsc y supervisor)
│   ├── supervisor.py           # orquestador asyncio (tasks + watchdog)
│   ├── ingest/
│   │   ├── __init__.py         # RawMessage (envoltorio crudo fuente→pipeline)
│   │   ├── ws_emsc.py          # WSIngestor (keepalive, reconexión)
│   │   └── rest_usgs.py        # RESTReconciler (poll 60 s, cursor)
│   ├── pipeline/
│   │   ├── __init__.py         # docstring del pipeline
│   │   ├── normalize.py        # Normalizer (mapeo por fuente, geo.haversine_km, severidad)
│   │   ├── filtro.py           # GeoFilter (radio + magnitud, límites inclusivos)
│   │   └── dedup.py            # Deduplicator (nuevo/actualizar/duplicado)
│   ├── notify/
│   │   ├── __init__.py         # docstring de la capa de notificación
│   │   ├── presentacion.py     # formato legible + color por severidad (puro)
│   │   ├── toast.py            # desktop-notifier (urgencia por severidad)
│   │   ├── alert_window.py     # ventana Tkinter no descartable + política
│   │   ├── queue.py            # AlertQueue + puente asyncio↔Tk
│   │   └── sound.py            # capa de audio por severidad
│   ├── state.py                # StateStore (JSON atómico, platformdirs)
│   ├── logging_conf.py         # logging estructurado + rotativo
│   └── assets/                 # info.wav / atencion.wav / critico.wav (generados)
├── autostart/
│   ├── linux_systemd.py        # instalar/desinstalar systemd --user
│   ├── macos_launchagent.py    # LaunchAgent plist
│   └── windows_task.py         # tarea programada (schtasks)
├── packaging/
│   ├── build_linux.sh          # AppImage + .deb/.rpm (fpm)
│   ├── build_windows.ps1       # PyInstaller onefile (.exe)
│   ├── build_macos.sh          # .app → .dmg (codesign/notarize doc)
│   ├── vigia-eew.spec          # PyInstaller spec
│   └── apt-r2/                 # doc/utilidades repo apt en Cloudflare R2
├── tests/
└── .github/workflows/build.yml # matriz windows/macos/ubuntu → release assets
```

## 2. Fases, tareas y dependencias

### Fase 0 — SDD (este conjunto) · 🟡 puerta de aprobación
| ID | Tarea | Depende de | Entregable |
|---|---|---|---|
| F0-1 | PRD, API Spec, Technical Design, Data Model, Implementation Plan | — | `docs/*.md` |
| F0-2 | `ARCHITECTURE.md` con diagramas Mermaid | F0-1 | `ARCHITECTURE.md` |
| F0-3 | **Revisión y aprobación** | F0-1, F0-2 | ✅ luz verde para codificar |

### Fase 1 — Estructura + modelo de datos
| ID | Tarea | Depende de | RF |
|---|---|---|---|
| F1-1 | `pyproject.toml` (uv/hatchling, deps, entry point) | F0-3 | RF-26, RF-27 |
| F1-2 | `models.py` (`SeismicEvent`, `AppState`, firmas) | F1-1 | RF-07 |
| F1-3 | `config.py` + `config.toml.example` | F1-1 | RF-24, RF-12 |
| F1-4 | `logging_conf.py` (consola + rotativo) | F1-1 | RF-25 |
| F1-5 | `state.py` (JSON atómico, platformdirs) | F1-2 | RF-06, RF-10 |
| F1-6 | `geo.py` (`haversine_km`, compartido por normalize y dedup) | F1-1 | RF-08 |

### Fase 2 — Ingestión (push primario + respaldo)
| ID | Tarea | Depende de | RF |
|---|---|---|---|
| F2-0a | `backoff.py` (`exponential_backoff`, equal jitter, compartido por ws_emsc y supervisor) | F1-1 | RF-03, RNF-03 |
| F2-0b | `ingest/__init__.py` (`RawMessage`: envoltorio crudo fuente→pipeline) | F1-2 | RF-07 |
| F2-1 | `ws_emsc.py`: conexión, **keepalive 15 s**, **reconexión backoff** | F2-0a, F2-0b | RF-01, RF-02, RF-03, RF-04 |
| F2-2 | `rest_usgs.py`: poll 60 s, **cursor persistido**, manejo 429/5xx | F2-0b, F1-5 | RF-05, RF-06 |
| F2-3 | `supervisor.py`: tasks asyncio + reinicio con backoff + cierre limpio (SIGINT/SIGTERM) | F2-0a, F2-1, F2-2 | RNF-03, RNF-04 |

### Fase 3 — Normalización, filtro y dedup
| ID | Tarea | Depende de | RF |
|---|---|---|---|
| F3-1 | `normalize.py`: mapeo por fuente, severidad (usa `geo.haversine_km` de F1-6) | F2-*, F1-6 | RF-07, RF-08, RF-13 |
| F3-2 | `filtro.py`: radio + magnitud mínima | F3-1 | RF-12 |
| F3-3 | `dedup.py`: heurística inter-fuente, ids persistidos, `update` | F3-1, F1-5 | RF-09, RF-10, RF-11 |

### Fase 4 — Notificación (requisito central)
| ID | Tarea | Depende de | RF |
|---|---|---|---|
| F4-5 | `presentacion.py`: magnitud/lugar/distancia/profundidad/hora local/fuente + color (puro) | F3-1 | RF-18, RF-13, RNF-12 |
| F4-1 | `toast.py` con `desktop-notifier` (urgencia por severidad, fallo aislado) | F4-5 | RF-14 |
| F4-3 | `sound.py`: audio por severidad (insistencia creciente) + assets WAV | F4-5 | RF-17 |
| F4-2 | `alert_window.py`: Tkinter topmost, foco, no descartable, RECONOCIDO | F4-5 | RF-15..RF-19 |
| F4-4 | `queue.py`: cola (una a la vez) + `update` in-place + puente asyncio↔Tk (ADR-006) | F4-2 | RF-20, RF-11 |

### Fase 5 — CLI + modo simulación
| ID | Tarea | Depende de | RF |
|---|---|---|---|
| F5-1 | `cli.py`: arranque, `--config`, subcomandos | F1-3, F2-3, F4-* | RF-26 |
| F5-2 | `--simulate` (M6.1 La Guaira) | F4-*, F5-1 | RF-21 |

### Fase 6 — Autoarranque
| ID | Tarea | Depende de | RF |
|---|---|---|---|
| F6-1 | Linux systemd `--user` (instalar/desinstalar) | F5-1 | RF-22, RF-23 |
| F6-2 | macOS LaunchAgent (instalar/desinstalar) | F5-1 | RF-22, RF-23 |
| F6-3 | Windows tarea programada (instalar/desinstalar) | F5-1 | RF-22, RF-23 |

### Fase 7 — Verificación `--simulate` en los 3 SO
| ID | Tarea | Depende de | CA |
|---|---|---|---|
| F7-1 | Validar alerta no descartable + sonido en Linux | F5-2 | CA-01 |
| F7-2 | Validar en Windows | F5-2 | CA-01 |
| F7-3 | Validar en macOS (foco/topmost) | F5-2 | CA-01, ADR-003 |
| F7-4 | Pruebas de resiliencia (WS caído, 429, JSON inválido, reinicio) | F2-*, F3-* | CA-02..CA-07 |

### Fase 8 — Empaquetado y distribución
| ID | Tarea | Depende de | RF |
|---|---|---|---|
| F8-1 | PyPI (uv/hatchling), versionado semántico | F5-* | RF-27 |
| F8-2 | Windows `.exe` (PyInstaller onefile, sin consola) | F5-* | RF-28 |
| F8-3 | macOS `.app`→`.dmg` (+doc codesign/notarización) | F5-* | RF-29 |
| F8-4 | Linux AppImage + `.deb`/`.rpm` (fpm) + snap doc | F5-* | RF-30 |
| F8-5 | GitHub Actions matriz → release assets + scripts locales | F8-1..F8-4 | RF-31 |
| F8-6 | Doc repo apt en Cloudflare R2 | F8-4 | RF-32 |

## 3. Matriz de trazabilidad RF → componente

| RF | Componente(s) | Fase |
|---|---|---|
| RF-01..RF-04 | `ingest/ws_emsc.py`, `backoff.py` | F2 |
| RF-05, RF-06 | `ingest/rest_usgs.py`, `state.py` | F2 |
| RF-07 | `pipeline/normalize.py`, `models.py`, `ingest/__init__.py` (`RawMessage`) | F3/F2 |
| RF-08 | `geo.py` (`haversine_km`), `pipeline/normalize.py` | F1/F3 |
| RF-09, RF-10, RF-11 | `pipeline/dedup.py`, `geo.py`, `state.py` | F3 |
| RF-12 | `pipeline/filtro.py`, `config.py` | F3 |
| RF-13 | `pipeline/normalize.py`, `notify/sound.py`, `notify/presentacion.py` (color) | F3/F4 |
| RF-14 | `notify/toast.py`, `notify/presentacion.py` | F4 |
| RF-15..RF-19 | `notify/alert_window.py` | F4 |
| RF-18 | `notify/presentacion.py`, `notify/alert_window.py` | F4 |
| RF-20 | `notify/queue.py` | F4 |
| RF-21 | `cli.py` (`--simulate`) | F5 |
| RF-22, RF-23 | `autostart/*` | F6 |
| RF-24 | `config.py` | F1 |
| RF-25 | `logging_conf.py` | F1 |
| RF-26 | `cli.py`, `pyproject.toml` | F1/F5 |
| RF-27..RF-32 | `packaging/*`, `.github/workflows/build.yml` | F8 |

## 4. Estrategia de pruebas (resumen)

| Nivel | Foco | Cubre |
|---|---|---|
| Unitarias | normalización (mapeo EMSC/USGS), haversine, severidad, dedup heurística | RF-07..RF-13 |
| Integración | ingestión con servidor WS *fake* + respuestas USGS grabadas (fixtures) | RF-01..RF-06 |
| Resiliencia | inyección de fallos: cierre WS, 429/5xx, JSON inválido, reinicio | RNF-03, CA-02..CA-07 |
| Manual/E2E | `--simulate` en los 3 SO (alerta no descartable, foco, sonido) | CA-01 |

> Fixtures: usar los eventos reales verificados (M4.3 Morón, M4.5 Boca de Aroa) y el simulado M6.1.

## 5. Dependencias (stack)

| Dependencia | Uso | RF/ADR |
|---|---|---|
| `websockets` | WS EMSC (keepalive nativo) | RF-01/ADR-009 |
| `httpx` | REST USGS async | RF-05/ADR-009 |
| `pydantic` (v2) | validación modelos/config | RF-07/RF-24 |
| `desktop-notifier` | toast multiplataforma | RF-14 |
| Tkinter (stdlib) | ventana de alerta | RF-15/ADR-003 |
| `platformdirs` | rutas de estado/config | RF-06/RF-10 |
| `tomllib` (stdlib) | leer `config.toml` | RF-24/ADR-007 |
| `tzdata`/zoneinfo | hora America/Caracas | RF-18/RNF-12 |
| PyInstaller, fpm, linuxdeploy | empaquetado | RF-28..RF-30 |

## 6. Hitos y orden de entrega

1. **M0**: Fase 0 aprobada (puerta SDD). ← *estado actual*
2. **M1**: Fases 1–3 (núcleo: ingestión + pipeline) con pruebas unitarias/integración verdes.
3. **M2**: Fase 4–5 (notificación + `--simulate`) demostrable en Linux.
4. **M3**: Fase 6–7 (autoarranque + verificación en los 3 SO).
5. **M4**: Fase 8 (empaquetado + CI con release assets).
