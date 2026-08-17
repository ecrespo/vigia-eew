# Matriz consolidada de pruebas — Vigía-eew

> Consolida los 275 casos de prueba de las 22 HUs.
> **P1 = protege un comportamiento que un commit fix demuestra que ya estuvo roto.**

## 0. Cómo leer esta matriz

Listar las 275 filas una por una repetiría las HUs sin añadir información. En su lugar:

- **§1** lista **completas** las filas **P1** (las derivadas de fixes reales) — son las
  que la v2 debe escribir primero, sin excepción.
- **§2** lista **completos** los **huecos**: casos sin test automatizado hoy.
- **§3** resume el resto (P2/P3 ya cubiertos) agregado por HU, con enlace al detalle.

Nada se omite en silencio: 275 = 15 (P1) + 20 (huecos) + 240 (cubiertos, resumidos).
El detalle fila a fila de esos 240 está en la tabla "Casos de prueba" de cada HU.

## 1. Casos P1 — derivados de fixes reales

Cada uno protege un comportamiento que **ya falló en producción**.

| ID | HU | Criterio | Tipo | Prioridad | ¿Test existente? | Fix de origen |
|---|---|---|---|---|---|---|
| TC-002.7 | HU-002 | CA-002.7 | unitaria | **P1** | `[VERIFY: tests/test_state.py:72]` | `b0f832c` — `prune()` nunca se llamaba |
| TC-002.8 | HU-002 | CA-002.7 | integración | **P1** | `[VERIFY: tests/test_dedup.py:157]` | `b0f832c` — cableado de la poda |
| TC-009.6 | HU-009 | CA-009.4 | unitaria | **P1** | `[VERIFY: tests/test_filter.py:121]` | `b0f832c` — sin filtro de frescura |
| TC-009.7 | HU-009 | CA-009.4 | unitaria | **P1** | `[VERIFY: tests/test_filter.py:128]` | `b0f832c` — backlog de días viejos |
| TC-009.8 | HU-009 | CA-009.4 | unitaria | **P1** | `[VERIFY: tests/test_filter.py:135]` | `b0f832c` |
| TC-009.9 | HU-009 | CA-009.5 | unitaria | **P1** | `[VERIFY: tests/test_filter.py:144]` | `b0f832c` — día local vs UTC |
| TC-011.11 | HU-011 | CA-011.9 | e2e (GUI) | **P1** | `[VERIFY: tests/test_alert_window.py:157]` | `f90c796`, `f0960ac` — texto recortado |
| TC-015.2 | HU-015 | CA-015.2 | CI | **P1** | No — solo el workflow | `5ee3b1d` — PyPI publicaba antes de tiempo |
| TC-015.3 | HU-015 | CA-015.3 | CI | **P1** | **No** | `7b1c71c`, `c38d9f6` — icono inválido, 2 releases |
| TC-015.4 | HU-015 | CA-015.4 | CI | **P1** | **No** | `bdc2a9d` — recurso dinámico ausente |
| TC-015.5 | HU-015 | CA-015.5 | unitaria | **P1** | `[VERIFY: tests/test_subprocess_env.py:23]` | `a02607f` — LD_LIBRARY_PATH |
| TC-015.6 | HU-015 | CA-015.5 | unitaria | **P1** | `[VERIFY: tests/test_subprocess_env.py:32]` | `a02607f` |
| TC-015.7 | HU-015 | CA-015.5 | unitaria | **P1** | `[VERIFY: tests/test_subprocess_env.py:42]` | `a02607f` — DYLD en macOS |
| TC-017.3 | HU-017 | CA-017.3 | unitaria | **P1** | `[VERIFY: tests/test_tray.py:139]` | `651c024` — no importaba sin display |
| TC-022.2 | HU-022 | CA-022.2 | unitaria | **P1** | **No** | `8e0064a` — endpoint en HTTP plano |

**11 de 15 P1 tienen test; 4 no.** Los cuatro descubiertos son de empaquetado y de
configuración de endpoint — exactamente las dos áreas donde el historial muestra que los
fallos escapan al suite.

## 2. Huecos — casos sin test automatizado hoy

| ID | HU | Criterio | Tipo | Prioridad | Por qué importa |
|---|---|---|---|---|---|
| TC-011.13 | HU-011 | CA-011.1 | e2e | **P1** | **Wayland**: la promesa central del producto no está verificada donde el compositor controla foco y apilamiento (RR-3) |
| TC-015.11 | HU-015 | CA-015.1 | e2e | **P1** | Humo del artefacto: arrancar el binario y correr `--simulate` cubriría de una vez los 4 fixes de empaquetado |
| TC-015.3 | HU-015 | CA-015.3 | CI | **P1** | Validar resolución de iconos antes de invocar linuxdeploy |
| TC-015.4 | HU-015 | CA-015.4 | CI | **P1** | Verificar que los hiddenimports dinámicos están en el binario |
| TC-022.2 | HU-022 | CA-022.2 | unitaria | **P1** | Fijar HTTPS para que no se revierta silenciosamente |
| TC-022.16 | HU-022 | CA-022.1 | integración | **P2** | Si GEOFON cambia columnas, hoy se pierde la fuente en silencio (RR-7) |
| TC-004.1 | HU-004 | CA-004.1 | unitaria | **P2** | Timestamps UTC en el log — sin cobertura alguna |
| TC-004.2 | HU-004 | CA-004.2 | unitaria | **P2** | Handlers de consola y archivo |
| TC-004.3 | HU-004 | CA-004.2 | unitaria | **P3** | Rotación del archivo |
| TC-004.4 | HU-004 | CA-004.3 | unitaria | **P3** | Ruta de log por SO |
| TC-004.6 | HU-004 | CA-004.2 | unitaria | **P2** | Un log no escribible no debe tumbar el arranque |
| TC-017.14 | HU-017 | CA-017.9 | integración | **P2** | `AgentState` lo tocan 3 hilos; no hay test de concurrencia |
| TC-010.13 | HU-010 | CA-010.5 | integración | **P2** | Enjambre: la heurística fusiona sismos genuinamente distintos |
| TC-018.11 | HU-018 | CA-018.2 | unitaria | **P2** | Paridad de catálogos de traducción |
| TC-021.12 | HU-021 | CA-021.1 | integración | **P2** | Sismo publicado justo antes del arranque se pierde por el sembrado |
| TC-007.10 | HU-007 | CA-007.2 | integración | **P2** | Tarea que falla siempre: riesgo de bucle caliente |
| TC-014.14 | HU-014 | CA-014.7 | integración | **P3** | Qué ve el usuario si `systemctl` no existe |
| TC-020.14 | HU-020 | CA-020.1 | unitaria | **P3** | Margen de ±decenas de km en fronteras 1:110m |
| TC-001.7 | HU-001 | CA-001.6 | unitaria | **P3** | Severidad exactamente en el umbral |
| TC-002.9 | HU-002 | CA-002.7 | integración | **P3** | Racha larga sin alertas: la poda no corre (limitación aceptada) |
| TC-019.13 | HU-019 | CA-019.11 | integración | **P3** | Confirmar que en TUI no se construyen toast ni bandeja |

## 3. Resto de casos, por HU

Los 240 restantes ya tienen test automatizado. Detalle fila a fila en cada HU.

| HU | TC totales | Con test | Huecos | P1 |
|---|---|---|---|---|
| HU-001 | 8 | 7 | 1 | 0 |
| HU-002 | 10 | 9 | 1 | 2 |
| HU-003 | 10 | 10 | 0 | 0 |
| HU-004 | 6 | 1 | 5 | 0 |
| HU-005 | 11 | 11 | 0 | 0 |
| HU-006 | 13 | 13 | 0 | 0 |
| HU-007 | 10 | 9 | 1 | 0 |
| HU-008 | 15 | 15 | 0 | 0 |
| HU-009 | 13 | 13 | 0 | 4 |
| HU-010 | 13 | 12 | 1 | 0 |
| HU-011 | 13 | 12 | 1 | 1 |
| HU-012 | 13 | 13 | 0 | 0 |
| HU-013 | 13 | 13 | 0 | 0 |
| HU-014 | 14 | 13 | 1 | 0 |
| HU-015 | 11 | 6 | 5 | 6 |
| HU-016 | 12 | 12 | 0 | 0 |
| HU-017 | 14 | 13 | 1 | 1 |
| HU-018 | 11 | 10 | 1 | 0 |
| HU-019 | 13 | 12 | 1 | 0 |
| HU-020 | 14 | 13 | 1 | 0 |
| HU-021 | 12 | 11 | 1 | 0 |
| HU-022 | 16 | 14 | 2 | 1 |
| **Total** | **275** | **255** | **20** | **15** |

## 4. Resumen de cobertura

- **275 casos · 255 con test automatizado (92,7 %) · 20 huecos.**
- El repo tiene **348 tests reales** en 35 archivos: hay más tests que casos de prueba
  derivados, porque varios tests cubren variantes de un mismo criterio.

### Por tipo

| Tipo | Casos | Comentario |
|---|---|---|
| Unitaria | ~215 | El grueso; favorecido por la inyección de dependencias |
| Integración | ~40 | Pipeline completo, resiliencia, cableado de `app.py` |
| e2e / GUI | ~12 | Ventana Tkinter real (tras `VIGIA_GUI_TESTS=1`) y piloto de Textual |
| CI | ~8 | Empaquetado; sin test unitario posible |

### Por prioridad

| Prioridad | Casos | Con test |
|---|---|---|
| P1 | 15 | 11 (73 %) |
| P2 | ~95 | 91 |
| P3 | ~165 | 153 |

### Huecos críticos — el orden en que la v2 debe atacarlos

1. **TC-011.13 (Wayland)** — la garantía central del producto sin verificar en el
   escritorio Linux por defecto. Bloquea la decisión de toolkit de la v2.
2. **TC-015.11 (humo del artefacto)** — un solo test de CI que arranca el binario
   construido y corre `--simulate` cubre TC-015.3, TC-015.4 y valida rutas de asset y
   saneamiento de entorno. Es el mayor retorno por esfuerzo de toda la lista.
3. **TC-022.2 + TC-022.16 (contrato de fuentes)** — HTTPS fijado por test, y detección
   explícita de cambios de formato en lugar de descarte silencioso.
4. **TC-004.\* (logging)** — módulo completo sin tests; TC-004.6 en particular, porque un
   fallo ahí contradice el patrón de aislamiento del resto del sistema.

## 5. Observación sobre el entorno de ejecución

Dos tests del suite por defecto —`test_build_icon_assembles_menu_with_actions`
`[VERIFY: tests/test_tray.py:81]` y `test_build_tray_enabled_returns_icon`
`[VERIFY: tests/test_app.py:175]`— **requieren un display real** y fallan con
`Xlib DisplayNameError` en un entorno headless, pese a que `CLAUDE.md` afirma que el suite
por defecto corre sin display.

Verificado durante este análisis: con `xvfb-run` pasan los 345 tests; sin él, fallan esos
dos. La v2 debe resolverlo con el guard `VIGIA_GUI_TESTS=1` que ya usan los smokes de
Tkinter, o ejecutando CI bajo `xvfb` (RR-6, DT-5).
