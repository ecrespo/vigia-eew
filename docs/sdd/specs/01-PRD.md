# PRD — Vigía-eew v2

> Versión 1.0 · 2026-09-06 · Nivel de rigor: **spec-anchored**
> Rige la **v2**. La especificación del sistema en producción (v0.6.0) sigue siendo
> `docs/PRD.md`; este documento no la reemplaza hasta que la v2 exista.

## 1. Alcance y no-alcance

**Qué es la v2.** Una reconstrucción del agente que conserva a paridad las capacidades verificadas
de la v0.6.0 y cierra las cinco brechas que las auditorías midieron: la garantía de alerta bajo
Wayland, la ausencia de umbral de cobertura, las fronteras no ejecutables, la condición de carrera
en el apagado y el coste de añadir una fuente.

**Qué NO es.** No es un rediseño de dominio: las cuatro fuentes, la heurística de deduplicación, el
filtro geográfico y el contrato interno se mantienen. No introduce servidor, base de datos ni
contenedores.

## 2. Cómo leer este PRD sin duplicar contenido

Este documento define **requisitos** en notación EARS con ID estable. **No repite los criterios de
aceptación**: cada REQ apunta a la Historia de Usuario de `docs/reverse-sdd/HU/` que ya contiene sus
escenarios Gherkin y sus casos de prueba, reconstruidos del código y del historial.

```
EARS (aquí)  =  el requisito, con REQ-ID     →  citado por Tasks y por los tests
Gherkin (allí) = los escenarios que lo verifican  →  ya escritos, 95 criterios / 157 casos
```

Un REQ **sin HU de respaldo** es capacidad nueva de la v2 y lleva sus criterios aquí mismo.

**Notación de prioridad:** `[MUST]` bloquea el release · `[SHOULD]` diferible con nota ·
`[MAY]` opcional.

**Convención de ID:** `REQ-{ÁREA}-{NNN}`, donde ÁREA son **2 o 3 letras mayúsculas**
(`ALE`, `ING`, `PIP`, `CFG`, `OPS`, `UX`, `OBS`). Expresión regular canónica para herramientas:
`REQ-[A-Z]{2,3}-\d{3}`. Un ID retirado no se reutiliza.

---

## 3. Requisitos — Alerta (REQ-ALE)

### REQ-ALE-001 `[MUST]` — Alerta no descartable *(por evento)*
CUANDO un evento supere los filtros de relevancia, EL SISTEMA DEBERÁ presentar una alerta que solo
se cierre mediante acuse explícito del usuario, ignorando `Escape`, el botón de cierre de la ventana
y la pérdida de foco.
→ Criterios y pruebas: [HU-004 CA-004.1](../../reverse-sdd/HU/HU-004-alerta-imposible-de-ignorar.md)

### REQ-ALE-002 `[MUST]` — Paridad de la garantía entre frontends *(ubicuo)*
EL SISTEMA DEBERÁ aplicar REQ-ALE-001 de forma idéntica en el frontend gráfico y en el de terminal.
→ [HU-011 CA-011.2](../../reverse-sdd/HU/HU-011-dashboard-tui-headless.md)

### REQ-ALE-003 `[MUST]` — Declaración de alcance bajo Wayland *(ubicuo)* · **NUEVO en v2**
EL SISTEMA DEBERÁ documentar en su README y en su primera ejecución el conjunto de entornos de
escritorio donde REQ-ALE-001 está garantizado, y DEBERÁ nombrar explícitamente aquellos donde no.

*Criterios (sin HU previa — capacidad nueva):*
- CUANDO el agente arranque en una sesión Wayland sin el mecanismo de presentación privilegiado,
  EL SISTEMA DEBERÁ registrar un aviso de una línea nombrando la limitación.
- EL SISTEMA DEBERÁ exponer esa condición en el menú de la bandeja o en la barra de estado del TUI.

*Racional: Art. 1 de la constitución. Hoy la promesa se hace sin acotar el entorno.*

### REQ-ALE-004 `[SHOULD]` — Presentación bajo Wayland *(opcional por entorno)*
DONDE el entorno de escritorio sea Wayland, EL SISTEMA DEBERÍA presentar la alerta mediante un
mecanismo que el compositor honre (servicio D-Bus con extensión de shell, o equivalente nativo),
cumpliendo REQ-ALE-001.
→ Diseño: ADR-010 de `docs/TECHNICAL-DESIGN.md` (especificado, nunca implementado) y
[Tech Design v2 §4](03-TECHNICAL-DESIGN.md).

> **Degradado de `[MUST]` a `[SHOULD]` el 2026-09-19 por la decisión D-1**, con el veredicto de
> [10-SPIKE-WAYLAND](../../v1/10-SPIKE-WAYLAND.md) delante. Razón: GNOME no implementa
> `zwlr_layer_shell_v1`, así que la única vía es una extensión de GNOME Shell —y aun
> implementándola, «la alerta funciona en Wayland» seguiría siendo falso en KDE, sway y cualquier
> otro escritorio. Cumplirlo no haría verdadera la frase que promete. **Queda fuera del corte de la
> v1.0.0**; el alcance real lo declara REQ-ALE-003, que sí está implementado.

### REQ-ALE-005 `[MUST]` — Una alerta a la vez *(por estado)*
MIENTRAS haya una alerta en pantalla, EL SISTEMA DEBERÁ encolar las siguientes en orden de llegada
y no presentarlas hasta que la actual sea acusada.
→ [HU-004 CA-004.4](../../reverse-sdd/HU/HU-004-alerta-imposible-de-ignorar.md)

### REQ-ALE-006 `[MUST]` — Actualización en sitio *(por evento)*
CUANDO llegue una actualización del evento que está en pantalla, EL SISTEMA DEBERÁ refrescar esa
alerta sin abrir otra ni reencolarla.
→ [HU-004 CA-004.4](../../reverse-sdd/HU/HU-004-alerta-imposible-de-ignorar.md), [HU-003 CA-003.5](../../reverse-sdd/HU/HU-003-pipeline-normalizacion-filtro-dedup.md)

### REQ-ALE-007 `[MUST]` — La pausa retiene, no descarta *(por estado)*
MIENTRAS la presentación esté pausada, EL SISTEMA DEBERÁ seguir encolando los eventos relevantes y
DEBERÁ presentarlos al reanudar.
→ [HU-009 CA-009.2](../../reverse-sdd/HU/HU-009-icono-bandeja.md)

### REQ-ALE-008 `[MUST]` — El contenido cabe en la ventana *(ubicuo)*
EL SISTEMA DEBERÁ dimensionar la ventana de alerta de modo que magnitud, lugar, hora y distancia
sean legibles sin recorte para el texto más largo que el contrato interno admite.
→ [HU-004 CA-004.3](../../reverse-sdd/HU/HU-004-alerta-imposible-de-ignorar.md)
*Racional: dos fixes históricos por síntoma (`f90c796`, `f0960ac`); en la v2 es requisito verificable.*

### REQ-ALE-009 `[SHOULD]` — Sonido escalado por severidad *(por evento)*
CUANDO se presente una alerta, EL SISTEMA DEBERÍA reproducir un aviso sonoro cuya insistencia
escale con la severidad, sin depender del sonido del toast del sistema.
→ [HU-004 CA-004.5](../../reverse-sdd/HU/HU-004-alerta-imposible-de-ignorar.md)

### REQ-ALE-010 `[MUST]` — Los efectos auxiliares no interrumpen *(no deseado)*
SI el reproductor de sonido, el notificador de escritorio o el ícono de bandeja fallan, ENTONCES EL
SISTEMA DEBERÁ registrar un aviso y continuar presentando la alerta visual.
→ [HU-004 CA-004.6](../../reverse-sdd/HU/HU-004-alerta-imposible-de-ignorar.md), [HU-009 CA-009.5](../../reverse-sdd/HU/HU-009-icono-bandeja.md)

---

## 4. Requisitos — Ingesta (REQ-ING)

### REQ-ING-001 `[MUST]` — Canal push primario *(ubicuo)*
EL SISTEMA DEBERÁ mantener una conexión WebSocket persistente con EMSC como canal de menor latencia.
→ [HU-002 CA-002.1](../../reverse-sdd/HU/HU-002-ingesta-emsc-usgs-supervisor.md)

### REQ-ING-002 `[MUST]` — Reconexión con backoff *(no deseado)*
SI la conexión push se interrumpe, ENTONCES EL SISTEMA DEBERÁ reconectar automáticamente con espera
exponencial acotada y jitter.
→ [HU-002 CA-002.2](../../reverse-sdd/HU/HU-002-ingesta-emsc-usgs-supervisor.md)

### REQ-ING-003 `[MUST]` — Reconciliación con cursor persistido *(por evento)*
CUANDO se cumpla el intervalo de sondeo, EL SISTEMA DEBERÁ consultar cada fuente REST con cursor
desde su última posición persistida, y DEBERÁ avanzar el cursor solo tras procesar la respuesta.
→ [HU-002 CA-002.3](../../reverse-sdd/HU/HU-002-ingesta-emsc-usgs-supervisor.md), [HU-015 CA-015.1](../../reverse-sdd/HU/HU-015-fuente-geofon.md)

### REQ-ING-004 `[MUST]` — Piso de consulta en medianoche local *(por evento)*
CUANDO el cursor persistido falte o sea anterior a la medianoche local del día en curso, EL SISTEMA
DEBERÁ anclar el `starttime` de la consulta en esa medianoche.
→ [HU-016 CA-016.5](../../reverse-sdd/HU/HU-016-frescura-backlog-poda.md)

### REQ-ING-005 `[MUST]` — Cobertura local sin cursor *(por evento)*
CUANDO la fuente local no ofrezca parámetro temporal, EL SISTEMA DEBERÁ distinguir lo nuevo con un
conjunto de vistos sembrado en el primer sondeo **sin emitir alertas**.
→ [HU-014 CA-014.1, CA-014.2](../../reverse-sdd/HU/HU-014-fuente-funvisis.md)

### REQ-ING-006 `[MUST]` — Ningún fallo de red detiene la ingesta *(no deseado)*
SI una fuente responde con error, agota el tiempo de espera o devuelve un cuerpo inválido, ENTONCES
EL SISTEMA DEBERÁ registrarlo y continuar en el siguiente ciclo, respetando `Retry-After` cuando el
servidor lo indique.
→ [HU-002 CA-002.4](../../reverse-sdd/HU/HU-002-ingesta-emsc-usgs-supervisor.md), [HU-014 CA-014.5](../../reverse-sdd/HU/HU-014-fuente-funvisis.md), [HU-015 CA-015.4](../../reverse-sdd/HU/HU-015-fuente-geofon.md)

### REQ-ING-007 `[MUST]` — Una fila corrupta no aborta el lote *(no deseado)*
SI una entrada de una respuesta no puede interpretarse, ENTONCES EL SISTEMA DEBERÁ descartar esa
entrada y procesar las restantes.
→ [HU-015 CA-015.3](../../reverse-sdd/HU/HU-015-fuente-geofon.md), [HU-003 CA-003.2](../../reverse-sdd/HU/HU-003-pipeline-normalizacion-filtro-dedup.md)

### REQ-ING-008 `[MUST]` — Transporte cifrado por defecto *(ubicuo)* · **REFORZADO en v2**
EL SISTEMA DEBERÁ usar HTTPS en todo endpoint que lo ofrezca, y DEBERÁ declarar por escrito, con su
justificación, cada endpoint que se consuma sin TLS.
→ [HU-015 CA-015.5](../../reverse-sdd/HU/HU-015-fuente-geofon.md)
*Racional: el endpoint de GEOFON se introdujo en HTTP y hubo que corregirlo (`8e0064a`); el de
FUNVISIS sigue sin TLS válido y se acepta por ser público y de solo lectura.*

### REQ-ING-009 `[MUST]` — Registro declarativo de fuentes *(ubicuo)* · **NUEVO en v2**
EL SISTEMA DEBERÁ declarar cada fuente en un registro único que asocie su configuración, su
ingestor y su mapeo de normalización, de modo que añadir una fuente no requiera modificar el
ensamblador ni el normalizador.

*Criterio verificable:* añadir una fuente ficticia en un test DEBERÁ tocar exactamente tres puntos
(ingestor, mapeo, entrada del registro).
*Racional: hoy cuesta ≥5 archivos (`docs/arch-eval/` P2-4, ADR-001).*

### REQ-ING-010 `[MUST]` — Independencia entre fuentes *(ubicuo)*
EL SISTEMA DEBERÁ mantener los ingestores mutuamente independientes: ninguno importa a otro.
*Verificable por el contrato 4 de import-linter (Art. 5).*

---

## 5. Requisitos — Pipeline (REQ-PIP)

### REQ-PIP-001 `[MUST]` — Contrato interno único *(ubicuo)*
EL SISTEMA DEBERÁ convertir todo mensaje de cualquier fuente a un único tipo de evento interno, y
DEBERÁ calcular distancia y severidad en esa conversión en lugar de tomarlas del origen.
→ [HU-003 CA-003.1](../../reverse-sdd/HU/HU-003-pipeline-normalizacion-filtro-dedup.md)

### REQ-PIP-002 `[MUST]` — Orden filtro→dedup *(ubicuo)*
EL SISTEMA DEBERÁ evaluar los filtros de relevancia **antes** de la deduplicación, de modo que un
evento descartado no altere el estado de deduplicación.
→ [HU-003](../../reverse-sdd/HU/HU-003-pipeline-normalizacion-filtro-dedup.md), [HU-016](../../reverse-sdd/HU/HU-016-frescura-backlog-poda.md)

### REQ-PIP-003 `[MUST]` — Relevancia por radio y magnitud *(por evento)*
CUANDO se evalúe un evento, EL SISTEMA DEBERÁ descartarlo si está fuera del radio configurado o por
debajo de la magnitud mínima; ambos límites son inclusivos.
→ [HU-003 CA-003.3](../../reverse-sdd/HU/HU-003-pipeline-normalizacion-filtro-dedup.md)

### REQ-PIP-004 `[MUST]` — Frescura por día local *(por evento)*
CUANDO se evalúe un evento, EL SISTEMA DEBERÁ descartarlo salvo que su instante, convertido al día
calendario local de la zona configurada, sea el día en curso.
→ [HU-016 CA-016.1, CA-016.2](../../reverse-sdd/HU/HU-016-frescura-backlog-poda.md)

### REQ-PIP-005 `[MUST]` — Filtro de país como lista de bloqueo *(opcional)*
DONDE el filtro de país esté habilitado, EL SISTEMA DEBERÁ descartar únicamente los eventos que
estén positivamente dentro de otro país, y DEBERÁ conservar los de país indeterminado o marítimos.
→ [HU-012 CA-012.1, CA-012.2](../../reverse-sdd/HU/HU-012-filtro-de-pais.md)

### REQ-PIP-006 `[MUST]` — Filtros inertes ante configuración inválida *(no deseado)*
SI un filtro opcional no puede evaluarse con confianza —zona horaria inválida, país del usuario
indeterminable—, ENTONCES EL SISTEMA DEBERÁ dejarlo inerte, registrar un aviso una sola vez y no
suprimir ningún evento.
→ [HU-012 CA-012.3](../../reverse-sdd/HU/HU-012-filtro-de-pais.md), [HU-016 CA-016.3](../../reverse-sdd/HU/HU-016-frescura-backlog-poda.md)
*Racional: Art. 3.*

### REQ-PIP-007 `[MUST]` — Ningún filtro opcional amplía lo que el radio descartó *(ubicuo)*
EL SISTEMA DEBERÁ aplicar radio y magnitud como condición necesaria: ningún filtro adicional puede
admitir un evento que aquellos rechazaron.
→ [HU-012 CA-012.4](../../reverse-sdd/HU/HU-012-filtro-de-pais.md), [HU-016 CA-016.4](../../reverse-sdd/HU/HU-016-frescura-backlog-poda.md)

### REQ-PIP-008 `[MUST]` — Identidad heurística entre fuentes *(no deseado)*
SI dos eventos de fuentes distintas están dentro de los umbrales configurados de distancia, tiempo
y magnitud, ENTONCES EL SISTEMA DEBERÁ tratarlos como el mismo sismo y presentar una sola alerta.
→ [HU-003 CA-003.4](../../reverse-sdd/HU/HU-003-pipeline-normalizacion-filtro-dedup.md), [HU-015 CA-015.6](../../reverse-sdd/HU/HU-015-fuente-geofon.md)

### REQ-PIP-009 `[MUST]` — La heurística es agnóstica al número de fuentes *(ubicuo)*
EL SISTEMA DEBERÁ mantener la deduplicación independiente de cuántas fuentes existan: añadir una no
altera los umbrales ni la lógica.
→ [HU-015 CA-015.6](../../reverse-sdd/HU/HU-015-fuente-geofon.md)

---

## 6. Requisitos — Estado y configuración (REQ-CFG)

### REQ-CFG-001 `[MUST]` — Sin re-alerta tras reinicio *(por evento)*
CUANDO el agente arranque, EL SISTEMA DEBERÁ cargar lo ya alertado y no volver a presentarlo.
→ [HU-001 CA-001.3](../../reverse-sdd/HU/HU-001-contrato-configuracion-estado.md), [HU-003 CA-003.6](../../reverse-sdd/HU/HU-003-pipeline-normalizacion-filtro-dedup.md)

### REQ-CFG-002 `[MUST]` — Escritura atómica y tolerante a corrupción *(no deseado)*
SI el archivo de estado está corrupto o ausente, ENTONCES EL SISTEMA DEBERÁ arrancar con estado
vacío; toda escritura DEBERÁ ser atómica y no dejar temporales huérfanos.
→ [HU-001 CA-001.4](../../reverse-sdd/HU/HU-001-contrato-configuracion-estado.md)

### REQ-CFG-003 `[MUST]` — Estado acotado en el tiempo *(por evento)*
CUANDO se registre una alerta nueva, EL SISTEMA DEBERÁ podar las entradas anteriores a la ventana
de retención antes de persistir.
→ [HU-016 CA-016.6](../../reverse-sdd/HU/HU-016-frescura-backlog-poda.md)
*Racional: la poda existía sin ninguna ruta que la llamara durante 14 fases (`b0f832c`).*

### REQ-CFG-004 `[MUST]` — Los cursores solo avanzan *(no deseado)*
SI se intenta retroceder un cursor de fuente, ENTONCES EL SISTEMA DEBERÁ conservar el valor actual.
→ [HU-001 CA-001.5](../../reverse-sdd/HU/HU-001-contrato-configuracion-estado.md)

### REQ-CFG-005 `[MUST]` — Configuración validada y de solo lectura *(ubicuo)*
EL SISTEMA DEBERÁ leer su configuración de un archivo TOML validado por esquema y DEBERÁ fallar de
forma explícita ante una configuración inválida o una ruta explícita inexistente.
→ [HU-001 CA-001.6](../../reverse-sdd/HU/HU-001-contrato-configuracion-estado.md)

### REQ-CFG-006 `[MUST]` — Siembra en el primer arranque *(por evento)*
CUANDO no exista configuración en la ruta por defecto, EL SISTEMA DEBERÁ crearla desde la plantilla
empaquetada sin sobrescribir nunca un archivo existente.
→ [HU-013 CA-013.1, CA-013.2](../../reverse-sdd/HU/HU-013-semilla-configuracion.md)

### REQ-CFG-007 `[MUST]` — Ubicación automática una sola vez *(por evento)*
CUANDO no haya punto de referencia manual ni ubicación cacheada, EL SISTEMA DEBERÁ detectarla una
sola vez antes de iniciar la ingesta y persistirla; un fallo NO DEBERÁ cachearse.
→ [HU-008 CA-008.1, CA-008.3](../../reverse-sdd/HU/HU-008-ubicacion-automatica-ip.md)

### REQ-CFG-008 `[MUST]` — La simulación no usa red *(opcional)*
DONDE el modo simulación esté activo, EL SISTEMA DEBERÁ presentar la alerta de prueba sin abrir
ninguna conexión, incluida la de geolocalización.
→ [HU-005 CA-005.2](../../reverse-sdd/HU/HU-005-cli-ensamblaje-simulacion.md), [HU-008 CA-008.5](../../reverse-sdd/HU/HU-008-ubicacion-automatica-ip.md)

---

## 7. Requisitos — Operación (REQ-OPS)

### REQ-OPS-001 `[MUST]` — Supervisión con reinicio aislado *(no deseado)*
SI una tarea de larga vida falla, ENTONCES EL SISTEMA DEBERÁ reiniciarla con backoff sin afectar a
las demás y sin terminar el proceso.
→ [HU-002 CA-002.5](../../reverse-sdd/HU/HU-002-ingesta-emsc-usgs-supervisor.md)

### REQ-OPS-002 `[MUST]` — Apagado limpio y determinista *(por evento)* · **REFORZADO en v2**
CUANDO se solicite la parada, EL SISTEMA DEBERÁ cancelar todas las tareas vivas y terminar sin
tareas huérfanas, **independientemente del instante en que llegue la solicitud respecto al arranque
del bucle de eventos**.

*Criterio verificable adicional (nuevo):* SI la parada llega antes de que el hilo trabajador haya
publicado su bucle y su supervisor, ENTONCES EL SISTEMA DEBERÁ esperar a que estén disponibles o
registrar un aviso nombrando la situación — nunca omitir la cancelación en silencio.
→ Parcial en [HU-002 CA-002.6](../../reverse-sdd/HU/HU-002-ingesta-emsc-usgs-supervisor.md); el criterio nuevo viene de `docs/arch-eval/` P2-1 y ADR-002.

### REQ-OPS-003 `[MUST]` — Estado compartido declarado *(ubicuo)* · **NUEVO en v2**
EL SISTEMA DEBERÁ documentar, para cada dato mutable accedido por más de un hilo, a qué hilo
pertenece y con qué primitiva se sincroniza.
*Racional: Art. 6.*

### REQ-OPS-004 `[MUST]` — Autoarranque nativo por plataforma *(por evento)*
CUANDO el usuario solicite instalar el arranque automático, EL SISTEMA DEBERÁ registrarlo con el
mecanismo nativo de su plataforma y DEBERÁ poder revertirlo sin dejar residuos.
→ [HU-006](../../reverse-sdd/HU/HU-006-autoarranque-multiplataforma.md)

### REQ-OPS-005 `[MUST]` — Entorno saneado para subprocesos *(ubicuo)*
EL SISTEMA DEBERÁ lanzar todo binario del sistema con un entorno del que se hayan retirado las
rutas de librerías inyectadas por el empaquetador.
→ [HU-006 CA-006.5](../../reverse-sdd/HU/HU-006-autoarranque-multiplataforma.md)

### REQ-OPS-006 `[MUST]` — Distribución sin entorno de desarrollo *(por evento)*
CUANDO se publique una versión, EL SISTEMA DEBERÁ producir un paquete instalable y binarios
autocontenidos por plataforma.
→ [HU-007](../../reverse-sdd/HU/HU-007-empaquetado-binarios-release.md)

### REQ-OPS-007 `[MUST]` — Validación de artefactos de empaquetado *(no deseado)* · **NUEVO en v2**
SI un recurso requerido por el empaquetador tiene formato o dimensiones inválidas, ENTONCES la
construcción DEBERÁ fallar con un mensaje que nombre el recurso, antes de invocar al empaquetador.

*Criterio verificable:* un recurso deliberadamente inválido hace fallar el pipeline de build.
*Racional: rompió dos releases consecutivas (`7b1c71c`, `c38d9f6`) y hoy no hay ningún test
(`docs/code-audit/` TC-007.4).*

### REQ-OPS-008 `[MUST]` — El binario producido se verifica *(por evento)* · **NUEVO en v2**
CUANDO el pipeline construya un binario, EL SISTEMA DEBERÁ ejecutarlo en modo simulación y
comprobar que presenta y acusa una alerta antes de publicar.
*Racional: `docs/code-audit/` TC-007.7; hoy los recursos faltantes en el binario solo se descubren
en ejecución (`bdc2a9d`).*

---

## 8. Requisitos — Interfaz y localización (REQ-UX)

### REQ-UX-001 `[MUST]` — Idioma del sistema *(por evento)*
CUANDO el agente arranque, EL SISTEMA DEBERÁ presentar sus textos en el idioma detectado del
sistema operativo, y DEBERÁ permitir forzarlo por configuración.
→ [HU-010 CA-010.1, CA-010.3](../../reverse-sdd/HU/HU-010-i18n-ingles.md)

### REQ-UX-002 `[MUST]` — Degradación de idioma *(no deseado)*
SI el idioma detectado o configurado no está soportado, ENTONCES EL SISTEMA DEBERÁ usar inglés y
nunca fallar.
→ [HU-010 CA-010.2](../../reverse-sdd/HU/HU-010-i18n-ingles.md)

### REQ-UX-003 `[MUST]` — Código fuente en inglés desde el inicio *(ubicuo)*
EL SISTEMA DEBERÁ escribirse íntegramente en inglés —código, docstrings, comentarios, mensajes de
commit y artefactos— con los textos de usuario internacionalizados desde la primera fase.
→ [HU-010 CA-010.5](../../reverse-sdd/HU/HU-010-i18n-ingles.md)
*Racional: hacerlo tarde costó un `feat!` de 30+ archivos con renombrado de assets binarios (`7f9132e`).*

### REQ-UX-004 `[MUST]` — Estado y control sin terminal *(por evento)*
CUANDO el agente corra en una sesión gráfica, EL SISTEMA DEBERÁ ofrecer estado de conexión, última
alerta, pausa/reanudación, edición de configuración y salida desde un ícono de bandeja.
→ [HU-009](../../reverse-sdd/HU/HU-009-icono-bandeja.md)

### REQ-UX-005 `[MUST]` — Operación headless *(opcional)*
DONDE no haya sesión gráfica, EL SISTEMA DEBERÁ ofrecer un panel de terminal con las mismas
capacidades de estado, alerta y control.
→ [HU-011](../../reverse-sdd/HU/HU-011-dashboard-tui-headless.md)

### REQ-UX-006 `[MUST]` — Modo de prueba sin esperar un sismo *(por evento)*
CUANDO el usuario invoque el modo simulación, EL SISTEMA DEBERÁ presentar una alerta completa para
verificar ventana, sonido y notificación en su máquina.
→ [HU-005 CA-005.2](../../reverse-sdd/HU/HU-005-cli-ensamblaje-simulacion.md)

---

## 9. Requisitos — Observabilidad y calidad (REQ-OBS)

### REQ-OBS-001 `[MUST]` — Registro estructurado en UTC *(ubicuo)*
EL SISTEMA DEBERÁ registrar cada transición relevante con claves estables y marcas de tiempo en UTC.
→ Presente en v0.6.0; sin HU propia (capacidad transversal).

### REQ-OBS-002 `[MUST]` — Identificador de correlación *(ubicuo)* · **NUEVO en v2**
EL SISTEMA DEBERÁ propagar un identificador de correlación desde la ingesta hasta la presentación,
de modo que el recorrido completo de un sismo —incluidas las llegadas por fuentes distintas que se
deduplican— sea reconstruible con una sola búsqueda en los registros.

*Criterio verificable:* dado un sismo reportado por dos fuentes, una búsqueda por su identificador
de correlación devuelve las entradas de ingesta, normalización, filtro, veredicto de deduplicación
y presentación.
*Racional: `docs/arch-eval/` atributo 6 y P3-1.*

### REQ-OBS-003 `[MUST]` — Umbral de cobertura por criticidad *(ubicuo)* · **NUEVO en v2**
EL SISTEMA DEBERÁ hacer fallar el CI cuando la cobertura de líneas y ramas caiga por debajo del
umbral asignado a cada módulo: ≥85 % en pipeline y estado, ≥70 % en ingesta, ≥40 % en adaptadores
de E/S.
*Racional: Art. 8. Hoy la cobertura se mide y se archiva, pero no se exige (`docs/code-audit/` P2-1).*

### REQ-OBS-004 `[MUST]` — Separación de pruebas por tipo *(ubicuo)* · **NUEVO en v2**
EL SISTEMA DEBERÁ marcar sus pruebas de integración y de interfaz gráfica de modo que el lote
rápido pueda ejecutarse por separado en el gate de commit.
*Racional: `docs/code-audit/` P2-3.*

### REQ-OBS-005 `[MUST]` — Fronteras verificadas por herramienta *(ubicuo)* · **NUEVO en v2**
EL SISTEMA DEBERÁ declarar sus fronteras de importación como contratos verificables y el CI DEBERÁ
fallar ante una violación o un ciclo nuevo.
*Racional: Art. 5; `docs/arch-eval/` ADR-003.*

---

## 10. Trazabilidad y cobertura

| Área | REQs | MUST | SHOULD | Nuevos en v2 |
|---|---|---|---|---|
| Alerta (ALE) | 10 | 9 | 1 | 2 |
| Ingesta (ING) | 10 | 10 | 0 | 1 |
| Pipeline (PIP) | 9 | 9 | 0 | 0 |
| Estado y config (CFG) | 8 | 8 | 0 | 0 |
| Operación (OPS) | 8 | 8 | 0 | 3 |
| Interfaz (UX) | 6 | 6 | 0 | 0 |
| Observabilidad (OBS) | 5 | 5 | 0 | 4 |
| **Total** | **56** | **55** | **1** | **10** |

**46 de los 56 REQ heredan sus criterios Gherkin** de las 17 Historias de Usuario de
`docs/reverse-sdd/HU/` (95 criterios, 157 casos de prueba). **Los 10 nuevos** llevan sus criterios
aquí y necesitan pruebas escritas desde cero — son la primera prioridad del plan.

Requisitos de la v0.6.0 **retirados** en la v2: ninguno. Los IDs `RF-xx` de `docs/PRD.md` siguen
siendo la numeración del sistema en producción; la correspondencia `RF-xx ↔ REQ-xxx-NNN` está en
[07-ANALYZE.md §6](07-ANALYZE.md).

---

## 11. Constitution check

| Artículo | Cómo lo cumple este PRD |
|---|---|
| Art. 1 (la alerta es el producto) | REQ-ALE-001..004; ALE-003 y ALE-004 cierran la brecha de Wayland que el artículo exige declarar |
| Art. 2 (nada se pierde, nada se repite) | REQ-ALE-007, REQ-CFG-001, REQ-PIP-008 |
| Art. 3 (fail-safe) | REQ-PIP-006, REQ-ALE-010, REQ-ING-006 |
| Art. 4 (UTC) | REQ-PIP-001, REQ-PIP-004 (día local solo en el borde) |
| Art. 5 (fronteras ejecutables) | REQ-OBS-005, REQ-ING-010 |
| Art. 6 (estado compartido) | REQ-OPS-002, REQ-OPS-003 |
| Art. 8 (gate de ocho dimensiones) | REQ-OBS-003, REQ-OBS-004, REQ-OPS-007 |

**Excepciones solicitadas:** una. REQ-ING-008 permite consumir un endpoint sin TLS (FUNVISIS,
que no ofrece HTTPS válido) **con la condición** de declararlo por escrito con su justificación:
el dato es público, de solo lectura, y no cruzan credenciales ni datos de usuario. Sin esa
excepción se perdería la cobertura sísmica local, que es OBJ-3 para la geografía principal del
producto.
