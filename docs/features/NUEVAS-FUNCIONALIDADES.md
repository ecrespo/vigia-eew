# Nuevas funcionalidades — catálogo evaluado

> Fecha: 2026-08-16 · Commit base: `535740c`
> Cada ficha lleva: qué es, qué evidencia la respalda (competencia o análisis propio),
> esfuerzo, y **constitution check** contra `specs/constitution.md`.
> Las funcionalidades ya especificadas apuntan a su Delta Spec.

## 1. Panorama competitivo

Herramientas comparables, investigadas para situar a Vigía-eew:

| Herramienta | Tipo | Qué hace bien | Qué le falta / limita |
|---|---|---|---|
| **[MyShake](https://myshake.berkeley.edu/)** (UC Berkeley + Cal OES) | Móvil + escritorio | Alerta real anticipada vía ShakeAlert (M4.5+) en CA/OR/WA; convierte el móvil en sismómetro con el acelerómetro; notificaciones configurables por región y magnitud | Alerta anticipada solo en la costa oeste de EE. UU.; fuera de ahí es un notificador |
| **[LastQuake](https://www.emsc-csem.org/)** (EMSC) | Móvil | Rapidez post-sismo: detecta terremotos por picos de tráfico web; reportes ciudadanos y fotos; mapas | **No es early warning** — su fuerza es la media hora *después*, no los segundos *antes* |
| **[Earthquake Network](https://www.earthquakenetwork.it/)** | Móvil | Red colaborativa de detección con acelerómetros de móviles; alerta anticipada donde hay densidad de usuarios | Depende de masa crítica de usuarios en la zona |
| **[JQuake](https://jquake.net/en/)** | **Escritorio** (Win/Mac/Linux) | Monitor de movimiento fuerte en tiempo real; muestra estaciones individuales; avisos de EEW de la JMA **y de tsunami** | Solo Japón; los EEW quedaron tras un servicio de pago al cambiar los términos de NIED |
| **[GlobalQuake](https://github.com/xspanger3770/GlobalQuake)** | **Escritorio**, open source | Monitoriza sismos globalmente **en near-real-time desde formas de onda** (SeedLink + FDSNWS) y **emite sus propias alertas**; globo interactivo; escalas de intensidad con sonido | Repositorio archivado (mar-2025); el desarrollo siguió en plataforma propietaria |
| **[OpenEEW](https://openeew.com/)** (Grillo + IBM + Linux Foundation) | Plataforma open source | Sensores IoT de bajo coste (ESP32) publicando aceleraciones por MQTT; algoritmos de detección; pensado para comunidades desatendidas | Requiere desplegar hardware |
| **Vigía-eew** | **Escritorio** | 4 redes con dedup entre fuentes; alerta imposible de ignorar; cobertura local de Venezuela; sin servidor ni cuenta | Notifica por magnitud+radio; **no dice cuántos segundos faltan**; sin mapa ni intensidad estimada |

### Las tres lecciones que deja la comparación

1. **Nadie más cubre Venezuela con FUNVISIS.** Es la ventaja defendible del proyecto y
   ninguna herramienta global la replica.
2. **La brecha conceptual está en el "early".** ShakeAlert alerta por **intensidad
   esperada** (MMI III+) y comunica el tiempo hasta la sacudida; Vigía-eew alerta por
   magnitud y distancia, que es un proxy grueso: un M6.0 a 200 km y un M4.2 a 15 km pueden
   producir la misma sacudida en casa, y hoy el primero alerta y el segundo puede no
   hacerlo.
3. **GlobalQuake demuestra que un escritorio puede detectar, no solo esperar.** Consume
   formas de onda por SeedLink en vez de esperar a que un catálogo publique el evento.
   Ahí están los segundos que separan "notificación" de "alerta temprana".

## 2. Catálogo de funcionalidades

Prioridad: **A** = alto valor/coste razonable · **B** = valioso pero costoso o dependiente
· **C** = interesante, conflictivo o prematuro.

---

### F-01 · Panel de configuración desde la bandeja · **A**
*Solicitado por el usuario · Ya especificado:
[`changes/2026-08-panel-de-configuracion/`](../../changes/2026-08-panel-de-configuracion/delta-spec.md) (RF-43…RF-47)*

Hoy "Editar configuración" abre `config.toml` en un editor de texto: el usuario tiene que
saber TOML y un error solo se descubre en el siguiente arranque. Un panel con validación
elimina esa clase entera de fallo.

**Esfuerzo**: M (~1 semana) · **Constitution check**: ✅ todos los artículos; requiere
ADR-023 porque contradice el "solo lectura" de ADR-007.

---

### F-02 · Selección de redes sísmicas · **A**
*Solicitado por el usuario · Ya especificado: mismo delta (RF-48…RF-52)*

Listar las cuatro redes con su cobertura y tipo de canal, permitir activarlas, y admitir
el registro de redes FDSN adicionales por URL. Un usuario en Chile debería poder ver que
FUNVISIS no le sirve y añadir la red de su país.

**Hallazgo de diseño**: registrar redes FDSN **activa el disparador que ADR-016 dejó
escrito** ("unificar los pollers cuando llegue la tercera fuente FDSN"). La funcionalidad
paga la deuda técnica que `code-audit` R-07 y `arch-eval` ya habían señalado.

**Esfuerzo**: L (~2 semanas, incluye el refactor) · **Constitution check**: ✅; el
registro de una red añade un destino elegido por el usuario, no por el producto (Art. 7).

---

### F-03 · Cuenta atrás hasta la llegada de la sacudida · **A**
*Inspirado en ShakeAlert / MyShake · Sin dependencias nuevas*

Mostrar en la alerta **cuántos segundos faltan** para que llegue la onda S, calculado
desde la distancia hipocentral y una velocidad de propagación (~3,5 km/s), descontando la
latencia ya transcurrida desde el origen del sismo.

Es la funcionalidad que más cambia la naturaleza del producto por menos código: convierte
"ha ocurrido un sismo a 80 km" en "la sacudida llega en ~18 segundos". Toda la información
necesaria **ya está** en `SeismicEvent` (`time_utc`, `distance_km`, `depth_km`).

Honestidad obligatoria en el diseño: si el evento llegó con más retraso que el tiempo de
viaje, la cuenta atrás es negativa y **hay que decirlo** ("la sacudida ya debería haber
llegado"), no ocultarlo. Con las fuentes actuales, basadas en catálogo, ese será el caso
frecuente — y precisamente por eso F-05 es su continuación natural.

**Esfuerzo**: S (~2-3 días) · **Constitution check**: ✅ Art. 1 (enriquece la alerta sin
tocar el contrato), Art. 4 (aritmética sobre instantes UTC).

---

### F-04 · Alertar por intensidad esperada, no solo por magnitud y radio · **A**
*Alineado con ShakeAlert (umbral MMI III+) · Sin dependencias nuevas*

Estimar la intensidad de Mercalli esperada en la ubicación del usuario con una ecuación
de predicción de movimiento del suelo (magnitud + distancia + profundidad → PGA → MMI), y
permitir que el filtro y la severidad se basen en ella.

Corrige la distorsión estructural del filtro actual: hoy un M6.0 lejano y superficial
compite con un M4.2 cercano usando dos criterios independientes, cuando lo que le importa
al usuario es **cuánto va a temblar donde está**.

Diseño respetuoso con la constitución: se añade como **modo opcional**
(`[filter] mode = "radius" | "intensity"`), con `radius` por defecto. Cambiar el criterio
por defecto alteraría en silencio qué se alerta para todos los usuarios instalados.

**Esfuerzo**: M (~1 semana, la mayor parte en elegir y validar la ecuación) ·
**Constitution check**: ✅ Art. 2 (si la estimación no se puede calcular, se cae al filtro
por radio, nunca se suprime).

---

### F-05 · Ingesta de formas de onda por SeedLink · **B**
*Lo que hace GlobalQuake · Dependencia nueva*

Conectarse a servidores SeedLink (protocolo estándar de streaming sísmico en tiempo real)
para recibir datos de estaciones en vez de esperar a que un catálogo publique el evento.
Es el salto real de latencia: de decenas de segundos a unos pocos.

**El coste es alto y hay que decirlo**: implica detección propia (STA/LTA o similar),
volumen de datos continuo, y probablemente `obspy` — una dependencia científica pesada
frente a las nueve ligeras actuales. Contradice el espíritu de RNF-06 y exige un ADR que
lo justifique explícitamente.

**Esfuerzo**: XL (~1-2 meses) · **Constitution check**: ⚠️ tensión con la restricción de
dependencias; el resto de artículos se preserva.

---

### F-06 · Mapa del evento en la alerta · **B**
*Presente en MyShake, LastQuake, JQuake y GlobalQuake*

Mostrar epicentro y ubicación del usuario en un mapa pequeño dentro de la alerta. El
proyecto **ya tiene** el activo necesario: `assets/countries.geojson` (Natural Earth
1:110m) y un motor de punto-en-polígono, así que se puede dibujar sin red ni tiles
externos.

**Esfuerzo**: M · **Constitution check**: ✅ Art. 7 (sin llamadas de red: se dibuja del
asset embebido, nunca de un servidor de tiles).

---

### F-07 · Reportes ciudadanos "¿lo sentiste?" · **C**
*Lo que mejor hace LastQuake*

Permitir al usuario reportar si sintió el sismo y con qué intensidad, alimentando un mapa
colectivo.

**Conflicto directo con la arquitectura**: requiere un servidor que reciba los reportes, y
ADR-008 decidió deliberadamente no tener componente central. Además, enviar la ubicación
del usuario a un servicio choca con Art. 7. **No se recomienda** sin reabrir ADR-008 con
un análisis de coste operativo. Alternativa que sí encaja: registrar el reporte
**localmente**, para el historial del propio usuario (ver F-10).

**Constitution check**: ❌ Art. 7 y ADR-008 en su forma con servidor.

---

### F-08 · Avisos de tsunami · **B**
*Presente en JQuake*

Para un país con costa caribeña, un sismo submarino relevante debería poder derivar en un
aviso de tsunami. Fuentes candidatas: los boletines del Pacific Tsunami Warning Center y
del Caribe (CATAC), que publican en formatos consultables.

Requiere investigación previa de la fuente venezolana/caribeña autoritativa y de su
formato, y probablemente una severidad nueva por encima de `critical`.

**Esfuerzo**: L · **Constitution check**: ✅, encaja en el patrón de fuente nueva ya
probado cuatro veces.

---

### F-09 · Descubrimiento de redes FDSN · **C**
*Extensión natural de F-02*

Consultar el catálogo de servicios FDSN para ofrecer una lista de redes en vez de exigir
que el usuario escriba la URL.

Se dejó **fuera** del delta de F-02 a propósito: añade una llamada de red y una lista que
el producto no controla. Tiene sentido solo si F-02 demuestra que escribir la URL a mano
es una barrera real.

**Esfuerzo**: M · **Constitution check**: ⚠️ Art. 7 — llamada nueva a un tercero, aunque
sea a petición explícita del usuario.

---

### F-10 · Historial local y estadísticas · **A**
*Ninguna herramienta comparable lo hace bien en escritorio*

Una vista con los sismos de los últimos 30 días que pasaron el filtro: cuáles se
alertaron, cuáles se descartaron y **por qué** (fuera de radio, magnitud baja, otro país,
día anterior, duplicado de otra fuente).

Responde la pregunta operativa real del producto —"¿por qué no me avisó del sismo X?"—
que hoy exige leer logs, y de paso mitiga DEB-05 del informe de arquitectura (el id del
evento no se propaga por toda la cadena de logs). El estado persistido ya guarda parte de
lo necesario.

**Esfuerzo**: M · **Constitution check**: ✅ Art. 7 (todo local, nada sale de la máquina).

---

### F-11 · Múltiples puntos de referencia · **B**

Vigilar varias ubicaciones —casa, trabajo, la casa de los padres— con radio y magnitud
propios cada una, y que la alerta indique cuál se vio afectada.

Es una generalización natural de `[reference]`, que hoy es un único punto. El filtro
pasaría a evaluar N referencias y quedarse con la más restrictiva.

**Esfuerzo**: M · **Constitution check**: ✅ Art. 2 (con varias referencias, basta que una
acepte para no suprimir).

---

### F-12 · Perfil de accesibilidad · **A**

La garantía del producto es "imposible de ignorar", y hoy descansa en una ventana modal
más sonido. Para una persona sorda o con baja visión, media garantía se pierde en
silencio.

Concreto: destello de pantalla completa configurable, contraste y tamaño de tipografía
ajustables, y compatibilidad verificada con lectores de pantalla en el texto de la alerta.

**Esfuerzo**: M · **Constitution check**: ✅ Art. 1 — es la interpretación literal del
artículo, no una extensión: hoy la promesa no se cumple para todos los usuarios.

---

### F-13 · Simulacro programado · **B**

`--simulate` ya existe y funciona sin red. Falta poder **programarlo**: un simulacro
mensual automático que verifique de punta a punta que el agente sigue funcionando en esa
máquina — que el sonido suena, que la ventana aparece, que la bandeja responde.

Es el equivalente a probar el detector de humo. Para un agente que puede pasar meses sin
alertar, es la única forma de saber que sigue vivo.

**Esfuerzo**: S · **Constitution check**: ✅ Art. 3.

---

### F-14 · Publicar alertas en formato CAP · **C**
*Estándar OASIS usado por USGS, NOAA y Google Public Alerts*

Emitir las alertas en Common Alerting Protocol permitiría integrarlas con otros sistemas
—megafonía, domótica, paneles— sin acoplarse a Vigía-eew.

Interesante para un despliegue institucional (un colegio, una empresa), pero hoy no hay
demanda conocida y el producto es explícitamente personal. **Revisar si aparece un caso
de uso organizacional** — el mismo disparador que reabriría ADR-008.

**Esfuerzo**: M · **Constitution check**: ✅ técnicamente; ⚠️ de producto (¿es este el
producto que se quiere?).

---

## 3. Resumen de prioridad

| Prioridad | Funcionalidades | Criterio |
|---|---|---|
| **A** (6) | F-01, F-02, F-03, F-04, F-10, F-12 | Alto valor, coste contenido, sin conflicto constitucional |
| **B** (5) | F-05, F-06, F-08, F-11, F-13 | Valiosas, pero costosas o dependientes de las A |
| **C** (3) | F-07, F-09, F-14 | Conflictivas con ADR-008/Art. 7, o prematuras |

La secuencia recomendada está en [`ROADMAP.md`](ROADMAP.md).

## Fuentes

- [MyShake — UC Berkeley Seismology Lab](https://myshake.berkeley.edu/)
- [MyShake en App Store](https://apps.apple.com/us/app/myshake-earthquake-alerts/id1467058529) · [Cal OES: nuevas herramientas MyShake](https://www.news.caloes.ca.gov/cal-oes-and-uc-berkeley-announce-new-myshake-tools-for-early-earthquake-notification/)
- [LastQuake — EMSC](https://play.google.com/store/apps/details?id=org.emsc_csem.lastquake)
- [Earthquake Network](https://alternativeto.net/software/earthquake-network)
- [JQuake](https://jquake.net/en/) · [JQuake — About](https://jquake.net/en/about.html)
- [GlobalQuake (GitHub)](https://github.com/xspanger3770/GlobalQuake)
- [OpenEEW](https://openeew.com/) · [OpenEEW en GitHub](https://github.com/openeew/openeew)
- [USGS — Earthquake Early Warning Overview](https://www.usgs.gov/programs/earthquake-hazards/science/earthquake-early-warning-overview)
- [Real-Time Seismic Intensity Prediction for EEW (revisión sistemática, PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10255511/)
- [ESenTRy: EEW on-site basado en intensidad de Mercalli instrumental](https://link.springer.com/article/10.1007/s12145-024-01407-2)
- [Common Alerting Protocol (Wikipedia)](https://en.wikipedia.org/wiki/Common_Alerting_Protocol) · [Google Public Alerts — requisitos CAP](https://developers.google.com/public-alerts/guides/cap-requirements/overview)
- [ObsPy — cliente SeedLink](https://docs.obspy.org/packages/obspy.clients.seedlink.html)
