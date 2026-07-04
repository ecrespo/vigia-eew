# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es esto

Vigía-eew (`vigia-eew`) es un agente de escritorio (Python 3.11+, `src/` layout) que monitorea
sismos en tiempo real (WebSocket EMSC como vía primaria, polling REST USGS como respaldo) y muestra
una alerta de escritorio **no descartable** cuando un evento cae dentro del radio/magnitud
configurados. Proceso único por máquina, sin punto único de fallo (cada máquina corre su propio
agente).

## Comandos

```bash
uv venv && uv pip install -e ".[dev]"   # setup (recomendado); o: pip install -e ".[dev]"

pytest                                  # suite completa
PYTHONPATH=src pytest -q                # si el paquete no está instalado editable
pytest tests/test_dedup.py::test_x -q   # un solo test
VIGIA_GUI_TESTS=1 pytest                # incluye los smokes de Tkinter real (opt-in, requiere display)

ruff check .                            # lint (line-length 100, reglas E,F,I,UP,B)
mypy src                                # type check (strict = true)

vigia-eew --help
vigia-eew --simulate                    # inyecta un sismo simulado (M6.1 La Guaira) sin red
vigia-eew --check-config                # valida config.toml y sale
vigia-eew --install-autostart           # instala autoarranque (systemd/LaunchAgent/tarea) y sale
```

Gate de calidad antes de dar por cerrada una tarea: `pytest`, `ruff check .`, `mypy src` — los tres
en verde.

## Arquitectura

**Un solo proceso asyncio** por máquina. Dos ingestas alimentan una `raw_queue` común:

- `ingest/ws_emsc.py` (`WSIngestor`): WebSocket EMSC, **vía primaria**, keepalive de 15 s, reconexión
  con backoff exponencial + jitter (`backoff.py`, compartido con el supervisor).
- `ingest/rest_usgs.py` (`RESTReconciler`): polling USGS cada 60 s con **cursor persistido**, solo
  reconcilia lo que el WS pudo perder; no compite con el push.

Un `pipeline/procesador.py` (`Procesador`) consume `raw_queue` y encadena
`pipeline/normalize.py` → `pipeline/filtro.py` → `pipeline/dedup.py`:

- **Normalize**: mapea el crudo de cada fuente al contrato interno único `SeismicEvent`
  (`models.py`), calcula distancia (`geo.py::haversine_km`) y severidad.
- **Filtro**: descarta por radio o magnitud mínima (config).
- **Dedup**: dedup intra-fuente por id, heurística inter-fuente (≤100 km, ≤90 s, ≤0.5 mag) y manejo
  de `update` de EMSC (actualiza el evento en curso en vez de re-alertar). IDs y firmas recientes se
  persisten en `state.py` (`StateStore`, JSON atómico vía `platformdirs`).

`supervisor.py` (`Supervisor`) orquesta las tasks asyncio (`ws`, `rest`, `pipeline`) y **reinicia
cada una con backoff si falla**, sin tumbar el proceso — nunca debe morir por un fallo transitorio
de red o parseo.

Eventos nuevos/relevantes llegan a `notify/` (`ControladorAlertas` en `controlador.py`), que
orquesta tres efectos como **callbacks inyectables** (para poder testear sin I/O real):
`crear_ventana` (Tkinter no descartable, topmost, `alert_window.py`), `reproducir_sonido`
(`sound.py`, por severidad) y `enviar_toast` (`toast.py`, `desktop-notifier`). `queue.py` mantiene
**una alerta a la vez** y actualiza in-place ante un `update`.

**Puente asyncio↔Tkinter** (`app.py`, ADR-006 en `docs/TECHNICAL-DESIGN.md`): Tkinter exige correr
en el hilo principal, la ingestión vive en asyncio en un hilo de trabajo aparte. `PuenteAsyncioTk`
(en `notify/queue.py`) cruza los eventos entre ambos vía cola thread-safe + `widget.after()`.
`Aplicacion` (`app.py`) cablea todo esto; expone `ejecutar()` (agente completo) y `simular()`
(inyecta el evento de `simulacion.py` sin red, para `--simulate`).

`autostart/` instala/desinstala el arranque automático por SO (systemd `--user` en Linux,
LaunchAgent en macOS, tarea programada en Windows), invocado desde `cli.py` vía
`--install-autostart`/`--uninstall-autostart`.

### Patrón de testing recurrente

Inyectar dependencias (`connect`/`sleep`/`client`/`runner`/`crear_ventana`/etc.) y separar la
**lógica pura** (generación de comando/unit/plist, formato, cálculo) del **efecto de sistema**
(red, Tkinter real, systemctl/launchctl/schtasks, audio). Los tests de GUI real están marcados
`skipif` salvo `VIGIA_GUI_TESTS=1`; la suite por defecto corre headless.

## Desarrollo dirigido por specs (SDD)

El proyecto se construye **fase por fase** siguiendo `docs/IMPLEMENTATION-PLAN.md`, que enlaza
`docs/PRD.md` (requisitos RF-xx/RNF-xx), `docs/API-SPEC.md` (contratos EMSC/USGS/interno),
`docs/TECHNICAL-DESIGN.md` (ADRs numerados) y `docs/DATA-MODEL.md`. `ARCHITECTURE.md` tiene los
diagramas Mermaid (flujo de datos, secuencia, estados, despliegue). Si se agrega un módulo no
listado en `IMPLEMENTATION-PLAN.md`, esa sección (estructura + tabla de fase + matriz RF→módulo)
se actualiza junto con el código.

Convención de commits: uno por fase completada (`feat:`/`docs:` conventional, cuerpo describiendo
qué se agregó y por qué), terminando en un trailer `Co-Authored-By:` con el modelo que lo generó
(ver `git log`).

## Convenciones

- **Español** en código, docstrings, comentarios, mensajes de commit y artefactos (RNF-10).
- Todo `datetime` interno es **tz-aware en UTC** (`models.py` lo valida y rechaza *naive*); la
  conversión a hora local (`America/Caracas`) ocurre solo en `notify/presentacion.py`.
- Contrato interno (`SeismicEvent`) es el único payload que cruza capas — ver `API-SPEC.md` §3 para
  el mapeo de campos EMSC/USGS y las invariantes (distancia y severidad son siempre derivadas).