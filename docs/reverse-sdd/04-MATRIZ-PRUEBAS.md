# 04 — Matriz consolidada de pruebas

> Consolida los 157 casos de prueba de las 17 HUs, más los 5 escenarios e2e del cluster C-08
> (pruebas de resiliencia), que no genera HU propia.
>
> **Prioridad P1** = protege un comportamiento que un commit `fix` demuestra que estuvo roto, o
> carece de test automatizado hoy. **P2** = camino feliz o negativo cubierto. **P3** = caso borde.

## 1. Resumen de cobertura

| Métrica | Valor |
|---|---|
| Casos totales (HUs) | **157** |
| Con test automatizado existente | **143 (91 %)** |
| Sin test — a escribir en la v2 | **14 (9 %)** |
| Escenarios e2e adicionales (C-08) | 5, todos cubiertos |

| Tipo | Casos | | Prioridad | Casos |
|---|---|---|---|---|
| unitaria | 125 | | P1 | 20 |
| integración | 31 | | P2 | 93 |
| e2e | 1 (+5 de C-08) | | P3 | 44 |

Base de evidencia: **344 pruebas** en 35 archivos `test_*.py`, suite headless por defecto.

## 2. Huecos críticos — P1 sin test automatizado

Los 14 casos sin cobertura se concentran en **empaquetado, publicación y configuración de CI**:
todo aquello que solo se ejerce al construir o publicar un artefacto. Es coherente con la historia
del repositorio, donde el cluster de empaquetado (C-09) acumula la mayor densidad de fixes.

| Caso | HU | Qué protege | Por qué es P1 |
|---|---|---|---|
| TC-007.4 | HU-007 | El build falla rápido si un asset del empaquetado tiene formato o resolución inválidos | **Rompió dos releases consecutivas** `[COMMITS: 7b1c71c, c38d9f6]` |
| TC-007.3 | HU-007 | Los recursos de terceros viajan dentro del binario congelado | Fue un fallo en tiempo de ejecución `[COMMITS: bdc2a9d]` |
| TC-015.8 | HU-015 | El endpoint de GEOFON usa HTTPS | Se introdujo en HTTP y hubo que corregirlo `[COMMITS: 8e0064a]` |
| TC-007.1, TC-007.2, TC-007.7 | HU-007 | Publicación en PyPI y ejecución del binario producido | Sin verificación automática hoy |
| TC-017.5, TC-017.6, TC-017.7 | HU-017 | Entorno del runner, caché sin lockfile, publicación | Tres fixes de CI en un solo día `[COMMITS: 0e707a1, 27e4b45, f51da9c]` |
| TC-010.8 | HU-010 | El código fuente permanece en inglés | Convención verificada solo por revisión humana |

**Orden recomendado para la v2**: TC-007.4 → TC-015.8 → TC-007.3/TC-007.7 → los de CI. Los tres
primeros son baratos (una validación de formato, un aserto sobre la URL por defecto, un smoke del
binario con `--simulate`) y cubren tres bugs históricos reales.

## 3. Matriz completa

| ID | HU | Criterio | Tipo | Prioridad | ¿Test existente en el repo? | Estado v2 |
|---|---|---|---|---|---|---|
| TC-001.1 | HU-001 | CA-001.1 | unitaria | P2 | `[VERIFY: tests/test_models.py:36]` | cubierto |
| TC-001.2 | HU-001 | CA-001.1 | unitaria | P3 | `[VERIFY: tests/test_models.py:53]` | cubierto |
| TC-001.3 | HU-001 | CA-001.1 | unitaria | P2 | `[VERIFY: tests/test_models.py:48]` | cubierto |
| TC-001.4 | HU-001 | CA-001.2 | unitaria | P2 | `[VERIFY: tests/test_models.py:77]` | cubierto |
| TC-001.5 | HU-001 | CA-001.2 | unitaria | P3 | `[VERIFY: tests/test_normalize.py:131]` | cubierto |
| TC-001.6 | HU-001 | CA-001.3 | unitaria | P2 | `[VERIFY: tests/test_state.py:39]` | cubierto |
| TC-001.7 | HU-001 | CA-001.4 | unitaria | P2 | `[VERIFY: tests/test_state.py:86]` | cubierto |
| TC-001.8 | HU-001 | CA-001.5 | unitaria | P2 | `[VERIFY: tests/test_state.py:52]` | cubierto |
| TC-001.9 | HU-001 | CA-001.6 | unitaria | P2 | `[VERIFY: tests/test_config.py:122]` | cubierto |
| TC-001.10 | HU-001 | CA-001.1 | unitaria | P2 | `[VERIFY: tests/test_models.py:62]` | cubierto |
| TC-002.1 | HU-002 | CA-002.1 | unitaria | P2 | `[VERIFY: tests/test_ws_emsc.py:132]` | cubierto |
| TC-002.2 | HU-002 | CA-002.1 | unitaria | P3 | `[VERIFY: tests/test_ws_emsc.py:113]` | cubierto |
| TC-002.3 | HU-002 | CA-002.1 | unitaria | P2 | `[VERIFY: tests/test_ws_emsc.py:119]` | cubierto |
| TC-002.4 | HU-002 | CA-002.2 | unitaria | P2 | `[VERIFY: tests/test_ws_emsc.py:159]` | cubierto |
| TC-002.5 | HU-002 | CA-002.2 | unitaria | P3 | `[VERIFY: tests/test_backoff.py:18]` | cubierto |
| TC-002.6 | HU-002 | CA-002.3 | unitaria | P2 | `[VERIFY: tests/test_rest_usgs.py:171]` | cubierto |
| TC-002.7 | HU-002 | CA-002.3 | unitaria | P3 | `[VERIFY: tests/test_rest_usgs.py:193]` | cubierto |
| TC-002.8 | HU-002 | CA-002.4 | unitaria | P2 | `[VERIFY: tests/test_rest_usgs.py:203]` | cubierto |
| TC-002.9 | HU-002 | CA-002.5 | unitaria | P2 | `[VERIFY: tests/test_supervisor.py:30]` | cubierto |
| TC-002.10 | HU-002 | CA-002.5 | unitaria | P3 | `[VERIFY: tests/test_supervisor.py:53]` | cubierto |
| TC-002.11 | HU-002 | CA-002.6 | unitaria | P2 | `[VERIFY: tests/test_supervisor.py:81]` | cubierto |
| TC-003.1 | HU-003 | CA-003.1 | unitaria | P2 | `[VERIFY: tests/test_normalize.py:72]` | cubierto |
| TC-003.2 | HU-003 | CA-003.1 | unitaria | P3 | `[VERIFY: tests/test_normalize.py:86]` | cubierto |
| TC-003.3 | HU-003 | CA-003.2 | unitaria | P2 | `[VERIFY: tests/test_normalize.py:149]` | cubierto |
| TC-003.4 | HU-003 | CA-003.3 | unitaria | P2 | `[VERIFY: tests/test_filter.py:36]` | cubierto |
| TC-003.5 | HU-003 | CA-003.3 | unitaria | P3 | `[VERIFY: tests/test_filter.py:48]` | cubierto |
| TC-003.6 | HU-003 | CA-003.3 | unitaria | P2 | `[VERIFY: tests/test_filter.py:40]` | cubierto |
| TC-003.7 | HU-003 | CA-003.4 | e2e | P2 | `[VERIFY: tests/test_resilience.py:107]` | cubierto |
| TC-003.8 | HU-003 | CA-003.4 | unitaria | P3 | `[VERIFY: tests/test_dedup.py:75]` | cubierto |
| TC-003.9 | HU-003 | CA-003.4 | unitaria | P2 | `[VERIFY: tests/test_dedup.py:106]` | cubierto |
| TC-003.10 | HU-003 | CA-003.5 | unitaria | P2 | `[VERIFY: tests/test_dedup.py:60]` | cubierto |
| TC-003.11 | HU-003 | CA-003.5 | unitaria | P2 | `[VERIFY: tests/test_dedup.py:66]` | cubierto |
| TC-003.12 | HU-003 | CA-003.6 | unitaria | P2 | `[VERIFY: tests/test_dedup.py:143]` | cubierto |
| TC-004.1 | HU-004 | CA-004.1 | unitaria | P2 | `[VERIFY: tests/test_alert_window.py:111]` | cubierto |
| TC-004.2 | HU-004 | CA-004.1 | unitaria | P2 | `[VERIFY: tests/test_alert_window.py:87]` | cubierto |
| TC-004.3 | HU-004 | CA-004.1 | unitaria | P2 | `[VERIFY: tests/test_alert_window.py:94]` | cubierto |
| TC-004.4 | HU-004 | CA-004.2 | unitaria | P3 | `[VERIFY: tests/test_alert_window.py:119]` | cubierto |
| TC-004.5 | HU-004 | CA-004.3 | unitaria | P1 | `[VERIFY: tests/test_alert_window.py:174]` | cubierto |
| TC-004.6 | HU-004 | CA-004.4 | integración | P2 | `[VERIFY: tests/test_alert_queue.py:73]` | cubierto |
| TC-004.7 | HU-004 | CA-004.4 | integración | P3 | `[VERIFY: tests/test_alert_queue.py:128]` | cubierto |
| TC-004.8 | HU-004 | CA-004.5 | unitaria | P2 | `[VERIFY: tests/test_sound.py:44]` | cubierto |
| TC-004.9 | HU-004 | CA-004.5 | unitaria | P2 | `[VERIFY: tests/test_sound.py:97]` | cubierto |
| TC-004.10 | HU-004 | CA-004.6 | unitaria | P2 | `[VERIFY: tests/test_toast.py:62]` | cubierto |
| TC-005.1 | HU-005 | CA-005.1 | integración | P2 | `[VERIFY: tests/test_cli.py:59]` | cubierto |
| TC-005.2 | HU-005 | CA-005.2 | unitaria | P2 | `[VERIFY: tests/test_simulation.py:11]` | cubierto |
| TC-005.3 | HU-005 | CA-005.2 | integración | P3 | `[VERIFY: tests/test_app.py:96]` | cubierto |
| TC-005.4 | HU-005 | CA-005.3 | integración | P2 | `[VERIFY: tests/test_cli.py:81]` | cubierto |
| TC-005.5 | HU-005 | CA-005.4 | integración | P2 | `[VERIFY: tests/test_cli.py:88]` | cubierto |
| TC-005.6 | HU-005 | CA-005.5 | integración | P2 | `[VERIFY: tests/test_processor.py:63]` | cubierto |
| TC-005.7 | HU-005 | CA-005.5 | integración | P2 | `[VERIFY: tests/test_processor.py:77]` | cubierto |
| TC-005.8 | HU-005 | CA-005.1 | integración | P3 | `[VERIFY: tests/test_cli.py:136]` | cubierto |
| TC-006.1 | HU-006 | CA-006.1 | unitaria | P2 | `[VERIFY: tests/test_autostart.py:29]` | cubierto |
| TC-006.2 | HU-006 | CA-006.1 | unitaria | P2 | `[VERIFY: tests/test_autostart.py:48]` | cubierto |
| TC-006.3 | HU-006 | CA-006.2 | unitaria | P2 | `[VERIFY: tests/test_autostart_linux.py:28]` | cubierto |
| TC-006.4 | HU-006 | CA-006.3 | unitaria | P2 | `[VERIFY: tests/test_autostart_linux.py:39]` | cubierto |
| TC-006.5 | HU-006 | CA-006.3 | unitaria | P3 | `[VERIFY: tests/test_autostart_linux.py:70]` | cubierto |
| TC-006.6 | HU-006 | CA-006.4 | unitaria | P3 | `[VERIFY: tests/test_autostart.py:21]` | cubierto |
| TC-006.7 | HU-006 | CA-006.5 | unitaria | P1 | `[VERIFY: tests/test_subprocess_env.py:23]` | cubierto |
| TC-006.8 | HU-006 | CA-006.5 | unitaria | P1 | `[VERIFY: tests/test_subprocess_env.py:73]` | cubierto |
| TC-007.1 | HU-007 | CA-007.1 | integración | P1 | **No** | **pendiente v2** |
| TC-007.2 | HU-007 | CA-007.1 | unitaria | P1 | **No** | **pendiente v2** |
| TC-007.3 | HU-007 | CA-007.2 | integración | P1 | **No** | **pendiente v2** |
| TC-007.4 | HU-007 | CA-007.3 | unitaria | P1 | **No** | **pendiente v2** |
| TC-007.5 | HU-007 | CA-007.4 | unitaria | P1 | `[VERIFY: tests/test_subprocess_env.py:23]` | cubierto |
| TC-007.6 | HU-007 | CA-007.4 | unitaria | P1 | `[VERIFY: tests/test_subprocess_env.py:42]` | cubierto |
| TC-007.7 | HU-007 | CA-007.5 | integración | P1 | **No** | **pendiente v2** |
| TC-008.1 | HU-008 | CA-008.1 | integración | P2 | `[VERIFY: tests/test_app.py:108]` | cubierto |
| TC-008.2 | HU-008 | CA-008.1 | integración | P3 | `[VERIFY: tests/test_app.py:136]` | cubierto |
| TC-008.3 | HU-008 | CA-008.2 | integración | P2 | `[VERIFY: tests/test_app.py:123]` | cubierto |
| TC-008.4 | HU-008 | CA-008.3 | unitaria | P2 | `[VERIFY: tests/test_geoloc.py:48]` | cubierto |
| TC-008.5 | HU-008 | CA-008.3 | unitaria | P2 | `[VERIFY: tests/test_geoloc.py:53]` | cubierto |
| TC-008.6 | HU-008 | CA-008.4 | unitaria | P2 | `[VERIFY: tests/test_geoloc.py:68]` | cubierto |
| TC-008.7 | HU-008 | CA-008.4 | unitaria | P3 | `[VERIFY: tests/test_geoloc.py:73]` | cubierto |
| TC-008.8 | HU-008 | CA-008.5 | integración | P3 | `[VERIFY: tests/test_app.py:96]` | cubierto |
| TC-008.9 | HU-008 | CA-008.1 | unitaria | P3 | `[VERIFY: tests/test_geoloc.py:80]` | cubierto |
| TC-009.1 | HU-009 | CA-009.1 | unitaria | P2 | `[VERIFY: tests/test_ws_emsc.py:193]` | cubierto |
| TC-009.2 | HU-009 | CA-009.1 | unitaria | P3 | `[VERIFY: tests/test_ws_emsc.py:209]` | cubierto |
| TC-009.3 | HU-009 | CA-009.2 | integración | P2 | `[VERIFY: tests/test_alert_queue.py:94]` | cubierto |
| TC-009.4 | HU-009 | CA-009.2 | integración | P3 | `[VERIFY: tests/test_alert_queue.py:105]` | cubierto |
| TC-009.5 | HU-009 | CA-009.2 | integración | P3 | `[VERIFY: tests/test_alert_queue.py:117]` | cubierto |
| TC-009.6 | HU-009 | CA-009.3 | integración | P2 | `[VERIFY: tests/test_app.py:181]` | cubierto |
| TC-009.7 | HU-009 | CA-009.4 | integración | P2 | `[VERIFY: tests/test_app.py:205]` | cubierto |
| TC-009.8 | HU-009 | CA-009.4 | unitaria | P3 | `[VERIFY: tests/test_tray.py:39]` | cubierto |
| TC-009.9 | HU-009 | CA-009.5 | unitaria | P2 | `[VERIFY: tests/test_tray.py:121]` | cubierto |
| TC-009.10 | HU-009 | CA-009.5 | unitaria | P2 | `[VERIFY: tests/test_tray.py:139]` | cubierto |
| TC-010.1 | HU-010 | CA-010.1 | unitaria | P2 | `[VERIFY: tests/test_i18n.py:38]` | cubierto |
| TC-010.2 | HU-010 | CA-010.1 | unitaria | P3 | `[VERIFY: tests/test_i18n.py:48]` | cubierto |
| TC-010.3 | HU-010 | CA-010.1 | unitaria | P2 | `[VERIFY: tests/test_i18n.py:54]` | cubierto |
| TC-010.4 | HU-010 | CA-010.2 | unitaria | P2 | `[VERIFY: tests/test_i18n.py:43]` | cubierto |
| TC-010.5 | HU-010 | CA-010.2 | unitaria | P2 | `[VERIFY: tests/test_i18n.py:25]` | cubierto |
| TC-010.6 | HU-010 | CA-010.3 | unitaria | P2 | `[VERIFY: tests/test_i18n.py:29]` | cubierto |
| TC-010.7 | HU-010 | CA-010.4 | unitaria | P2 | `[VERIFY: tests/test_i18n.py:20]` | cubierto |
| TC-010.8 | HU-010 | CA-010.5 | unitaria | P1 | **No** | **pendiente v2** |
| TC-011.1 | HU-011 | CA-011.1 | integración | P2 | `[VERIFY: tests/test_tui.py:26]` | cubierto |
| TC-011.2 | HU-011 | CA-011.1 | integración | P3 | `[VERIFY: tests/test_tui.py:41]` | cubierto |
| TC-011.3 | HU-011 | CA-011.2 | integración | P2 | `[VERIFY: tests/test_tui.py:65]` | cubierto |
| TC-011.4 | HU-011 | CA-011.2 | integración | P2 | `[VERIFY: tests/test_tui.py:78]` | cubierto |
| TC-011.5 | HU-011 | CA-011.3 | integración | P3 | `[VERIFY: tests/test_tui.py:90]` | cubierto |
| TC-011.6 | HU-011 | CA-011.4 | integración | P2 | `[VERIFY: tests/test_tui.py:117]` | cubierto |
| TC-011.7 | HU-011 | CA-011.4 | integración | P3 | `[VERIFY: tests/test_tui.py:153]` | cubierto |
| TC-011.8 | HU-011 | CA-011.5 | integración | P2 | `[VERIFY: tests/test_tui.py:169]` | cubierto |
| TC-011.9 | HU-011 | CA-011.6 | unitaria | P1 | `[VERIFY: tests/test_tray.py:139]` | cubierto |
| TC-012.1 | HU-012 | CA-012.1 | unitaria | P2 | `[VERIFY: tests/test_filter.py:67]` | cubierto |
| TC-012.2 | HU-012 | CA-012.1 | unitaria | P2 | `[VERIFY: tests/test_filter.py:72]` | cubierto |
| TC-012.3 | HU-012 | CA-012.2 | unitaria | P3 | `[VERIFY: tests/test_filter.py:77]` | cubierto |
| TC-012.4 | HU-012 | CA-012.3 | unitaria | P2 | `[VERIFY: tests/test_filter.py:88]` | cubierto |
| TC-012.5 | HU-012 | CA-012.3 | unitaria | P3 | `[VERIFY: tests/test_filter.py:83]` | cubierto |
| TC-012.6 | HU-012 | CA-012.4 | unitaria | P2 | `[VERIFY: tests/test_filter.py:94]` | cubierto |
| TC-012.7 | HU-012 | CA-012.5 | unitaria | P2 | `[VERIFY: tests/test_geocode.py:69]` | cubierto |
| TC-012.8 | HU-012 | CA-012.5 | unitaria | P3 | `[VERIFY: tests/test_geocode.py:46]` | cubierto |
| TC-012.9 | HU-012 | CA-012.5 | unitaria | P2 | `[VERIFY: tests/test_geocode.py:77]` | cubierto |
| TC-013.1 | HU-013 | CA-013.1 | unitaria | P2 | `[VERIFY: tests/test_config.py:142]` | cubierto |
| TC-013.2 | HU-013 | CA-013.1 | unitaria | P3 | `[VERIFY: tests/test_config.py:142]` | cubierto |
| TC-013.3 | HU-013 | CA-013.2 | unitaria | P3 | `[VERIFY: tests/test_config.py:151]` | cubierto |
| TC-013.4 | HU-013 | CA-013.3 | integración | P3 | `[VERIFY: tests/test_cli.py:122]` | cubierto |
| TC-013.5 | HU-013 | CA-013.4 | unitaria | P2 | `[VERIFY: tests/test_config.py:167]` | cubierto |
| TC-013.6 | HU-013 | CA-013.5 | unitaria | P2 | `[VERIFY: tests/test_config.py:127]` | cubierto |
| TC-013.7 | HU-013 | CA-013.5 | unitaria | P3 | `[VERIFY: tests/test_config.py:135]` | cubierto |
| TC-013.8 | HU-013 | CA-013.6 | unitaria | P2 | `[VERIFY: tests/test_config.py:175]` | cubierto |
| TC-014.1 | HU-014 | CA-014.1 | unitaria | P2 | `[VERIFY: tests/test_rest_funvisis.py:84]` | cubierto |
| TC-014.2 | HU-014 | CA-014.2 | unitaria | P2 | `[VERIFY: tests/test_rest_funvisis.py:92]` | cubierto |
| TC-014.3 | HU-014 | CA-014.2 | unitaria | P3 | `[VERIFY: tests/test_rest_funvisis.py:110]` | cubierto |
| TC-014.4 | HU-014 | CA-014.3 | unitaria | P2 | `[VERIFY: tests/test_rest_funvisis.py:127]` | cubierto |
| TC-014.5 | HU-014 | CA-014.4 | unitaria | P2 | `[VERIFY: tests/test_normalize.py:196]` | cubierto |
| TC-014.6 | HU-014 | CA-014.4 | unitaria | P2 | `[VERIFY: tests/test_normalize.py:248]` | cubierto |
| TC-014.7 | HU-014 | CA-014.5 | unitaria | P2 | `[VERIFY: tests/test_rest_funvisis.py:156]` | cubierto |
| TC-014.8 | HU-014 | CA-014.5 | unitaria | P2 | `[VERIFY: tests/test_rest_funvisis.py:162]` | cubierto |
| TC-014.9 | HU-014 | CA-014.6 | unitaria | P3 | `[VERIFY: tests/test_filter.py:40]` | cubierto |
| TC-015.1 | HU-015 | CA-015.1 | unitaria | P2 | `[VERIFY: tests/test_rest_geofon.py:165]` | cubierto |
| TC-015.2 | HU-015 | CA-015.1 | unitaria | P3 | `[VERIFY: tests/test_rest_geofon.py:213]` | cubierto |
| TC-015.3 | HU-015 | CA-015.2 | unitaria | P3 | `[VERIFY: tests/test_rest_geofon.py:179]` | cubierto |
| TC-015.4 | HU-015 | CA-015.3 | unitaria | P2 | `[VERIFY: tests/test_rest_geofon.py:189]` | cubierto |
| TC-015.5 | HU-015 | CA-015.3 | unitaria | P2 | `[VERIFY: tests/test_rest_geofon.py:257]` | cubierto |
| TC-015.6 | HU-015 | CA-015.4 | unitaria | P3 | `[VERIFY: tests/test_rest_geofon.py:223]` | cubierto |
| TC-015.7 | HU-015 | CA-015.4 | unitaria | P2 | `[VERIFY: tests/test_rest_geofon.py:232]` | cubierto |
| TC-015.8 | HU-015 | CA-015.5 | unitaria | P1 | **No** | **pendiente v2** |
| TC-015.9 | HU-015 | CA-015.6 | unitaria | P2 | `[VERIFY: tests/test_dedup.py:86]` | cubierto |
| TC-015.10 | HU-015 | CA-015.6 | unitaria | P3 | `[VERIFY: tests/test_dedup.py:100]` | cubierto |
| TC-016.1 | HU-016 | CA-016.1 | unitaria | P2 | `[VERIFY: tests/test_filter.py:121]` | cubierto |
| TC-016.2 | HU-016 | CA-016.1 | unitaria | P2 | `[VERIFY: tests/test_filter.py:128]` | cubierto |
| TC-016.3 | HU-016 | CA-016.1 | unitaria | P2 | `[VERIFY: tests/test_filter.py:135]` | cubierto |
| TC-016.4 | HU-016 | CA-016.2 | unitaria | P3 | `[VERIFY: tests/test_filter.py:144]` | cubierto |
| TC-016.5 | HU-016 | CA-016.3 | unitaria | P2 | `[VERIFY: tests/test_filter.py:161]` | cubierto |
| TC-016.6 | HU-016 | CA-016.3 | unitaria | P3 | `[VERIFY: tests/test_filter.py:154]` | cubierto |
| TC-016.7 | HU-016 | CA-016.4 | unitaria | P2 | `[VERIFY: tests/test_filter.py:168]` | cubierto |
| TC-016.8 | HU-016 | CA-016.5 | unitaria | P2 | `[VERIFY: tests/test_rest_usgs.py:111]` | cubierto |
| TC-016.9 | HU-016 | CA-016.5 | unitaria | P3 | `[VERIFY: tests/test_rest_usgs.py:135]` | cubierto |
| TC-016.10 | HU-016 | CA-016.5 | unitaria | P3 | `[VERIFY: tests/test_rest_usgs.py:121]` | cubierto |
| TC-016.11 | HU-016 | CA-016.5 | unitaria | P2 | `[VERIFY: tests/test_rest_usgs.py:160]` | cubierto |
| TC-016.12 | HU-016 | CA-016.6 | unitaria | P2 | `[VERIFY: tests/test_dedup.py:157]` | cubierto |
| TC-017.1 | HU-017 | CA-017.1 | unitaria | P1 | **No** | **pendiente v2** |
| TC-017.2 | HU-017 | CA-017.1 | unitaria | P1 | **No** | **pendiente v2** |
| TC-017.3 | HU-017 | CA-017.2 | unitaria | P1 | **No** | **pendiente v2** |
| TC-017.4 | HU-017 | CA-017.2 | unitaria | P1 | **No** | **pendiente v2** |
| TC-017.5 | HU-017 | CA-017.3 | unitaria | P1 | **No** | **pendiente v2** |
| TC-017.6 | HU-017 | CA-017.4 | unitaria | P1 | **No** | **pendiente v2** |
| TC-017.7 | HU-017 | CA-017.5 | integración | P1 | **No** | **pendiente v2** |


## 4. Escenarios e2e del cluster C-08

`tests/test_resilience.py` `[COMMITS: f49d139]` verifica el sistema completo, no una HU concreta.
Son las pruebas de mayor valor del repositorio y deben replicarse íntegras en la v2.

| ID | Escenario | Cubre | Prioridad | Test existente |
|---|---|---|---|---|
| E2E-1 | Un evento que solo llegó por USGS genera alerta atravesando el pipeline completo | HU-002, HU-003, HU-004 | P1 | `[VERIFY: tests/test_resilience.py:94]` |
| E2E-2 | El mismo terremoto reportado por dos fuentes produce **una sola** alerta | HU-003 | P1 | `[VERIFY: tests/test_resilience.py:107]` |
| E2E-3 | Dos eventos fuera de la heurística **no** se deduplican (control negativo) | HU-003 | P1 | `[VERIFY: tests/test_resilience.py:121]` |
| E2E-4 | Tras reiniciar el agente, un evento ya visto no se vuelve a alertar | HU-001, HU-003 | P1 | `[VERIFY: tests/test_resilience.py:138]` |
| E2E-5 | El supervisor mantiene vivo el ingestor WebSocket tras una caída | HU-002 | P1 | `[VERIFY: tests/test_resilience.py:186]` |

## 5. Notas de método

- El **tipo** se deriva del archivo de test que respalda cada caso: los de `test_app.py`,
  `test_cli.py`, `test_processor.py`, `test_tui.py`, `test_controller.py` y `test_alert_queue.py`
  cruzan componentes y se clasifican como integración; `test_resilience.py` es e2e; el resto,
  unitaria.
- Los casos de GUI real (`test_alert_window.py::test_smoke_*`) están tras `VIGIA_GUI_TESTS=1` y no
  corren en la suite por defecto. Se cuentan como cubiertos, pero la v2 debería ejecutarlos en un
  job de CI con display virtual para que la cobertura sea efectiva y no nominal.
- Ningún caso de prueba cubre el comportamiento bajo Wayland (CA-004.1), porque no hay
  implementación que probar: ver `01-ARQUITECTURA.md` §7.
