# Estimación de esfuerzo — Vigía-eew v1.0

> Artefacto 09 del kit v1.0 · 2026-09-06 · Base: las 49 tareas de [07-TASKS.md](07-TASKS.md)
>
> **Esto es una estimación de ingeniería, no un compromiso.** Se publica con su método, sus
> supuestos y sus fuentes de error para que se pueda discutir el número en vez de creerlo.

## 1. Supuestos, que son la mitad del número

| Supuesto | Valor |
|---|---|
| Perfil | **Una persona** con conocimiento del código y del stack |
| Jornada | 8 h de trabajo efectivo sobre estas tareas |
| Incluye | Escribir el código, sus pruebas, pasar el gate y dejar la especificación actualizada (Art. 9) |
| **No incluye** | Tiempo de espera de decisiones (D-1, D-3), revisión por terceros, ni interrupciones |
| **No incluye** | Aprendizaje de tecnologías nuevas para quien lo implemente |

**La distinción que más cambia la lectura:** son **horas de esfuerzo**, no días de calendario. Si el
trabajo es a tiempo parcial —que es lo habitual en un proyecto de un solo mantenedor— el calendario
se estira proporcionalmente.

## 2. Las funcionalidades, por épica

**11 épicas, 35 ítems del backlog que se ejecutan.**

### Deuda: lo que falta para poder llamarla 1.0.0

| Épica | Qué se implementa | Ítems |
|---|---|---|
| **EP-1** · Resolución reproducible y runtime | Versionar el lockfile · piso de seguridad de Pillow · `pip` ≥ 26.2 · runtime a Python 3.13 en 5 sitios · techos en 8 rangos · gate de resolución mínima · matriz 3.13+3.14 · auditar las 6 deps de macOS y Windows | 8 |
| **EP-2** · Gate de ocho dimensiones | Umbral de cobertura por criticidad · `ruff format` + reformateo de 19 archivos · markers de test · gate de duplicación y complejidad · lote de 9 ítems P3 · bajar complejidad de 2 funciones | 6 |
| **EP-3** · Fronteras y concurrencia | 4 contratos de importación · test que reproduce la carrera de apagado · sincronizar `_loop`/`_sup` · contrato de hilos documentado · `lat check` en el gate · backlinks en 3 puntos | 6 |
| **EP-4** · Añadir una fuente en 3 puntos | Registro declarativo `SourceSpec` · extraer el cableado a `wiring.py` | 2 |
| **EP-5** · Correlación de punta a punta | Identificador que sobrevive a la deduplicación y llega a la presentación | 1 |
| **EP-6** · La alerta en Wayland | **Declarar** el alcance de la garantía · **spike** · implementación con caída a Tk | 2 |
| **EP-7** · Empaquetado verificable | Validar recursos antes de empaquetar · ejecutar el binario antes de publicar · base de build fijada | 3 |
| **EP-9** · Entorno de contribución | Devcontainer con Tk y display virtual · guía de contribución | 1 |

### Capacidad nueva pedida

| Épica | Qué se implementa | Ítems |
|---|---|---|
| **EP-8** · Configurar sin editar un archivo | Escritor que preserva los 46 comentarios, atómico, con respaldo y detección de edición externa · panel Tk generado desde el esquema, con los **39 campos** de las 10 secciones · integración en la bandeja | 2 |
| **EP-10** · El usuario decide qué red manda | Prioridad en la especificación de fuente · el deduplicador conserva el dato de la red más prioritaria · lista ordenable en el panel | 1 |
| **EP-11** · El agente deja de olvidar | Histórico SQLite de todo evento evaluado con su veredicto y motivo · migración de esquema · retención y poda · consulta y listado · cliente de teselas con caché · **mapa de OpenStreetMap** con símbolo por magnitud | 3 |

**Fuera del corte, especificados:** panel en la TUI (B-37) y recarga en caliente (B-38).
**Condicionales, sin fase:** 6 ítems con disparador propio (B-29 a B-33, B-39).

## 3. La estimación

Construida **de abajo arriba**, tarea por tarea, con rango bajo–alto.

| Fase | Tareas | Bajo (h) | Alto (h) |
|---|---|---|---|
| F0 · Base verificable | 10 | 12 | 27 |
| F1 · Runtime y contribución | 4 | 10 | 24 |
| F2 · Suministro y gate | 6 | 8 | 18 |
| F3 · Estructura interna | 9 | 28 | 63 |
| **F4 · La promesa (Wayland)** | 5 | **33** | **108** |
| F5 · Configuración y prioridad | 6 | 27 | 66 |
| F6 · Histórico | 3 | 12 | 29 |
| F7 · Listado y mapa | 5 | 30 | 75 |
| F8 · Corte de la v1.0.0 | 1 | 2 | 5 |
| **Total** | **49** | **162** | **415** |

| | |
|---|---|
| **Jornadas de 8 h** | **20 – 52** |
| **Semanas a tiempo completo** (5 d/sem) | **4 – 10,5** |
| A media jornada | 8 – 21 semanas |
| A un día por semana | 20 – 52 semanas |

### Las cinco tareas que dominan el total

Entre ellas suman **58 h en el escenario bajo y 160 h en el alto**: el 36 % y el 39 % del total.

| Tarea | Bajo | Alto | Por qué es grande |
|---|---|---|---|
| **T-132** Implementar Wayland | 16 | 60 | Servicio D-Bus, extensión de shell, caída a Tk. **El alcance real solo se conoce tras el spike** |
| **T-148** Mapa en lienzo Tk | 12 | 30 | Composición de teselas, proyección, escalado por magnitud, interacción |
| **T-136** Panel desde el esquema | 12 | 30 | 39 campos, validación en vivo, reglas entre campos, secciones plegables |
| **T-131** Spike de Wayland | 8 | 24 | **Es investigación**: su duración no se estima, se acota |
| **T-121** Registro de fuentes | 6 | 14 | Toca el normalizador, las 4 fábricas y el supervisor |

## 4. Escenarios

El número cambia mucho según dos decisiones que aún no están tomadas.

| Escenario | Horas | Jornadas | Cuándo aplica |
|---|---|---|---|
| **Completo** | 162 – 415 | 20 – 52 | D-1 confirma Wayland como `[MUST]` y el spike es favorable |
| **Sin implementación de Wayland** | 146 – 355 | 18 – 44 | El spike concluye que no es viable, **o** D-1 lo degrada a `[SHOULD]` |
| **Sin Wayland y sin mapa** | 125 – 302 | 16 – 38 | Además se recorta el mapa, dejando el listado del histórico |

**El escenario intermedio no es un fracaso.** Si el spike dice que no, T-130 —declarar dónde la
alerta está garantizada y dónde no— sigue siendo obligatoria y **cierra la brecha honestamente**: el
producto deja de prometer lo que no cumple. Eso son 3–8 h, no 16–60.

**El tercer escenario es el recorte natural si hay que publicar.** El listado ya entrega el valor
completo del histórico —responder *"¿por qué no me avisó?"*— sin depender de red, de un tercero ni
del empaquetado de Pillow.

## 5. Por qué el rango es tan ancho

Un factor de **2,5×** entre el extremo bajo y el alto. No es imprecisión: es la forma honesta de
representar lo que no se sabe.

| Fuente de incertidumbre | Efecto |
|---|---|
| **El spike de Wayland es investigación** | Puede terminar en un día o en tres, y su resultado determina si T-132 existe |
| **Trabajo de interfaz sobre Tkinter** | El panel y el mapa son las dos piezas más difíciles de estimar: el 80 % visible se hace rápido y el 20 % de pulido cuesta tanto como el resto |
| **Refactor sobre código que funciona** | F3 toca el módulo más central. Las 344 pruebas son la red, pero también lo que hay que mantener verde |
| **Volumen real del histórico** | Hallazgo V-09: la estimación de filas no está medida, y puede obligar a revisar la retención |
| **Una dependencia sin wheel para 3.13/3.14** | Se detecta pronto (al re-bloquear en T-111), pero si aparece, cambia F1 |

## 6. Discrepancia con las estimaciones del backlog

**Conviene anotarla en lugar de elegir una en silencio.**

| Fase | Backlog / plan | Esta estimación |
|---|---|---|
| F0 (Ola 1) | ≈ 1 jornada | **12 – 27 h** = 1,5 – 3,5 jornadas |
| F1 (Ola 2) | ≈ 1 jornada | **10 – 24 h** = 1,3 – 3 jornadas |
| F2 (Ola 3) | ≈ media jornada | **8 – 18 h** = 1 – 2,3 jornadas |
| F3 (Ola 4) | ≈ 2-3 jornadas | **28 – 63 h** = 3,5 – 8 jornadas |

**Las cifras del backlog son optimistas por un factor de 2 a 3.** La causa es identificable: la
escala de esfuerzo del backlog (`S ≤ 1 h`) mide **el cambio**, no **la tarea completa**. Versionar
`uv.lock` es un `git add` de un minuto; dejarlo con la caché de CI corregida, verificado en un clon
limpio y con el gate en verde es media jornada.

**Cuál usar:** la del backlog para *priorizar* —compara ítems entre sí, y para eso el sesgo es
constante y no importa—; la de aquí para *planificar calendario*.

## 7. Lo que esta estimación no cubre

| No incluido | Por qué |
|---|---|
| Espera de **D-1** y **D-3** | Son decisiones humanas. D-3 bloquea 6 tareas; D-1 bloquea la fase de mayor riesgo |
| Revisión de código por terceros | Con colaboradores (EP-9) aparece, y no está contada |
| Corrección de defectos encontrados al implementar | Lo habitual es un 10–20 % adicional |
| El trabajo de V-01 | Revisar las 177 apariciones de "v2" en 49 archivos: **estimo 2–4 h**, y no es parte de las 49 tareas |
| Medir el volumen real del histórico (V-09) | Ocurre después del primer uso real, no durante la implementación |

## 8. Recomendación de secuencia

**Empezar por F0 hoy** — 12 a 27 h que no dependen de ninguna decisión pendiente y dejan el proyecto
en condiciones de que todo lo demás sea verificable. La primera tanda supervisada son T-101 a T-105.

**Resolver D-3 esta semana.** Es trámite —el argumento técnico está cerrado y medido— y desbloquea
seis tareas repartidas en tres fases. Es la decisión con mejor relación entre esfuerzo de tomarla y
trabajo que libera.

**Poner D-1 en marcha en paralelo**, sin prisa por cerrarla: T-130 permite acotar la promesa mientras
tanto, así que el producto deja de prometer de más aunque la decisión tarde.

**Si el calendario aprieta**, el orden de recorte es: el mapa (T-147 a T-149, 21–53 h), después la
implementación de Wayland si el spike no es concluyente (16–60 h). **No se recorta F0 a F3**: son la
diferencia entre una 1.0.0 y una 0.7.0 con más funciones.
