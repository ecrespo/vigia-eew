# PRD — Vigía-eew (Documento de Requisitos de Producto)

| Campo | Valor |
|---|---|
| Producto | **Vigía** (`vigia-eew`) — agente de alerta sísmica de escritorio |
| Versión del documento | 1.0 (borrador para revisión) |
| Estado | 🟡 Pendiente de aprobación (puerta de fase SDD) |
| Fecha | 2026-06-28 |
| Autor | Ernesto Crespo |
| Repositorio | https://github.com/ecrespo/vigia-eew |
| Metodología | Spec-Driven Development (las specs preceden al código) |

> Este PRD es el artefacto primario. Ningún código de aplicación se escribe hasta que el
> conjunto de artefactos SDD (PRD, API Spec, Technical Design, Data Model, Implementation
> Plan) y `ARCHITECTURE.md` esté aprobado. Cada requisito tiene un **ID trazable** que se
> referencia desde el resto de documentos y desde el código.

---

## 1. Problema

Una notificación de escritorio convencional es **descartable**: se silencia con "No molestar",
se cierra con un clic accidental o queda enterrada detrás de otras ventanas. En una emergencia
sísmica eso es exactamente lo que no debe ocurrir. La población y los equipos operativos en
Venezuela carecen de una herramienta **gratuita, auto-alojada y robusta** que garantice que una
alerta sísmica relevante **se vea y se reconozca**, sin depender de un teléfono, de servicios
pagos ni de claves de API.

El proyecto nace tras el terremoto de Venezuela de junio de 2026. Dependiendo de la distancia al
epicentro, una alerta basada en *push* real puede llegar **antes que las ondas sísmicas más
destructivas**; y cuando no, garantiza que la alerta no se pierda y quede registrada.

## 2. Usuarios y personas

| Persona | Descripción | Necesidad principal |
|---|---|---|
| **P1 — Operador humanitario** | Coordina respuesta en una ONG/protección civil. Tiene una estación de trabajo encendida 24/7. | Que la alerta interrumpa cualquier actividad y exija reconocimiento explícito; registro auditable. |
| **P2 — Ciudadano técnico** | Usuario avanzado (Linux/Win/macOS) que quiere alerta personal en su equipo. | Instalación simple, autoarranque, configurable por punto de referencia. |
| **P3 — Administrador de flotilla** | Despliega el agente en muchas máquinas. | Empaquetado nativo por SO, autoarranque, sin punto único de fallo. |

El usuario primario para el diseño de UX de la alerta es **P1 (operador humanitario)**.

## 3. Objetivos y métricas de éxito

| ID | Objetivo | Métrica / criterio |
|---|---|---|
| OBJ-1 | Alerta imposible de ignorar | La ventana de alerta solo se cierra con el botón **RECONOCIDO** (no Esc, no X, no clic fuera). |
| OBJ-2 | Latencia baja por *push* real | Tiempo desde mensaje EMSC recibido hasta ventana visible ≤ 1 s en hardware típico. |
| OBJ-3 | Cero eventos perdidos | Todo evento dentro del filtro reportado por EMSC **o** USGS termina alertado (push + reconciliación). |
| OBJ-4 | Robustez 24/7 | El agente nunca muere por un fallo transitorio (WS caído, 429/5xx, JSON inválido, red). |
| OBJ-5 | Multiplataforma sin fricción | Ejecutable en Linux, Windows y macOS; autoarranque y artefactos instalables nativos. |
| OBJ-6 | Auto-alojado y gratuito | Sin claves de API, sin servicios pagos; cada máquina corre su propio agente. |

## 4. Casos de uso

| ID | Caso de uso | Actor | Flujo resumido |
|---|---|---|---|
| CU-1 | Recibir alerta por sismo (push) | Sistema/P1 | EMSC empuja `create` → normaliza → pasa filtro → dedup (nuevo) → alerta en pantalla + sonido + toast. |
| CU-2 | Recuperar evento perdido (respaldo) | Sistema | USGS FDSN (cada 60 s) detecta evento que el WS no entregó → normaliza → filtro → dedup → alerta. |
| CU-3 | Recibir corrección de magnitud | Sistema | EMSC empuja `update` del mismo `unid` → se actualiza el evento mostrado **sin** disparar una alerta nueva. |
| CU-4 | Evitar alerta duplicada entre fuentes | Sistema | EMSC y USGS reportan el mismo sismo → la heurística de dedup lo reconoce → una sola alerta. |
| CU-5 | Reconocer una alerta | P1 | El usuario pulsa **RECONOCIDO** → la ventana se cierra → se registra el reconocimiento → se muestra el siguiente en cola. |
| CU-6 | Encolar múltiples sismos | Sistema/P1 | Varios eventos simultáneos → se muestran en orden, uno a uno. |
| CU-7 | Probar la capa de alerta | P2/P3 | Ejecutar `vigia-eew --simulate` → inyecta M6.1 cerca de La Guaira → verifica alerta sin sismo real. |
| CU-8 | Configurar filtro | P2 | Editar `config.toml` (punto de referencia, radio, magnitud mínima, severidades). |
| CU-9 | Instalar autoarranque | P2/P3 | Ejecutar el instalador de autoarranque del SO (systemd user / LaunchAgent / tarea programada). |
| CU-10 | Reiniciar sin re-alertar | Sistema | Tras reinicio, el estado persistido evita volver a alertar eventos ya reconocidos. |

## 5. Requisitos funcionales (RF)

### 5.1 Ingestión (push primario + respaldo)
- **RF-01** — Conectarse por WebSocket a `wss://www.seismicportal.eu/standing_order/websocket` como **vía primaria** (push real, sin polling de alta frecuencia).
- **RF-02** — Enviar **keepalive (ping) cada ~15 s** sobre el WS; sin keepalive el socket muere en silencio.
- **RF-03** — **Reconexión perpetua** con *backoff* exponencial al detectar cierre del WS; nunca quedarse con el socket caído.
- **RF-04** — Procesar mensajes EMSC con `action` ∈ {`create`, `update`} y `data` como Feature GeoJSON.
- **RF-05** — Consultar **USGS FDSN** por REST como **respaldo de baja frecuencia (cada 60 s)** únicamente para reconciliar/recuperar eventos no entregados por el WS y cubrir sismos locales pequeños.
- **RF-06** — Mantener un **cursor persistido** ("desde el último evento visto") para la consulta USGS.

### 5.2 Normalización
- **RF-07** — Normalizar EMSC y USGS a un **esquema de evento común**: `id`, `magnitud`, `magType`, `lugar/region`, `lat`, `lon`, `profundidad_km`, `hora_utc`, `fuente`, `distancia_km` al punto de referencia.
- **RF-08** — Calcular la `distancia_km` entre el epicentro y el punto de referencia (haversine).

### 5.3 Deduplicación
- **RF-09** — Considerar **el mismo sismo** si coincide dentro de **~100 km, ~90 s y ~0.5 de magnitud** entre fuentes.
- **RF-10** — **Persistir los `id` ya alertados** para no repetir tras reinicios.
- **RF-11** — Manejar `update` del WS (corrección de magnitud) **sin** disparar alerta nueva (actualiza el evento existente).

### 5.4 Filtrado (configurable)
- **RF-12** — Filtrar por **punto de referencia (lat/lon), radio en km y magnitud mínima** configurables.
- **RF-13** — Clasificar **severidad por magnitud** (p. ej. `<4` info, `4–5.5` atención, `5.5+` crítico), configurable, que cambie **color y sonido** de la alerta.
- **RF-33** — Cuando el usuario **no** configura `[referencia]` manualmente, **detectar automáticamente** el punto de referencia geográfico por geolocalización de IP (mejor esfuerzo), cachear el resultado para no repetir la consulta en cada arranque, y hacer **fallback silencioso** al default (Caracas) si la detección falla, sin bloquear el arranque del agente.

### 5.5 Notificación (requisito central)
- **RF-14** — Mostrar un **toast nativo** del SO (informativo) con `desktop-notifier` (Linux/Win/macOS).
- **RF-15** — Mostrar una **ventana de alerta superpuesta** siempre al frente (*topmost*), sin decoración, overlay grande centrado o pantalla completa.
- **RF-16** — La ventana **toma el foco** al aparecer y **se re-eleva** si lo pierde.
- **RF-17** — Reproducir **sonido de alarma**, más insistente según severidad.
- **RF-18** — Mostrar grande y legible: **MAGNITUD**, lugar/región, **distancia** al punto de referencia, profundidad, **hora local (zona de Venezuela)** y fuente.
- **RF-19** — La ventana **no se cierra con Esc, la X ni clic fuera**; solo con el botón **RECONOCIDO** (cierre explícito, no técnicamente imposible, para no bloquear al usuario ante un bug).
- **RF-20** — **Encolar múltiples sismos** y mostrarlos en orden.

### 5.6 Modo de prueba
- **RF-21** — Flag `--simulate` que **inyecte un evento falso** (p. ej. M6.1 cerca de La Guaira) para validar la capa de notificación en cada SO sin esperar un sismo real.

### 5.7 Autoarranque
- **RF-22** — Permitir **inicio automático al iniciar sesión**: Linux (systemd de usuario), macOS (LaunchAgent/Login Item), Windows (tarea programada al inicio de sesión).
- **RF-23** — Proveer comando/script para **instalar y desinstalar** el autoarranque en cada SO.

### 5.8 Configuración, logging y CLI
- **RF-24** — Configuración en archivo **`config.toml`** validada con **pydantic**, con *defaults* sensatos (Caracas: lat 10.4806, lon -66.9036).
- **RF-25** — **Logging estructurado** a consola y a **archivo rotativo**.
- **RF-26** — CLI con *entry point* de consola **`vigia-eew`** (subcomandos/flags: ejecutar, `--simulate`, instalar/desinstalar autoarranque, ruta de config).

### 5.9 Empaquetado y distribución
- **RF-27** — Paquete **PyPI** publicable con `pyproject.toml` (build con **hatchling**, gestor **uv**), versionado semántico.
- **RF-28** — **Windows**: `.exe` con PyInstaller (onefile, sin consola para la GUI).
- **RF-29** — **macOS**: bundle `.app` empaquetado en `.dmg`.
- **RF-30** — **Linux**: AppImage (recomendado) + `.deb` y `.rpm` (vía `fpm`); snap opcional/documentado.
- **RF-31** — **CI de build**: GitHub Actions con matriz (windows/macos/ubuntu-latest) que produzca todos los artefactos como *release assets*; más scripts locales (`build_windows.ps1`, `build_macos.sh`, `build_linux.sh`).
- **RF-32** — Documentar cómo servir el `.deb` desde un **repositorio apt propio en Cloudflare R2**.

## 6. Requisitos no funcionales (RNF)

| ID | Categoría | Requisito |
|---|---|---|
| RNF-01 | Latencia | EMSC recibido → ventana visible ≤ **1 s** (P95) en hardware típico. |
| RNF-02 | Disponibilidad | Operación **24/7**; sin punto único de fallo (cada máquina, su agente). |
| RNF-03 | Robustez | El proceso **no termina** por fallos transitorios (WS caído, timeouts, 429/5xx, JSON inválido, pérdida de red). |
| RNF-04 | Concurrencia | Basado en **asyncio**; tareas de ingestión sin bloquear la UI. |
| RNF-05 | "Alerta no descartable" | La alerta no se puede ocultar con un clic accidental; solo cierre explícito (RF-19). |
| RNF-06 | Portabilidad | Linux, Windows, macOS; UI por defecto en **Tkinter** (cero dependencias extra). |
| RNF-07 | Observabilidad | Logs estructurados con niveles; archivo rotativo; eventos de conexión/reconexión registrados. |
| RNF-08 | Mantenibilidad/Trazabilidad | Cada componente del código rastreable a un RF del PRD. |
| RNF-09 | Seguridad/Privacidad | Sin claves de API; sin enviar datos del usuario a terceros; solo lectura de fuentes públicas. Excepción explícita: la detección automática de ubicación (RF-33) consulta un servicio de geolocalización por IP, y solo cuando el usuario no fijó `[referencia]` manualmente — desactivable configurando la referencia a mano. |
| RNF-10 | Idioma | Código, comentarios y artefactos SDD en **español**. |
| RNF-11 | Versión de Python | **Python 3.11+** (uso de `tomllib` de la stdlib). |
| RNF-12 | Zona horaria | Hora local mostrada en **zona de Venezuela** (America/Caracas, UTC-4). |

## 7. Criterios de aceptación

| ID | Criterio (verificable) | Cubre |
|---|---|---|
| CA-01 | Con `--simulate`, en **los tres SO**, aparece la ventana de alerta al frente, con sonido, y **solo** se cierra con RECONOCIDO. | RF-15..RF-21, RNF-05 |
| CA-02 | Matar la red del WS hace que el agente reintente con *backoff* y se **reconecte** sin intervención, sin terminar el proceso. | RF-03, RNF-03 |
| CA-03 | Sin tráfico de eventos, el WS permanece vivo gracias al **ping cada ~15 s** (no se cierra por inactividad). | RF-02 |
| CA-04 | Un evento que el WS no entregó aparece vía **USGS** en ≤ 60 s y genera alerta. | RF-05, OBJ-3 |
| CA-05 | El **mismo** sismo reportado por EMSC y USGS produce **una sola** alerta. | RF-09, CU-4 |
| CA-06 | Un `update` de EMSC **actualiza** el evento mostrado y **no** crea una alerta nueva. | RF-11, CU-3 |
| CA-07 | Tras reiniciar el agente, los eventos **ya reconocidos no se vuelven a alertar**. | RF-10, CU-10 |
| CA-08 | Cambiar `radio`, `magnitud mínima` y `severidades` en `config.toml` modifica el comportamiento sin tocar código. | RF-12, RF-13, RF-24 |
| CA-09 | La hora se muestra en **America/Caracas** y la distancia en km al punto de referencia. | RF-08, RF-18, RNF-12 |
| CA-10 | El autoarranque se **instala y desinstala** correctamente en cada SO. | RF-22, RF-23 |
| CA-11 | El CI produce `.exe`, `.dmg`, AppImage, `.deb`, `.rpm` y el paquete de PyPI como artefactos. | RF-27..RF-31 |
| CA-12 | Sin `[referencia]` en `config.toml`, el agente detecta la ubicación por IP en el primer arranque y **reutiliza el caché** en arranques siguientes sin volver a llamar al servicio; si la detección falla, usa el default (Caracas) sin dejar de arrancar. | RF-33 |

## 8. Fuera de alcance (v1)

- Captura de notificaciones del teléfono celular como fuente (la fuente de verdad son **APIs sísmicas públicas**).
- Push real desde USGS por PDL (pesado/Java): se usa **polling** de respaldo en su lugar.
- Relay central FastAPI con *fan-out* por WebSocket: **documentado como evolución futura**, no implementado en v1 (cada máquina corre su propio agente).
- Frontend de presentación por **D-Bus** + **extensión de GNOME Shell** (modal con *grab* real en Wayland): **documentado como evolución futura** (ADR-010), no implementado en v1; el default sigue siendo Tkinter.
- Predicción sísmica o estimación de intensidad/sacudida (MMI/ShakeMap) propias.
- App móvil nativa, panel web, multiusuario/cuentas, telemetría centralizada.
- Firma de código con certificado de pago (se documenta el procedimiento; la firma efectiva depende de disponer del certificado).

## 9. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| WS de EMSC pierde mensajes o sufre timeouts (documentado). | Evento no alertado. | Respaldo USGS + reconciliación con cursor (RF-05, RF-06). |
| "No molestar" del SO silencia toasts. | Alerta no vista. | Ventana superpuesta *topmost* con foco (RF-15, RF-16) además del toast. |
| Backoff agresivo satura el endpoint. | Bloqueo/baneo. | Backoff exponencial con tope y *jitter* (Technical Design). |
| Diferencias de campos entre fuentes (`magtype` vs `magType`). | Datos mal normalizados. | Normalizador con mapeo explícito por fuente (API Spec / Data Model). |
| Gatekeeper/SmartScreen bloquean instaladores sin firmar. | Fricción de instalación. | Documentar codesign/notarización y procedimiento de confianza. |

## 10. Trazabilidad (resumen)

Los RF se mapean a componentes en `IMPLEMENTATION-PLAN.md` (matriz RF→componente) y a decisiones
en `TECHNICAL-DESIGN.md` (ADRs). Los contratos de entrada/salida están en `API-SPEC.md`; las
estructuras de datos en `DATA-MODEL.md`; la vista de sistema y diagramas en `ARCHITECTURE.md`.
