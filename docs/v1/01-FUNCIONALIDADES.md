# Funcionalidades de la v1.0 — mapa de alcance

> Artefacto 01 del kit v1.0 · Insumo: [`docs/BACKLOG-PRIORIZADO.md`](../BACKLOG-PRIORIZADO.md) rev. 2
>
> Convierte los 43 ítems del backlog en **11 épicas**, cada una con su Historia de Usuario y sus
> requisitos. Los 43 aparecen exactamente una vez: 37 dentro de una épica, 6 en la lista de
> condicionales del final.

## 1. Qué es la v1.0

**La v0.6.0 funciona.** Los 42 requisitos funcionales originales están implementados y verificados
por las 17 Historias de Usuario reconstruidas, y ningún ítem de este documento corrige un requisito
incumplido. Lo que falta para llamarla 1.0.0 es de otro tipo:

| Lo que falta | Por qué impide llamarla 1.0.0 |
|---|---|
| **Una promesa sin acotar** | El producto promete una alerta imposible de ignorar. Bajo Wayland —el escritorio Linux más común— no la cumple, y tampoco declara que no la cumple |
| **Capacidades documentadas que nunca se construyeron** | Diez, algunas especificadas desde la v0.1.0. Un 1.0.0 no debería arrastrar ADRs sin código |
| **Un gate que no cubre lo que dice cubrir** | La constitución exige ocho dimensiones; el gate mide cinco |
| **Reproducibilidad que no llega al usuario** | El lockfile no está versionado: lo que protege al desarrollador no protege a quien instala |
| **Capacidad nueva pedida** | Configuración gráfica, prioridad de redes e histórico consultable — decisión del mantenedor de que la 1.0 las incluya |

Las cuatro primeras filas son deuda: cosas que un 1.0.0 no debería arrastrar. **La quinta es
distinta** — son capacidades que nadie prometió y que entran porque el mantenedor decidió que un
producto sin ellas no está completo. Conviene no mezclarlas al discutir el alcance: si hubiera que
recortar, se recorta por ahí.

**No es deuda funcional**: es la diferencia entre un producto que funciona en la máquina de su autor
y uno que se puede publicar como estable.

## 2. Las nueve épicas

| Épica | Nombre | Ítems | HU | Prio | Esfuerzo |
|---|---|---|---|---|---|
| **EP-1** | Resolución reproducible y runtime con soporte | 8 | [HU-101](HU/HU-101-runtime-y-dependencias-reproducibles.md) | **P0** | ≈ 1 jornada |
| **EP-2** | El gate mide las ocho dimensiones | 6 | [HU-102](HU/HU-102-gate-de-calidad-completo.md) | P1 | ≈ 1 jornada |
| **EP-3** | Fronteras y concurrencia demostradas | 6 | [HU-103](HU/HU-103-fronteras-y-concurrencia.md) | P1 | ≈ 1 jornada |
| **EP-4** | Añadir una fuente cuesta tres puntos | 2 | [HU-104](HU/HU-104-registro-declarativo-de-fuentes.md) | P1 | ≈ 1 jornada |
| **EP-5** | Un sismo se sigue de punta a punta | 1 | [HU-105](HU/HU-105-correlacion-punta-a-punta.md) | P1 | M |
| **EP-6** | La alerta llega también en Wayland | 2 | [HU-106](HU/HU-106-alerta-bajo-wayland.md) | **P1** | L, sin estimar |
| **EP-7** | El empaquetado se verifica solo | 3 | [HU-107](HU/HU-107-empaquetado-verificable.md) | P1 | ≈ 1 jornada |
| **EP-8** | Configurar sin editar un archivo | 4 | [HU-108](HU/HU-108-panel-de-configuracion.md) | P2 | L |
| **EP-9** | Un colaborador aporta el mismo día | 1 | [HU-109](HU/HU-109-entorno-de-contribucion.md) | P1 | M |
| **EP-10** | El usuario decide qué red manda | 1 | [HU-110](HU/HU-110-prioridad-de-redes.md) | P2 | L |
| **EP-11** | El agente deja de olvidar | 3 | [HU-111](HU/HU-111-historico-de-sismos.md) · [HU-112](HU/HU-112-mapa-del-historico.md) | P2 | L |

---

### EP-1 · Resolución reproducible y runtime con soporte

**Ítems:** B-01, B-02, B-03, B-04, B-05, B-13, B-16, B-17 · **Requisitos:** REQ-DEP-001..007

Que una instalación limpia resuelva **exactamente** las versiones que el desarrollador probó, sobre
un intérprete que todavía recibe correcciones.

Hoy no ocurre ninguna de las dos cosas: `uv.lock` está en `.gitignore`, el piso del proyecto es
Python 3.11 —en fase security-only— y `Pillow>=10.0` admite versiones con **34 avisos conocidos**
aunque el lockfile resuelva una limpia. Es la única épica cuya cadena es **estrictamente
secuencial**: `requires-python` determina qué versiones son resolubles, así que fijar techos antes
de subir el runtime obliga a rehacerlos.

**Se cierra cuando** `uv sync --frozen` reproduce el entorno en una máquina limpia, la suite pasa en
3.13 y 3.14, y un gate impide que un rango vuelva a admitir una versión con avisos.

---

### EP-2 · El gate mide las ocho dimensiones

**Ítems:** B-09, B-10, B-11, B-12, B-25, B-26 · **Requisitos:** REQ-OBS-003, REQ-OBS-004, REQ-OBS-006, REQ-OBS-007

El Art. 8 de la constitución dice que nada entra sin gate verde y que el gate mide ocho dimensiones.
Mide cinco: **cobertura, formato, duplicación y complejidad no fallan nunca**, porque no están
conectadas.

La diferencia entre medir y exigir es la que separa un informe de un control. Hoy la cobertura se
puede calcular, pero nada obliga a que suba; el formato se puede comprobar, pero 19 archivos
divergen sin consecuencia.

**Se cierra cuando** el CI falla ante cobertura por debajo del umbral de cada módulo (85 % en
pipeline y estado, 70 % en ingesta, 40 % en adaptadores), ante un archivo sin formatear, ante
duplicación nueva y ante una función que supere el umbral de complejidad.

---

### EP-3 · Fronteras y concurrencia demostradas

**Ítems:** B-06, B-07, B-08, B-24, B-27, B-28 · **Requisitos:** REQ-OPS-002, REQ-OPS-003, REQ-OBS-005, REQ-OBS-008

Dos cosas que hoy dependen de que el proyecto tenga un solo autor: **que nadie importe lo que no
debe**, y **que el apagado ocurra en el orden correcto**.

La segunda es el hallazgo de mayor severidad de toda la auditoría de arquitectura. `Application`
asigna `_loop` y `_sup` desde el hilo de asyncio y los lee desde el hilo de Tk sin sincronización
`[VERIFY: src/vigia_eew/app.py:420,431,443]`. Si la parada llega antes de que el hilo trabajador
haya publicado ambos, la cancelación se omite en silencio. **El propio proyecto ya tiene el patrón
correcto a mano** — `agent_state.py:18` usa un `threading.Lock` para exactamente esto.

**Se cierra cuando** existe un test que falla contra el código actual y pasa contra el corregido, y
`lint-imports` rechaza una importación que cruce una frontera declarada.

---

### EP-4 · Añadir una fuente cuesta tres puntos

**Ítems:** B-18, B-21 · **Requisitos:** REQ-ING-009

Añadir una quinta fuente sísmica hoy toca **cinco archivos o más**: una escalera `if/elif` por
fuente en el normalizador `[VERIFY: src/vigia_eew/pipeline/normalize.py:55]`, cuatro fábricas en
`Application`, y el cableado del supervisor.

Un registro declarativo `dict[Source, SourceSpec]` lo reduce a **tres puntos**: la entrada del
registro, el ingestor y su prueba. `wiring.py` separado de `Application` es lo que lo hace posible
—y de paso baja el fan-out del módulo de 25 a ≤8, que es el hallazgo P1-1 de la evaluación de
arquitectura.

**Se cierra cuando** añadir una fuente de prueba requiere tocar tres archivos y ninguna escalera por
tipo queda en el pipeline.

---

### EP-5 · Un sismo se sigue de punta a punta

**Ítems:** B-22 · **Requisitos:** REQ-OBS-002

Un mismo sismo llega por EMSC y por GEOFON, se deduplica, se filtra y se presenta. Hoy esas cinco
etapas dejan registros que **no se pueden enlazar**: no hay forma de reconstruir el recorrido con
una sola búsqueda, y cuando una alerta no aparece hay que reconstruir a mano por marca de tiempo.

**Se cierra cuando** una búsqueda por identificador de correlación devuelve las entradas de ingesta,
normalización, filtro, veredicto de deduplicación y presentación — incluidas las de la fuente cuya
llegada se descartó por duplicada.

---

### EP-6 · La alerta llega también en Wayland

**Ítems:** B-19, B-20 · **Requisitos:** REQ-ALE-003, REQ-ALE-004 · **Bloqueada por D-1**

**Es la brecha más importante del proyecto.** El producto promete una alerta imposible de ignorar.
Bajo GNOME/Wayland, la ventana `topmost` de Tkinter no tiene garantía de quedar por encima, y el
ícono de bandeja necesita una extensión que el usuario puede no tener. ADR-010 diseñó la solución
—servicio D-Bus más extensión de shell— **en la v0.1.0**, se profundizó en un commit propio
(`230b0b8`), y **nunca se escribió una línea de código**.

Son dos capacidades distintas y conviene no confundirlas:

| Ítem | Qué es | Esfuerzo |
|---|---|---|
| **B-19** | **Declarar** dónde la alerta está garantizada y dónde no | S |
| **B-20** | **Cumplirla** bajo Wayland: spike de D-Bus + implementación con caída a Tk | L |

B-19 es barato y honesto: acota la promesa a lo que el producto cumple hoy. B-20 la extiende. **Se
pueden hacer por separado y en ese orden**, y esa es la recomendación — declarar primero evita que
el producto siga prometiendo de más mientras dure el spike.

**Bloqueo real:** **D-1** decide si REQ-ALE-004 es `[MUST]` —y entonces la v1.0.0 no se publica sin
Wayland— o `[SHOULD]`, y se publica con la limitación declarada. Es la única decisión del backlog
que cambia el criterio de corte del release.

---

### EP-7 · El empaquetado se verifica solo

**Ítems:** B-14, B-15, B-23 · **Requisitos:** REQ-OPS-007, REQ-OPS-008, REQ-OPS-009

Los recursos que faltan en un binario **hoy se descubren ejecutándolo**, y eso ya rompió **dos
releases consecutivas** (`7b1c71c`, `c38d9f6`). Un tercer riesgo, más silencioso, se añadió sin que
nadie lo decidiera: el binario de Linux hereda la glibc de `ubuntu-latest`, así que **la versión
mínima de sistema que soporta cambia cuando GitHub actualiza sus runners**.

**Se cierra cuando** un recurso deliberadamente inválido hace fallar el build *antes* de invocar al
empaquetador, el binario producido se ejecuta en modo simulación dentro del pipeline, y la imagen
de build declara su base en lugar de heredarla.

---

### EP-8 · Configurar sin editar un archivo

**Ítems:** B-35, B-36, B-37, B-38 · **Requisitos:** REQ-CFG-009..012, REQ-GUI-001..007

Hoy la única vía de configuración es el menú de bandeja *"Editar configuración…"*, que abre
`config.toml` con el editor del sistema `[VERIFY: src/vigia_eew/tray.py:52]`. Para el destinatario
del producto —un usuario no técnico que quiere saber si un sismo le afecta— eso es una barrera.

**La superficie real son 39 campos en 10 secciones**: referencia, filtro, cuatro fuentes, dedup,
severidad, notificación y logging. No es un diálogo de tres casillas.

> **Corrección de dato.** El backlog §4 dice *"51 campos repartidos en 10 secciones"*. El recuento
> sobre `src/vigia_eew/config.py` da **39 campos hoja en 10 secciones**; la cifra 51 no se
> reproduce. Las 10 secciones sí son correctas. Se anota aquí y en
> [08-ANALYZE §V-02](08-ANALYZE.md) en lugar de editar el backlog, que es de otra tarea.

**El obstáculo va primero.** La configuración es de solo lectura **por decisión explícita**: ADR-007
eligió `tomllib`, que no tiene escritor, y anotó *"writing config isn't needed in v1"*. Un panel que
guarda **contradice esa decisión**, así que B-35 —la enmienda— es requisito previo y no negociable.

Cuatro restricciones que el panel tiene que respetar, cada una con su razón:

| Restricción | Por qué | Cómo |
|---|---|---|
| No perder los comentarios | Las **46 líneas de comentarios** de la plantilla son hoy la ayuda en línea del usuario | `tomlkit`, que preserva formato; `tomli-w` no |
| Validar antes de escribir | Art. 3: un panel que deja una config inválida deja el agente sin arrancar | Los modelos pydantic que ya existen, **antes** de tocar el archivo |
| Escritura atómica con respaldo | El mismo criterio que ya rige `state.json` `[VERIFY: src/vigia_eew/state.py:61]` | Temporal + `rename`, y `.bak` de la versión anterior |
| Avisar de que hace falta reiniciar | La config se lee **una sola vez, al arrancar** | El panel lo dice. La recarga en caliente es B-38, aparte |

**Riesgo propio de esta épica:** es el primer componente que **escribe** en un archivo que el
usuario también puede editar a mano. Si alguien lo tiene abierto en su editor mientras el panel
guarda, uno de los dos pierde. Por eso REQ-CFG-011 exige detectar la modificación externa por
*mtime*.

**Alcance de la v1.0:** B-35 y B-36. **B-37** (paridad en la TUI) y **B-38** (recarga en caliente)
quedan especificados en la HU pero **fuera del corte** — son P3 y no bloquean el release.

---

### EP-9 · Un colaborador aporta el mismo día

**Ítems:** B-34 · **Requisitos:** REQ-DEV-001..004

La decisión de abrir el proyecto a colaboradores ya está tomada, y con ella el bus factor 1 pasa de
riesgo aceptado a problema con solución en marcha. Lo que falta es que empezar no cueste una tarde.

El obstáculo concreto es específico de este proyecto: **necesita tkinter**, que no viene en las
imágenes base de Python. La CI ya lo resuelve usando el Python gestionado por `uv`
`[COMMITS: 0e707a1]`; un colaborador chocaría con lo mismo sin ninguna pista.

**Se cierra cuando** abrir el repositorio en un devcontainer deja el entorno instalado, los hooks
activos y las pruebas de GUI real ejecutables — las 3 que hoy están excluidas por defecto.

**Depende de EP-1**: la imagen debe traer la versión de Python que el proyecto exija. Construirla
sobre 3.11 y rehacerla después es trabajo duplicado.

---

### EP-10 · El usuario decide qué red manda

**Ítems:** B-40 · **Requisitos:** REQ-ING-011, REQ-PIP-010, REQ-GUI-008

Hoy las cuatro redes viven en cuatro secciones separadas del archivo, cada una con su `enabled`, y
**no hay jerarquía entre ellas**. Cuando el mismo sismo llega por dos, el deduplicador conserva la
primera que llegó — es decir, gana la de menor latencia, que es un accidente de red y no una
decisión de nadie.

**Qué cambia:** una lista con casillas y orden, y ese orden significa que **prevalecen los datos de
la red mejor posicionada**, aunque haya llegado después.

El caso que lo justifica es concreto y venezolano: un sismo local llega por EMSC con magnitud
estimada automáticamente y por FUNVISIS con magnitud revisada por el servicio nacional. Hoy se
muestra la que llegó antes. Con prioridad, el usuario decide **cuál considera más fiable para su
geografía** — que es precisamente la razón por la que FUNVISIS está en el producto.

**Tres límites deliberados**, cada uno protegiendo algo que ya funciona:

| Límite | Qué protege |
|---|---|
| La prioridad **no decide si se alerta** | Los sismos locales que solo cataloga FUNVISIS. Quién alerta lo sigue decidiendo el filtro |
| La prioridad **no serializa las consultas** | La latencia. Las cuatro fuentes siguen siendo concurrentes e independientes (REQ-ING-010) |
| Una red sin prioridad **se ordena al final**, no se excluye | La compatibilidad: un `config.toml` de la v0.6.0 sigue siendo válido |

**Depende de EP-4.** La prioridad es un campo de la especificación de cada fuente; sin el registro
declarativo habría que añadirla en cuatro sitios y leerla en un quinto.

**Se cierra cuando** reordenar la lista cambia qué magnitud se muestra para un sismo que llegó por
dos redes, y deshabilitar una red desde la lista impide que su tarea se cree.

---

### EP-11 · El agente deja de olvidar

**Ítems:** B-41, B-42, B-43 · **Requisitos:** REQ-HIS-001..006, REQ-MAP-001..005

El agente hoy **recuerda solo lo justo para no repetirse**: qué identificadores ya alertó, podados a
24 horas. Pasado ese plazo no queda rastro de nada. No se puede responder *"¿cuántos sismos me
afectaron este año?"* ni, sobre todo, ***"¿por qué no me avisó de aquel?"***.

**Qué se guarda: todo evento evaluado, alertado o descartado, con el motivo del descarte.** Guardar
solo los alertados haría la tabla más pequeña y dejaría sin respuesta la pregunta que más importa
cuando el producto parece fallar. Con el veredicto registrado, la respuesta es una consulta: fuera
de radio, bajo la magnitud mínima, de otro día, o duplicado de otro que sí alertó.

Encaja con **EP-5**: el identificador de correlación es lo que enlaza las llegadas de un mismo sismo
por redes distintas, y es la clave natural del histórico.

#### El obstáculo: la constitución dice que no hay base de datos

*"Persistencia: JSON atómico en disco. **Sin base de datos**"* es una restricción vigente, y "base de
datos" estaba entre lo descartado con este argumento: *"el estado son unos KB en memoria consultados
por pertenencia"*.

**Ese argumento es cierto del estado operativo y falso del histórico** — son dos problemas distintos
que hasta ahora no hacía falta separar. La enmienda [E-05](00-ENMIENDAS-CONSTITUCION.md) acota la
restricción en lugar de derogarla: **el estado operativo sigue en JSON, sin excepción**.

Lo que hace la enmienda defendible es que **SQLite es biblioteca estándar**: cero dependencias
nuevas, sin servicio que administrar, un archivo junto al que ya existe.

#### El mapa: teselas de OpenStreetMap

**No añade ninguna dependencia.** `httpx` ya está para las fuentes REST, `Pillow` ya está por la
bandeja, y el lienzo es Tk de la biblioteca estándar. Descargar la tesela, decodificarla y pintarla
se hace con lo que el proyecto ya tiene.

> **Efecto lateral que conviene registrar:** el mapa convierte a Pillow en dependencia de primera
> clase **independientemente de lo que decida D-2** sobre `pystray`. Hasta ahora Pillow estaba en el
> árbol solo porque la bandeja lo exige; si la bandeja se retirara, saldría. Con el mapa, no. Eso
> refuerza B-02 (piso de seguridad de Pillow), no lo debilita.

Tres consecuencias nuevas para este producto, todas declaradas en
[E-06](00-ENMIENDAS-CONSTITUCION.md):

| Consecuencia | Cómo se acota |
|---|---|
| El agente pedirá datos a un destino que no es una fuente sísmica | Solo con el mapa abierto, nunca en segundo plano. Caché local |
| La zona que el usuario mira queda expuesta al proveedor de teselas | La caché lo reduce y el carácter bajo demanda lo acota. **No lo elimina** — queda declarado, no escondido |
| Atribución y uso | "© OpenStreetMap contributors" visible, cliente identificado, sin descargas masivas |

**Degradación (Art. 3):** sin red y sin caché, el mapa no está disponible y **el listado sigue
funcionando**. El histórico es la funcionalidad; el mapa es una vista sobre él, y por eso B-42 va
antes que B-43.

**Se cierra cuando** un sismo descartado aparece en el listado con su motivo, y el mapa lo sitúa con
un símbolo cuyo tamaño refleja la magnitud.

---

## 3. Fuera del alcance de la v1.0 — capacidades condicionales

Seis ítems del backlog **no entran**, y no por falta de tiempo: **su disparador no se ha cumplido**.
Subirlos sería malinterpretar sus propios ADR, que los dejaron condicionados a propósito.

| ID | Capacidad | Disparador que la activaría |
|---|---|---|
| B-28 | Backlinks `# @lat:` en los 3 sitios de mayor valor | Ninguno: **entra en la Fase 3**. Es P2 y estaba sin ola asignada en el backlog |
| B-29 | Extracción semántica de `docs/` en Graphify | Disponer de un backend LLM en el entorno |
| B-30 | Unificar los dos pollers FDSN en una base común | **Una quinta fuente FDSN.** Con dos, la regla de tres no se cumple |
| B-31 | Fronteras de país a Natural Earth 1:50m | Que el filtro de país pase a activo por defecto |
| B-32 | Modo de recuperación histórica (`--backfill`) | Un caso de uso real que lo justifique |
| B-33 | Relay central opcional (FastAPI + fan-out WS) | Un despliegue multi-máquina |
| B-39 | Automatizar la actualización de dependencias | Que la cadencia manual trimestral se demuestre insuficiente |

**B-28 es la excepción y merece nota**: no es condicional, es P2 y depende de B-27. En el backlog
quedó sin asignar a ninguna ola —lo he verificado sumando las cinco olas: 30 de 39 ítems—, así que
**este plan lo coloca en la Fase 3**. Es el único ítem cuya ubicación no viene dada por el backlog.

Los otros seis se revisan cuando su disparador ocurra, no antes.

## 4. Trazabilidad de los 39 ítems

Cada ítem del backlog aparece exactamente una vez.

| Épica / destino | Ítems | Total |
|---|---|---|
| EP-1 | B-01, B-02, B-03, B-04, B-05, B-13, B-16, B-17 | 8 |
| EP-2 | B-09, B-10, B-11, B-12, B-25, B-26 | 6 |
| EP-3 | B-06, B-07, B-08, B-24, B-27, B-28 | 6 |
| EP-4 | B-18, B-21 | 2 |
| EP-5 | B-22 | 1 |
| EP-6 | B-19, B-20 | 2 |
| EP-7 | B-14, B-15, B-23 | 3 |
| EP-8 | B-35, B-36, B-37, B-38 | 4 |
| EP-9 | B-34 | 1 |
| EP-10 | B-40 | 1 |
| EP-11 | B-41, B-42, B-43 | 3 |
| Condicionales | B-29, B-30, B-31, B-32, B-33, B-39 | 6 |
| **Total** | | **43** ✓ |

**En alcance de la v1.0: 37 ítems** (los 43 menos los 6 condicionales), de los cuales B-37 y B-38
están dentro de EP-8 pero **fuera del corte del release**. El trabajo que se ejecuta son
**35 ítems**.

**B-31 se reevaluó al añadir el mapa y sigue siendo condicional.** Con teselas de OpenStreetMap las
fronteras vienen dibujadas en la propia tesela, así que el mapa **no** dispara la necesidad de
fronteras vectoriales propias a 1:50m. Su disparador sigue siendo el mismo: que el filtro de país
pase a activo por defecto.
