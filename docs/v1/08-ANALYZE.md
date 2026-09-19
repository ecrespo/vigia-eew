# Analyze — Vigía-eew v1.0 · 2026-09-06

> Artefacto 08 del kit v1.0 · **Solo lectura**: este documento no corrige nada, reporta.
> Validación cruzada de los **23 archivos** del kit **antes** de escribir una línea de código.
> Alcance: 10 documentos (README + artefactos 00 a 08) y 12 Historias de Usuario con su índice.
>
> **Revisión 2** tras incorporar la prioridad de redes (B-40) y el histórico con mapa (B-41..B-43).

## 1. Comprobaciones ejecutadas

Todas automatizadas sobre el contenido real, no revisadas a ojo.

| Comprobación | Método | Resultado |
|---|---|---|
| Identificadores de requisito únicos | Extracción y comparación contra el PRD base | **41 nuevos, 0 colisiones** con los 56 del PRD base |
| Requisitos fantasma | Todo `REQ-*` citado ¿está definido en algún PRD? | **0 fantasmas** |
| Cobertura requisito → tarea | Todo REQ nuevo ¿aparece en alguna tarea? | **0 sin tarea** |
| Criterios de aceptación únicos | Extracción de todos los escenarios Gherkin | **86 criterios, 0 duplicados** |
| Criterios citados sin escenario | Comparación citas ↔ escenarios | **0 huérfanos** |
| Tareas únicas y citadas | Extracción de `T-1NN` | **49 tareas, 0 citadas sin definir** |
| Enlaces relativos | Resolución contra el sistema de archivos | **0 rotos** |
| Rutas `src/` citadas | Existencia en `c3a2c29` | 8 inexistentes, **las 8 intencionales** (§5, V-06) |
| Diagramas Mermaid | Analizador de Mermaid 11 sobre cada bloque | **4 diagramas, 0 con error** |
| Cifras clave | Medición directa sobre el repositorio | 6 verificadas, **1 discrepancia** (§3, V-02) |

### 1.1 Cifras verificadas contra el repositorio, no citadas de memoria

| Cifra | Afirmada en | Medida | ¿Coincide? |
|---|---|---|---|
| 344 pruebas | 06, HU-101 | 344 funciones `test_*` | ✅ |
| 35 archivos de prueba | Glosario heredado | 35 `test_*.py` | ✅ |
| **19 archivos sin formatear** | 02, HU-102, T-105 | `ruff format --check` → *19 files would be reformatted* | ✅ **ejecutado en vivo** |
| **3 pruebas de interfaz real excluidas** | 02, HU-109, T-113 | 3 funciones con el gate, todas en `test_alert_window.py` | ✅ |
| 46 líneas de comentarios en la plantilla | 01, 02, 05, HU-108 | 46 líneas de comentario en `config.toml.example` | ✅ |
| 10 secciones de configuración | 01, 05, HU-108 | 10 modelos hoja bajo el modelo raíz | ✅ |
| **51 campos de configuración** | **Backlog §4** | **39 campos hoja** | ❌ **V-02** |

### 1.2 Reparto de los 41 requisitos nuevos

| Área | Cantidad | Origen |
|---|---|---|
| DEP | 8 | Dependencias y runtime |
| GUI | 8 | Panel de configuración y lista de redes |
| HIS | 6 | **Histórico de eventos** |
| MAP | 5 | **Vista geográfica** |
| CFG | 4 | Escritura de configuración |
| DEV | 4 | Entorno de contribución |
| OBS | 3 | Gate de calidad |
| ING, OPS, PIP | 3 | Prioridad de fuentes, binario fijado, resolución por prioridad |

---

## 2. Cobertura

### Requisito → tarea → criterio

| Comprobación | Resultado |
|---|---|
| Requisitos en alcance | 52 (11 heredados + 41 nuevos) |
| Con al menos una tarea | **50 de 52** |
| Sin tarea, **declarados diferidos** | 2 — REQ-GUI-006 y REQ-GUI-007 |
| Con al menos un criterio de aceptación | 50 de 52 (los mismos 2 quedan fuera) |
| Tareas sin requisito | **2, justificadas** — T-110 (documentación que habilita dos fases) y T-138 (corte del release) |

**Los dos `[SHOULD]` sin tarea no son un hueco: son una decisión escrita.** REQ-GUI-006 (panel en
terminal) y REQ-GUI-007 (recarga en caliente) corresponden a B-37 y B-38, ambos P3, declarados fuera
del corte en [01-FUNCIONALIDADES §EP-8](01-FUNCIONALIDADES.md) y en
[HU-108](HU/HU-108-panel-de-configuracion.md).

### Ítem del backlog → épica

Los 43 ítems aparecen **exactamente una vez**: 37 en una épica, 6 en la lista de condicionales. Suma
verificada en [01-FUNCIONALIDADES §4](01-FUNCIONALIDADES.md). De los 37, **35 se ejecutan** en la
v1.0 (B-37 y B-38 están en su épica pero fuera del corte).

### Fase → tarea

| Fase | Ítems | Tareas |
|---|---|---|
| F0 · Base verificable | 9 | 10 (T-101..T-110) |
| F1 · Runtime y contribución | 3 | 4 (T-111..T-114) |
| F2 · Suministro y gate | 6 | 6 (T-115..T-120) |
| F3 · Estructura interna | 8 | 9 (T-121..T-129) |
| F4 · La promesa | 4 | 5 (T-130..T-134) |
| F5 · Configuración y prioridad | 2 | 6 (T-135..T-137, T-139..T-141) |
| F6 · Histórico | 1 | 3 (T-142..T-144) |
| F7 · Listado y mapa | 2 | 5 (T-145..T-149) |
| F8 · Corte | — | 1 (T-138) |
| **Total** | **35** | **49** ✅ |

---

## 3. Hallazgos

Diez. **Ninguno crítico. Dos requieren decisión humana**; tres son riesgos aceptados que se declaran
en vez de cerrarse.

| ID | Severidad | Qué | Estado |
|---|---|---|---|
| **V-01** | 🟡 Media | La etiqueta "v2" en 49 archivos ya generados | **Abierto** — fuera del alcance de esta tarea |
| **V-02** | 🟡 Media | "51 campos" en el backlog frente a 39 medidos | **Abierto** — documentado, no corregido en el origen |
| **V-03** | 🔴 Alta | **D-1 sin resolver** bloquea F4 y el criterio de corte | **Abierto** — requiere decisión |
| **V-04** | 🟢 Baja | **D-3 sin resolver** bloquea T-111, del que dependen 6 tareas | **Abierto** — requiere decisión |
| **V-05** | 🟢 Baja | B-28 no estaba en ninguna ola del backlog | **Resuelto** por este kit |
| **V-06** | ⚪ Informativo | 8 rutas `src/` citadas no existen | **Intencional**, marcadas |
| **V-07** | 🟡 Media | E-05 revierte una decisión que el backlog había descartado | **Resuelto** — tramitado como enmienda, no en silencio |
| **V-08** | 🟡 Media | El mapa expone al proveedor de teselas la zona que mira el usuario | **Aceptado y declarado** — no se elimina |
| **V-09** | 🟡 Media | El volumen del histórico es **una estimación, no una medición** | **Abierto** — mitigado por retención configurable |
| **V-10** | 🟢 Baja | El mapa introduce un riesgo de empaquetado con precedente | **Resuelto** por el orden de fases |

### V-01 · La etiqueta "v2" en la documentación ya generada 🟡

Los documentos de etapas anteriores llaman "v2" a lo que este kit estableció que es la **v1.0**.
Medido de nuevo, excluyendo `docs/v1/`: **177 apariciones en 49 archivos**, concentradas en
`docs/sdd/specs/01-PRD.md` (21), `docs/reverse-sdd/04-MATRIZ-PRUEBAS.md` (19) y
`docs/reverse-sdd/05-PLAN-RECONSTRUCCION.md` (9).

**No es cosmético:** "v2" implica que existió una v1 estable, y quien lea `docs/sdd/` sin este kit
concluirá que Wayland y el gate son mejoras de segunda generación en lugar de **lo que falta para la
primera**.

**Por qué no se corrige aquí:** toca documentos de otras tareas, y no todas las apariciones son el
mismo error — algunas de `docs/DATA-MODEL.md` pueden referirse a versiones de API externas.
**Requiere revisión caso por caso, no un reemplazo global.**

### V-02 · "51 campos" frente a 39 medidos 🟡

El backlog §4 afirma *"51 campos repartidos en 10 secciones"*. El recuento programático sobre
`src/vigia_eew/config.py` da **39 campos hoja** en 10 secciones. La cifra dimensiona el esfuerzo de
B-36 y **es un criterio verificable** (REQ-GUI-001). Este kit usa 39 en los cinco documentos donde
aparece, con la discrepancia anotada; el backlog no se edita porque pertenece a otra tarea.

### V-03 · D-1 sin resolver bloquea la fase de mayor riesgo 🔴

D-1 —*¿la alerta bajo Wayland bloquea el release?*— determina si REQ-ALE-004 es `[MUST]` o
`[SHOULD]`, y con ello la condición 7 del criterio de corte. **No se puede decidir por defecto**:
`[MUST]` compromete el release a un spike de resultado desconocido; `[SHOULD]` publica una 1.0.0 que
no cumple su promesa central en el escritorio Linux más común.

Es el mismo hallazgo que las tres etapas anteriores señalaron y el A-01 del Analyze previo. **Sigue
abierto.**

**Mitigación aplicada:** T-130 (declarar el alcance) está separada de T-131/T-132 (cumplirlo), de
modo que declarar se puede hacer decida lo que decida D-1 — e incluso si el spike concluye que no es
viable.

### V-04 · D-3 bloquea la tarea de la que dependen otras seis 🟢

T-111 está bloqueada por D-3 y la enmienda E-01. De ella dependen T-112, T-113, T-115, T-116, T-117
y T-134 — seis tareas en tres fases. **Severidad baja porque el argumento técnico está cerrado y
medido**; lo que falta es el trámite de enmienda. **Es la decisión con mejor relación entre esfuerzo
de tomarla y trabajo que desbloquea.**

### V-05 · B-28 no estaba asignado a ninguna ola — **resuelto** 🟢

Las olas del backlog cubren 30 de los 43 ítems; de los restantes, todos son condicionales salvo
B-28, que es P2. Este plan lo coloca en **F3 como T-129**, tras T-128 del que depende. Es **el único
ítem cuya ubicación no viene dada por el backlog** sino decidida aquí.

### V-06 · Ocho rutas `src/` que no existen — intencional ⚪

`wiring.py`, `ingest/registry.py`, `config_writer.py`, `notify/config_panel.py`, `history.py`,
`notify/history_view.py`, `notify/history_map.py` y `tiles.py`. **Son archivos propuestos**, y las
ocho apariciones están marcadas `*(nuevo)*` para que un verificador estricto de rutas no las señale
como error.

### V-07 · El histórico revierte una decisión previamente descartada 🟡

**Qué.** El backlog §7 listaba "Base de datos" entre lo **descartado**, con este argumento: *"el
estado son unos KB en memoria consultados por pertenencia"*. B-41 la introduce.

**Por qué no es una contradicción.** El argumento original es **literalmente cierto del estado
operativo y literalmente falso del histórico** — dos problemas de persistencia distintos que hasta
ahora no hacía falta separar. La enmienda [E-05](00-ENMIENDAS-CONSTITUCION.md) **acota, no deroga**:
el estado operativo sigue en JSON, sin excepción.

**Por qué está aquí de todos modos.** Revertir una decisión documentada es exactamente el tipo de
movimiento que debe quedar registrado: **el riesgo no es esta decisión, es el precedente**. Si
"estaba descartado pero ahora lo necesitamos" se vuelve rutina, la lista de descartados deja de
significar nada. Por eso E-05 enumera explícitamente **lo que no autoriza**: mover la configuración,
mover el estado operativo, ni adoptar un motor cliente-servidor.

### V-08 · El mapa expone la zona que mira el usuario 🟡

**Qué.** Pedir teselas revela al proveedor, aproximadamente, qué zona está mirando el usuario. Hasta
la v1.0, el agente solo hablaba con fuentes sísmicas y —una vez— con un servicio de geolocalización.

**Estado: aceptado y declarado, no eliminado.** La caché lo reduce y el carácter bajo demanda lo
acota, pero no lo suprime. Está en REQ-MAP-001, en la enmienda
[E-06](00-ENMIENDAS-CONSTITUCION.md) y en el modelo de datos — **tres sitios, para que no se pierda**.

**Por qué se registra como hallazgo y no solo como diseño:** es una propiedad del producto que
cambia con esta versión, y quien la audite dentro de un año debe encontrarla escrita en lugar de
deducirla del código. **No es telemetría** —no se envía nada *sobre* el usuario— pero tampoco es
nada.

**Contrapartida positiva de la misma decisión:** E-06 **añade** la regla que no existía —los destinos
de red se declaran, y uno nuevo exige enmienda—, de modo que la próxima funcionalidad que quiera
"consultar un servicio rápido" tenga que pasar por ahí.

### V-09 · El volumen del histórico es una estimación 🟡

**Qué.** El modelo de datos estima **decenas de miles de filas al año**, del orden de decenas de MB.
Esa cifra **no está medida**: depende de la sismicidad global y de qué publica cada red, y el
histórico guarda también los descartes, que en un flujo global son bastantes más que las alertas.

**Por qué importa.** Determina si la retención por defecto es razonable o deja crecer un archivo en
el equipo del usuario.

**Mitigación ya en el diseño:** la retención es **configurable desde el principio** (REQ-HIS-004), y
es precisamente el parámetro que absorbe el error de la estimación. **La acción pendiente es medir
en el primer uso real y ajustar el valor por defecto con el dato**, no con la estimación — anotado
en T-144.

### V-10 · Riesgo de empaquetado del mapa, con precedente 🟢

**Qué.** El mapa usa el puente entre Pillow y Tk. **Ese es exactamente el tipo de recurso que falta
en un binario y solo se descubre al ejecutarlo** — el proyecto ya rompió una release así
(`bdc2a9d`), y otras dos por recursos de empaquetado (`7b1c71c`, `c38d9f6`).

**Resuelto por el orden de fases**, no por una comprobación nueva: **F7 depende de F4**, donde vive
el smoke del binario (T-133). Para cuando el mapa entre en el empaquetado, ya existe la comprobación
que detecta este fallo.

**Efecto lateral que conviene registrar:** el mapa convierte a Pillow en dependencia de primera clase
**independientemente de lo que decida D-2** sobre `pystray`. Hasta ahora Pillow estaba en el árbol
solo porque la bandeja lo exige. Eso **refuerza B-02** —el piso de seguridad de Pillow— en lugar de
debilitarlo.

---

## 4. Resultado por categoría del checklist

### Cobertura — ✅ con salvedad declarada
50 de 52 requisitos con tarea y criterio. Los 2 restantes son `SHOULD` **declarados diferidos**.

### Constitución — ✅
**Seis desviaciones, las seis tramitadas como enmiendas** en
[00-ENMIENDAS-CONSTITUCION.md](00-ENMIENDAS-CONSTITUCION.md). Sin ese artefacto, B-04, B-23, B-34,
B-35, B-36 y B-41 a B-43 serían violaciones.

**Una excepción solicitada**: `tzdata` exento de la regla de techos (E-04), con justificación
escrita.

**Observación sobre la dirección de las enmiendas.** Cinco amplían lo que el proyecto puede hacer y
una lo estrecha (E-06). Esa proporción es la esperada al pasar de 0.6.0 a 1.0.0, pero **una
constitución que solo se relaja deja de restringir**. Que E-06 exista —añadiendo una regla en el
mismo movimiento que abre una puerta— es lo que evita esa deriva.

### Ambigüedad — ⚠️ un hallazgo
**V-03.** REQ-ALE-004 lleva un `[MUST]` condicional a una decisión pendiente. Los otros 51
requisitos nombran un resultado observable; comprobado uno a uno: ninguno dice "correctamente",
"adecuadamente" ni "de forma óptima".

### Consistencia terminológica — ✅ con un hallazgo heredado
El glosario canónico se respeta: **pruebas** (344), **criterios de aceptación** (86 en este kit),
**requisitos** (52 en alcance), **módulos** (40). **V-01** es el hallazgo abierto.

### Caminos no felices — ✅
Cada capacidad nueva especifica su degradación:

| Capacidad | Camino no feliz especificado |
|---|---|
| Escritura de configuración | Validación falla · huella distinta · sin respaldo → **aborta, no escribe** |
| Wayland | Servicio ausente → cae a Tk · entorno no reconocido → no confirmado, arranca igual |
| Registro de fuentes | Fuente desconocida → falla al arrancar nombrándola, no en silencio |
| Prioridad de redes | Sin prioridad declarada → se ordena al final, **no se excluye** |
| **Histórico** | **No se puede escribir → la alerta se presenta igual** y el fallo se anota |
| **Mapa** | Sin red ni caché → mapa no disponible, **el listado sigue funcionando** |
| Devcontainer | *(sin camino no feliz — es entorno de desarrollo)* |

Las dos filas nuevas son las que protegen el Art. 1: **ni el histórico ni el mapa pueden impedir una
alerta.**

### Datos — ✅
Sin datos financieros. Todos los instantes del histórico en ISO-8601 UTC, donde el orden
lexicográfico es el cronológico. **Ninguna migración del estado operativo necesaria**: el campo de
correlación es opcional en la lectura. El histórico sí tiene migración de esquema, versionada y
probada (REQ-HIS-003).

### Ejecutabilidad de las tareas — ✅
Las 49 tienen "Done" verificable. Dependencias acíclicas, verificado recorriendo el grafo. **Dos
tareas marcadas `[!]` a propósito**: T-111 (bloqueada por D-3) y T-132 (bloqueada por D-1 y por el
veredicto del spike).

### Tareas huérfanas — ✅
Dos sin requisito, **ambas justificadas**: T-110 es documentación que habilita dos fases, T-138 es el
corte del release.

---

## 5. Lo que este Analyze NO puede cerrar

| Ítem | Por qué |
|---|---|
| **D-1** (Wayland bloquea el release) | Decisión de producto. Cambia el criterio de corte |
| **D-3** (enmienda a Python 3.13) | Trámite; el argumento técnico ya está cerrado |
| **D-2** (qué hacer con `pystray`) | Informa B-02, B-23 y B-36. **El mapa cambia su cálculo**: Pillow se queda pase lo que pase |
| **D-4** (backlog como fuente única) | Gobernanza |
| El volumen real del histórico | **V-09**: solo se sabe midiendo en uso real |
| Cobertura real de pruebas | El entorno de auditoría solo tenía Python 3.10. **Sin cifra inventada** |
| El veredicto del spike de Wayland | Es una incógnita técnica; T-131 existe para resolverla |

---

## 6. Veredicto

**El kit es internamente consistente y ejecutable.** 0 requisitos fantasma, 0 sin tarea, 0 criterios
duplicados de los 86, 0 enlaces rotos, 0 diagramas con error, y seis cifras clave verificadas contra
el repositorio en vez de citadas.

**Se puede empezar a implementar por la Fase 0 hoy**, sin esperar ninguna decisión: sus diez tareas
son independientes de D-1 y de D-3, ninguna toca lógica de producto, y dejan el proyecto en
condiciones de que todo lo demás sea verificable.

**Lo que cambió con las dos capacidades nuevas**, y conviene tener presente al planificar:

1. **El corte de la v1.0 pasó de 8 condiciones a 10.** Las dos nuevas son de otra naturaleza: no
   cierran deuda, añaden capacidad. **Si hubiera que recortar para publicar, es por ahí.** El mapa
   (F7) es el candidato natural — el listado ya entrega el valor del histórico sin él.
2. **Las enmiendas pasaron de cuatro a seis**, y una de ellas revierte una decisión que estaba
   documentada como descartada (V-07). Está tramitada, no hecha en silencio, y enumera lo que **no**
   autoriza.
3. **El producto adquiere una propiedad nueva que no tenía** (V-08): habla con un tercero que no es
   una fuente sísmica. Acotado, declarado, y compensado con una regla nueva que antes no existía.

**Las dos decisiones a tomar en paralelo**, en orden de urgencia: **D-3**, porque bloquea seis tareas
y es trámite; y **D-1**, porque define qué significa 1.0.0.

**Lo que este kit no arregla:** la etiqueta "v2" sigue en 49 archivos (V-01), y el backlog sigue
diciendo 51 campos donde hay 39 (V-02). Documentados, no corregidos en su origen — porque corregirlos
pertenece a otra tarea.
