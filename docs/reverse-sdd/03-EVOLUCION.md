# 03 — Evolución del sistema

> Derivado del historial git (59 commits, 2026-06-28 → 2026-08-16). Cada afirmación
> histórica cita sus hashes.

**Nota sobre las eras**: el script propuso eras por trimestre (2026-Q2 / 2026-Q3) porque
el repo **no tiene tags git**. Ese corte no dice nada útil aquí — 40 de 47 commits caen en
un solo trimestre. Las eras de abajo se derivan de los commits `chore: release`, que sí
marcan hitos reales de producto. Que las releases no estén tageadas es en sí un hallazgo:
`build.yml` se dispara con tags `vX.Y.Z` `[VERIFY: .github/workflows/build.yml:8]`, así
que los tags existen en el remoto o los binarios nunca se construyeron desde esta rama.

## Era 0 — Fundación completa en un día (2026-06-28 → 2026-07-03) → v0.1.0

El proyecto arrancó **por los specs, no por el código**: el segundo commit del repo son
los artefactos SDD completos (PRD, API-Spec, Technical Design, Data Model, Implementation
Plan, ARCHITECTURE) `[COMMITS: 737d7fa]`. Todo lo que vino después ejecuta ese plan.

En un solo día se construyeron las fases 1 a 5: modelos, config, estado y logging
`[COMMITS: b5c5371]`; ingestión EMSC/USGS y supervisor `[COMMITS: fc0ca99]`; pipeline de
normalización, filtro y dedup `[COMMITS: b40c20b]`; capa de notificación
`[COMMITS: fb50326]`; y CLI con modo simulación `[COMMITS: 4fb49d0]`. Cinco días después
llegaron autoarranque `[COMMITS: 5b79ff1]`, tests de resiliencia end-to-end
`[COMMITS: f49d139]` y empaquetado multiplataforma `[COMMITS: b6413e3]`.

**Lo que el sistema ganó**: de cero a un agente funcional y distribuible. La arquitectura
de hoy —cuatro capas, supervisor, efectos inyectados— ya estaba completa aquí; todo lo
posterior añade fuentes y frontends sin cambiarla. Es la señal más fuerte a favor del
enfoque SDD de este repo.

## Era 1 — El empaquetado muerde (2026-07-03 → 2026-07-04) → v0.1.1 … v0.1.3

Tres releases seguidas, las tres por fallos de empaquetado y ninguna por lógica de
negocio: un ícono placeholder con resolución inválida rompió el build de AppImage
`[COMMITS: 7b1c71c]` y luego linuxdeploy `[COMMITS: c38d9f6]`; después
`desktop_notifier.resources` faltaba en el binario PyInstaller `[COMMITS: bdc2a9d]`.

**Lección**: el código estaba probado, el *artefacto* no. Tres releases de parche
consecutivas sobre el mismo tema son el patrón de fixes más claro del historial.

## Era 2 — Contexto del usuario y frontends alternativos (2026-07-04) → v0.2.0

El agente deja de asumir que el usuario configuró algo. Detección automática de ubicación
por IP `[COMMITS: c20a59b]` — antes, quien no editaba `config.toml` obtenía un filtro
centrado en Caracas sin saberlo. Luego el ícono de bandeja `[COMMITS: fb3fe14]` para poder
ver estado y pausar sin depender de la terminal, y el dashboard TUI
`[COMMITS: 7f98980]` para servidores headless por SSH.

En medio, el cambio más invasivo del historial: **traducción de todo el código base al
inglés con i18n** `[COMMITS: 7f9132e]`, marcado `feat!` (breaking), seguido inmediatamente
de la migración a imports absolutos `[COMMITS: e49404d]`.

Dos fixes de layout en la ventana de alerta muestran que la garantía central seguía
madurando: la hora se recortaba por falta de `wraplength` `[COMMITS: f90c796]` y el
contenido chocaba contra el borde inferior `[COMMITS: f0960ac]`.

## Era 3 — Precisión de notificación (2026-07-04 → 2026-07-05) → v0.2.1, v0.3.0

Filtro de notificación por país `[COMMITS: a3a4a1a]`, resolviendo que un sismo a 80 km
puede estar en otro país. Se implementó como block-list y no como allow-list — decisión
deliberada, porque los sismos más peligrosos de Venezuela son *offshore* y no caen dentro
de ningún polígono terrestre.

Después, sembrado automático de `config.toml` desde plantilla en el primer arranque
`[COMMITS: a06f7a1]`: el usuario nuevo ya no parte de un archivo inexistente.

También aquí, un fix revelador: sanear `LD_LIBRARY_PATH` al lanzar binarios del sistema
`[COMMITS: a02607f]`, porque el bundle onefile de PyInstaller hacía que el reproductor de
sonido cargara las librerías del bundle en vez de las del sistema.

## Era 4 — Redundancia de fuentes (2026-07-05 → 2026-07-06) → v0.4.0, v0.5.0

De dos fuentes a cuatro. FUNVISIS `[COMMITS: 10bb72d]` para los sismos locales M2–3 que
EMSC y USGS no catalogan, con seen-set en memoria porque el endpoint no admite cursor.
GEOFON `[COMMITS: ade1199]` como cuarta red global independiente, para que un punto ciego
compartido entre EMSC y USGS no deje al agente mudo; corregido de inmediato a HTTPS
`[COMMITS: 8e0064a]`.

En paralelo se endureció la infraestructura: workflows de CI y seguridad más pre-commit
`[COMMITS: 97b2a8e]`, con tres fixes de CI en cadena `[COMMITS: 27e4b45, 0e707a1, f51da9c]`
— entre ellos "usar Python gestionado por uv para que tkinter esté disponible", el mismo
problema de entorno que sigue vivo hoy (ver `01-ARQUITECTURA.md` DT-5). Y un fix de fondo:
hacer el agente importable en un host headless `[COMMITS: 651c024]`.

## Era 5 — La corrección de frescura (2026-07-17) → v0.6.0

Un solo commit `[COMMITS: b0f832c]`, y el más interesante del historial. Investigando un
reporte de que el agente solo alertaba eventos de FUNVISIS, aparecieron **dos defectos
distintos**: ningún ingestor filtraba por *cuándo* ocurrió el sismo (un cursor rancio tras
días apagado podía surfacear un backlog de días), y `StateStore.prune()` existía con test
unitario propio desde la fase 1 pero **ninguna ruta de ejecución lo llamaba jamás** — el
estado crecía sin límite.

**Lección para la v2**: `prune()` tenía cobertura de tests y aun así estaba muerto. Un test
unitario prueba que una función *funciona*, no que alguien la *llama*. Los tests de
integración del pipeline son los que habrían detectado esto.

## Era 6 — Capas de conocimiento (2026-08-16)

Instalación de las tres capas de contexto (lat.md, CodeGraph, Graphify) y redacción de la
capa de intención `[COMMITS: 6e0f133]`. No cambia comportamiento; hace consultable el
*porqué* que hasta entonces vivía disperso en 18 ADRs.

## Lecciones para la v2

1. **Empaquetar es una feature, no un paso final.** Cuatro de los fixes del historial son
   de artefacto, no de lógica `[COMMITS: 7b1c71c, c38d9f6, bdc2a9d, a02607f]`. En la v2 el
   build de binarios debe existir desde la fase 1 y validar sus propios assets, en vez de
   aparecer en la fase 8 y descubrirse roto en producción.
2. **Cobertura ≠ ejecución.** `prune()` estuvo muerto durante 14 releases con test verde
   `[COMMITS: b0f832c]`. Añadir a la v2 una verificación de que las funciones públicas del
   dominio tienen al menos un llamador en ruta de ejecución.
3. **Nacer en inglés, con i18n desde el día uno.** La migración tardía `[COMMITS: 7f9132e]`
   fue un breaking change que tocó todo el árbol.
4. **Decidir Wayland antes de escribir la UI.** ADR-010 documenta a fondo el problema y su
   solución, y nunca se implementó. Es el mayor riesgo abierto: la promesa "imposible de
   ignorar" es frágil justo en el escritorio Linux por defecto.
5. **Fijar el entorno de tests, no solo las dependencias.** Los fixes de CI
   `[COMMITS: 0e707a1, 651c024]` y los dos tests que hoy exigen display real son el mismo
   problema recurrente: el suite asume un entorno gráfico que no siempre existe.
6. **El acoplamiento se concentró donde era predecible.** `app.py` (11 toques) y
   `config.py` (10) crecen con cada feature porque son el punto de cableado. Un registro de
   componentes o un contenedor de composición en la v2 evitaría que cada feature nueva
   modifique el mismo archivo.
