# PRD delta — Vigía-eew v1.0

> Artefacto 02 del kit v1.0 · Notación: **EARS** · Commit base: `c3a2c29`
> Documento base que este extiende: [`docs/sdd/specs/01-PRD.md`](../sdd/specs/01-PRD.md) (56 requisitos)

## 1. Alcance

**52 requisitos** componen la v1.0: **11 heredados** que ya estaban escritos y nunca se
implementaron, y **41 nuevos** que el backlog introduce.

| Origen | Cantidad | Qué son |
|---|---|---|
| Heredados sin implementar | 10 | Especificados en el PRD base, sin código |
| Heredado y reforzado | 1 | REQ-OPS-002, con un criterio nuevo por el hallazgo de la carrera |
| Nuevos en este delta | 41 | Dependencias, gate, configuración gráfica, contribución, **prioridad de redes, histórico y mapa** |
| **Total en alcance** | **52** | |

**Los otros 45 requisitos del PRD base no se repiten aquí.** Están implementados y verificados en la
v0.6.0; su criterio de aceptación vive en las 17 HU de
[`docs/reverse-sdd/HU/`](../reverse-sdd/HU/INDICE-HU.md). Repetirlos convertiría este documento en
una copia que envejece por separado.

### Convención de identificadores

`REQ-{ÁREA}-{NNN}`, con ÁREA de 2 o 3 letras. Expresión regular canónica: `REQ-[A-Z]{2,3}-\d{3}`.

| Área | Rango que usa este delta | Por qué |
|---|---|---|
| ALE | *(sin números nuevos)* | Solo hereda |
| CFG | **009-012** | El PRD base llega a CFG-008 |
| OPS | **009** | El PRD base llega a OPS-008 |
| OBS | **006-008** | El PRD base llega a OBS-005 |
| ING | **011** | El PRD base llega a ING-010 |
| PIP | **010** | El PRD base llega a PIP-009 |
| **DEP** | 001-008 | **Área nueva**: dependencias y runtime |
| **DEV** | 001-004 | **Área nueva**: entorno de contribución |
| **GUI** | 001-008 | **Área nueva**: panel de configuración |
| **HIS** | 001-006 | **Área nueva**: histórico de eventos |
| **MAP** | 001-005 | **Área nueva**: vista geográfica |

Los rangos no se solapan con el PRD base. Verificado en [08-ANALYZE §1](08-ANALYZE.md).

---

## 2. Requisitos heredados sin implementar

Se listan con su enlace, no con su texto. **Ninguno cambia de redacción**; lo que este kit añade es
la fase, la tarea y el test que los cierran.

| REQ | Capacidad | Especificado desde | Fase | Ítem |
|---|---|---|---|---|
| [REQ-ALE-003](../sdd/specs/01-PRD.md) `[MUST]` | Declaración de alcance bajo Wayland | PRD base | F4 | B-19 |
| [REQ-ALE-004](../sdd/specs/01-PRD.md) `[MUST]`\* | Presentación bajo Wayland | **ADR-010, v0.1.0** | F4 | B-20 |
| [REQ-ING-009](../sdd/specs/01-PRD.md) `[MUST]` | Registro declarativo de fuentes | PRD base · ADR-001 | F3 | B-18, B-21 |
| [REQ-OPS-002](../sdd/specs/01-PRD.md) `[MUST]` | Apagado limpio **y determinista** | Reforzado en este ciclo | F0, F2 | B-07, B-08 |
| [REQ-OPS-003](../sdd/specs/01-PRD.md) `[MUST]` | Estado compartido declarado | PRD base · Art. 6 | F3 | B-24 |
| [REQ-OPS-007](../sdd/specs/01-PRD.md) `[MUST]` | Validación de artefactos de empaquetado | PRD base | F0 | B-14 |
| [REQ-OPS-008](../sdd/specs/01-PRD.md) `[MUST]` | El binario producido se verifica | PRD base | F4 | B-15 |
| [REQ-OBS-002](../sdd/specs/01-PRD.md) `[MUST]` | Identificador de correlación | PRD base | F3 | B-22 |
| [REQ-OBS-003](../sdd/specs/01-PRD.md) `[MUST]` | Umbral de cobertura por criticidad | PRD base | F0 | B-09 |
| [REQ-OBS-004](../sdd/specs/01-PRD.md) `[MUST]` | Separación de pruebas por tipo | PRD base | F0 | B-11 |
| [REQ-OBS-005](../sdd/specs/01-PRD.md) `[MUST]` | Fronteras verificadas por herramienta | PRD base · Art. 5 | F0 | B-06 |

\* **REQ-ALE-004 es el único requisito cuyo grado depende de una decisión pendiente (D-1).** Si D-1
lo confirma `[MUST]`, la v1.0.0 no se publica sin presentación bajo Wayland. Si lo degrada a
`[SHOULD]`, se publica con la limitación declarada por REQ-ALE-003. **No se puede decidir por
defecto**: cambia el criterio de corte del release.

---

## 3. REQ-DEP — Dependencias y runtime *(área nueva)*

### REQ-DEP-001 `[MUST]` — Resolución reproducible para quien instala *(ubicuo)*
EL SISTEMA DEBERÁ versionar su archivo de bloqueo de dependencias, de modo que una instalación en
una máquina limpia resuelva exactamente las mismas versiones que el desarrollador verificó.

*Criterio verificable:* `git ls-files uv.lock` devuelve el archivo y `uv sync --frozen` reproduce el
entorno sin resolver nada.
*Racional: hoy está en `.gitignore:29`; la CI incluso lleva un rodeo por ello —
`cache-dependency-glob: pyproject.toml` con el comentario "uv.lock is gitignored in this repo"
`[VERIFY: .github/actions/setup-python-env/action.yml:16]`.* · **B-01**

### REQ-DEP-002 `[MUST]` — El piso de un rango es un piso de seguridad *(ubicuo)*
EL SISTEMA DEBERÁ declarar cada dependencia con un piso que no admita versiones con avisos de
seguridad conocidos.

*Criterio verificable:* `uv sync --resolution lowest-direct` produce un árbol sin avisos.
*Racional: `Pillow>=10.0` admite **34 avisos** aunque el lockfile resuelva 12.3.0, que tiene cero
(`docs/PAQUETERIA-VERSIONADO.md` P-02).* · **B-02**

### REQ-DEP-003 `[MUST]` — Ninguna versión instalada con aviso abierto *(no deseado)*
SI una dependencia del árbol resuelto tiene un aviso de seguridad publicado con corrección
disponible, ENTONCES el gate DEBERÁ fallar nombrando el paquete y el aviso.

*Criterio verificable:* el gate no reporta `CVE-2026-13346` (`pip` < 26.2). · **B-03**

### REQ-DEP-004 `[MUST]` — El runtime recibe correcciones de errores *(ubicuo)*
EL SISTEMA DEBERÁ exigir una versión de Python que esté en fase de correcciones de errores, no
solo de seguridad.

*Criterio verificable:* `requires-python`, `target-version` de ruff, `python_version` de mypy y los
tres jobs de `build.yml` declaran la misma versión ≥ 3.13.
*Depende de la enmienda [E-01](00-ENMIENDAS-CONSTITUCION.md) y de la decisión D-3.* · **B-04**

### REQ-DEP-005 `[MUST]` — Ningún salto de versión mayor sin decisión *(no deseado)*
SI una dependencia publica una versión mayor nueva, ENTONCES la resolución NO DEBERÁ adoptarla sin
un cambio explícito del rango declarado.

*Criterio verificable:* 8 de los 9 rangos de runtime llevan techo `<X+1`.
*Excepción única y declarada:* `tzdata`, por [E-04](00-ENMIENDAS-CONSTITUCION.md) — son datos IANA,
y ponerle techo congelaría husos horarios caducados. · **B-05**

### REQ-DEP-006 `[MUST]` — El piso de los rangos se audita solo *(por evento)*
CUANDO se ejecute el pipeline de integración, EL SISTEMA DEBERÁ resolver también con la versión
mínima que cada rango permite y auditar ese árbol.

*Criterio verificable:* un piso rebajado deliberadamente hace fallar el pipeline.
*Racional: sin este gate, P-02 volvería sin que nadie lo notara.* · **B-13**

### REQ-DEP-007 `[MUST]` — La compatibilidad se verifica, no se supone *(por evento)*
CUANDO se ejecute el pipeline de integración, EL SISTEMA DEBERÁ ejecutar la suite completa en al
menos dos versiones soportadas del intérprete.

*Criterio verificable:* la matriz de `ci.yml` incluye 3.13 y 3.14 y ambas pasan.
*Racional: hoy `ci.yml` no fija ninguna versión.* · **B-16**

### REQ-DEP-008 `[MUST]` — Ninguna plataforma queda sin auditar *(ubicuo)*
EL SISTEMA DEBERÁ auditar también las dependencias específicas de macOS y Windows, en los ejecutores
de esas plataformas.

*Criterio verificable:* el informe de composición cubre los 9 paquetes de runtime **más** los 6
específicos de plataforma que hoy quedan fuera. · **B-17**

---

## 4. REQ-OBS — Observabilidad y calidad *(extiende el PRD base)*

### REQ-OBS-006 `[MUST]` — El formato no se discute en revisión *(ubicuo)*
EL SISTEMA DEBERÁ aplicar un formateador automático y el gate DEBERÁ fallar ante cualquier archivo
que no lo cumpla.

*Criterio verificable:* `ruff format --check .` sale con código 0 en el gate.
*Racional: 19 archivos divergen hoy sin consecuencia (`docs/code-audit/` P2-2). El formateo inicial
va en un commit aislado para no contaminar diffs de lógica.* · **B-10**

### REQ-OBS-007 `[MUST]` — Duplicación y complejidad tienen umbral *(ubicuo)*
EL SISTEMA DEBERÁ fallar el gate ante duplicación de código o complejidad cognitiva por encima de
los umbrales declarados.

*Criterio verificable:* el gate ejecuta detección de duplicación y medición de complejidad, y las
dos funciones que hoy superan complejidad 12 quedan por debajo del umbral.
*Racional: son dos de las ocho dimensiones que el Art. 8 exige y el gate no cubre.* · **B-12, B-25, B-26**

### REQ-OBS-008 `[MUST]` — La deriva entre especificación y código falla como un lint *(ubicuo)*
EL SISTEMA DEBERÁ verificar en el gate que las decisiones de diseño registradas siguen
correspondiéndose con el código, y DEBERÁ enlazar desde el código a la decisión que lo explica en
los puntos donde la lógica no es evidente por sí sola.

*Criterio verificable:* la comprobación de la capa de intención pasa en el gate, y los tres puntos
de mayor valor —el veredicto de deduplicación, la aceptación del filtro y la resolución de la
referencia automática— llevan su enlace.
*Racional: Art. 9; `docs/CONTEXT_REPORT.md` §6.3.* · **B-27, B-28**

---

## 5. REQ-OPS — Operación *(extiende el PRD base)*

### REQ-OPS-009 `[MUST]` — El binario declara su base, no la hereda *(ubicuo)*
EL SISTEMA DEBERÁ construir el binario de Linux sobre una imagen base fijada explícitamente, de modo
que la versión mínima de sistema que soporta no cambie sin un cambio en el repositorio.

*Criterio verificable:* la construcción declara su imagen base con versión; actualizar el ejecutor
del CI no altera la glibc del binario publicado.
*Racional: hoy la hereda de `ubuntu-latest`. Permitido por la enmienda
[E-03](00-ENMIENDAS-CONSTITUCION.md), que acota "sin contenedores" al producto.* · **B-23**

---

## 6. REQ-CFG — Escritura de configuración *(extiende el PRD base)*

Estos cuatro requisitos son el **contrato de persistencia** que habilita el panel. Describen cómo se
escribe el archivo, no cómo se ve la interfaz — eso es REQ-GUI.

### REQ-CFG-009 `[MUST]` — Escribir no destruye la documentación del archivo *(ubicuo)*
EL SISTEMA DEBERÁ preservar los comentarios, el orden de las secciones y el formato del archivo de
configuración al escribirlo.

*Criterio verificable:* tras guardar un único campo, el archivo conserva sus **46 líneas de
comentarios** y el resto del contenido es idéntico byte a byte salvo el campo modificado.
*Racional: los comentarios son hoy la ayuda en línea del usuario. Exige `tomlkit`; `tomli-w` no lo
cumple.* · **B-35**

### REQ-CFG-010 `[MUST]` — Escritura atómica con respaldo recuperable *(por evento)*
CUANDO se guarde la configuración, EL SISTEMA DEBERÁ escribir mediante archivo temporal y renombrado
atómico, y DEBERÁ conservar la versión anterior recuperable.

*Criterio verificable:* una interrupción durante el guardado deja el archivo original intacto y sin
temporales huérfanos.
*Racional: el mismo criterio que ya rige el estado `[VERIFY: src/vigia_eew/state.py:61]`.* · **B-35**

### REQ-CFG-011 `[MUST]` — Una edición externa no se pisa en silencio *(no deseado)*
SI el archivo de configuración cambió en disco después de que el agente lo cargara, ENTONCES EL
SISTEMA NO DEBERÁ sobrescribirlo sin advertirlo primero.

*Criterio verificable:* modificar el archivo por fuera y guardar desde el panel produce una
advertencia que nombra el conflicto, no una sobrescritura.
*Racional: el panel es el primer componente que escribe en un archivo que el usuario también edita a
mano.* · **B-35**

### REQ-CFG-012 `[MUST]` — Nunca queda en disco una configuración inválida *(no deseado)*
SI los valores a guardar no validan contra el esquema, ENTONCES EL SISTEMA DEBERÁ rechazar la
escritura por completo y conservar el archivo anterior.

*Criterio verificable:* un intento de guardar `severity.info_max >= severity.warning_max` no
modifica el archivo.
*Racional: Art. 3 — una config inválida en disco deja el agente sin arrancar. Validación **antes**
de tocar el archivo, no después.* · **B-35**

---

## 7. REQ-GUI — Panel de configuración *(área nueva)*

### REQ-GUI-001 `[MUST]` — Toda la configuración es alcanzable desde la interfaz *(ubicuo)*
EL SISTEMA DEBERÁ permitir consultar y modificar los **39 campos** de las **10 secciones** de
configuración sin abrir un editor de texto.

*Criterio verificable:* una prueba recorre el esquema y comprueba que cada campo tiene control en el
panel — de modo que **añadir un campo al modelo y no al panel hace fallar la prueba**. · **B-36**

### REQ-GUI-002 `[MUST]` — Los errores se ven antes de guardar *(por evento)*
CUANDO el usuario introduzca un valor, EL SISTEMA DEBERÁ validarlo contra el esquema y mostrar el
error junto al campo, sin esperar al guardado.

*Criterio verificable:* un radio negativo se señala en el campo y el botón de guardar queda
inhabilitado. · **B-36**

### REQ-GUI-003 `[MUST]` — Se puede volver a los valores por defecto *(por evento)*
CUANDO el usuario lo solicite, EL SISTEMA DEBERÁ restaurar los valores por defecto de una sección o
del archivo completo, sin aplicarlos hasta que se guarde. · **B-36**

### REQ-GUI-004 `[MUST]` — El usuario sabe que hace falta reiniciar *(por evento)*
CUANDO se guarde correctamente, EL SISTEMA DEBERÁ indicar que los cambios se aplican al reiniciar el
agente.

*Racional: la configuración se lee **una sola vez, al arrancar** — el filtro, el normalizador y los
cuatro ingestores reciben la suya al construirse. Prometer lo contrario sería mentir hasta que
exista REQ-GUI-007.* · **B-36**

### REQ-GUI-005 `[MUST]` — El archivo sigue siendo accesible *(ubicuo)*
EL SISTEMA DEBERÁ conservar una vía para abrir el archivo de configuración directamente, junto a la
que abre el panel.

*Criterio verificable:* el menú de bandeja ofrece las dos entradas.
*Racional: el archivo sigue siendo la fuente de verdad — es lo que permite versionarlo, copiarlo
entre máquinas y editarlo por SSH. El panel es otra vía de acceso, no un reemplazo.* · **B-36**

### REQ-GUI-006 `[SHOULD]` — Paridad en el frontend de terminal *(opcional)*
DONDE no haya sesión gráfica, EL SISTEMA DEBERÍA ofrecer la misma edición de configuración desde el
panel de terminal.
**Fuera del corte de la v1.0** — P3, no bloquea el release. · **B-37**

### REQ-GUI-007 `[SHOULD]` — Aplicar sin reiniciar *(opcional)*
DONDE la recarga en caliente esté disponible, EL SISTEMA DEBERÍA aplicar la configuración guardada
sin reiniciar el proceso.
**Fuera del corte de la v1.0** — P3. Es lo que permitiría retirar el aviso de REQ-GUI-004. · **B-38**

---

## 8. REQ-DEV — Entorno de contribución *(área nueva)*

### REQ-DEV-001 `[MUST]` — El entorno se levanta en un paso *(por evento)*
CUANDO alguien abra el repositorio en un entorno de desarrollo en contenedor, EL SISTEMA DEBERÁ
proveer intérprete, gestor de proyecto y **las bibliotecas de sistema de Tk** sin pasos manuales.

*Criterio verificable:* en un contenedor recién creado, `uv run vigia-eew --check-config` funciona
sin instalar nada más.
*Racional: el proyecto **necesita tkinter**, que no viene en las imágenes base de Python; la CI ya
lo resuelve con el Python gestionado por `uv` `[COMMITS: 0e707a1]` y un colaborador chocaría con lo
mismo sin ninguna pista.* · **B-34**

### REQ-DEV-002 `[MUST]` — Nadie contribuye con el gate desactivado *(por evento)*
CUANDO se cree el entorno, EL SISTEMA DEBERÁ instalar los hooks de pre-commit automáticamente.

*Criterio verificable:* un commit que viole una regla del gate se rechaza en el contenedor recién
creado, sin que el colaborador haya ejecutado nada.
*Racional: Art. 8.* · **B-34**

### REQ-DEV-003 `[MUST]` — Las pruebas de interfaz real se pueden ejecutar *(ubicuo)*
EL SISTEMA DEBERÁ proveer en el entorno de desarrollo un display virtual que permita ejecutar las
pruebas de interfaz gráfica real.

*Criterio verificable:* `VIGIA_GUI_TESTS=1 pytest` ejecuta las 3 pruebas hoy excluidas por defecto y
pasa. · **B-34**

### REQ-DEV-004 `[MUST]` — La guía de contribución enlaza a los principios *(ubicuo)*
EL SISTEMA DEBERÁ documentar el gate, la convención de commits y **el enlace a la constitución** en
una guía de contribución.

*Racional: la constitución exige que `CLAUDE.md` apunte a ella para que cada agente herede los
principios; un colaborador humano necesita lo mismo por el mismo motivo.* · **B-34**

---

## 8bis. Prioridad de redes sísmicas

### REQ-ING-011 `[MUST]` — Cada fuente declara su prioridad *(ubicuo)*
EL SISTEMA DEBERÁ permitir declarar un orden de preferencia entre las fuentes sísmicas habilitadas.

*Criterio verificable:* la especificación de cada fuente incluye su prioridad, y una configuración
sin prioridades declaradas sigue siendo válida —las fuentes se ordenan al final, no se excluyen.
*Racional: hoy solo existe `enabled` por fuente, sin jerarquía. Depende del registro declarativo
(REQ-ING-009): sin él la prioridad habría que añadirla en cuatro sitios.* · **B-40**

### REQ-PIP-010 `[MUST]` — Al deduplicar prevalece la fuente más prioritaria *(por evento)*
CUANDO el deduplicador determine que dos llegadas corresponden al mismo sismo, EL SISTEMA DEBERÁ
conservar los datos de la fuente de mayor prioridad, **con independencia de cuál llegó antes**.

*Criterio verificable:* dado un sismo reportado por dos fuentes con magnitudes distintas, invertir su
orden de prioridad invierte la magnitud presentada.
*Racional: hoy prevalece la primera llegada, que es un accidente de latencia. El caso concreto es un
sismo local con magnitud automática de una red global frente a magnitud revisada de la red
nacional.* · **B-40**

**Dos límites que este requisito NO cruza**, y que son parte de él:

- **La prioridad no decide si se alerta.** Eso lo sigue decidiendo el filtro (REQ-PIP-003). Una
  fuente de baja prioridad que reporta un sismo relevante alerta igual; solo cede sus datos si otra
  mejor posicionada reporta el mismo. *Racional: lo contrario perdería los sismos locales que solo
  cataloga la red nacional, que es la razón por la que esa fuente existe.*
- **La prioridad no altera el orden ni la concurrencia de las consultas.** Las fuentes siguen siendo
  independientes (REQ-ING-010); serializarlas por prioridad retrasaría la alerta.

### REQ-GUI-008 `[MUST]` — Las redes se eligen y se ordenan desde la interfaz *(ubicuo)*
EL SISTEMA DEBERÁ presentar las fuentes sísmicas como una lista donde se pueda habilitar cada una y
cambiar su orden de prioridad.

*Criterio verificable:* reordenar la lista y guardar produce un archivo de configuración cuyo orden
de prioridad refleja el de la interfaz. · **B-40**

---

## 9. REQ-HIS — Histórico de eventos *(área nueva)*

Habilitada por la enmienda [E-05](00-ENMIENDAS-CONSTITUCION.md).

### REQ-HIS-001 `[MUST]` — Todo evento evaluado queda registrado con su veredicto *(por evento)*
CUANDO el pipeline termine de evaluar un evento, EL SISTEMA DEBERÁ registrarlo en el histórico con su
veredicto —alertado o descartado— y, si fue descartado, **el motivo**.

*Criterio verificable:* un evento fuera de radio aparece en el histórico con motivo "fuera de radio";
un evento alertado aparece marcado como alertado.
*Racional: guardar solo los alertados dejaría sin respuesta la pregunta que más importa cuando el
producto parece fallar: "¿por qué no me avisó de aquel sismo?".* · **B-41**

### REQ-HIS-002 `[MUST]` — El histórico nunca retrasa ni impide una alerta *(no deseado)*
SI el registro en el histórico falla o se demora, ENTONCES la alerta DEBERÁ presentarse igualmente y
el fallo DEBERÁ quedar en el registro de la aplicación.

*Criterio verificable:* con el archivo del histórico en solo lectura, la alerta se presenta y el
agente sigue funcionando.
*Racional: Art. 1 y Art. 3. El histórico es una consecuencia de la alerta, nunca una condición.* · **B-41**

### REQ-HIS-003 `[MUST]` — El esquema está versionado y migra solo *(por evento)*
CUANDO el agente arranque con un histórico de una versión de esquema anterior, EL SISTEMA DEBERÁ
migrarlo sin pérdida y sin intervención del usuario.

*Criterio verificable:* un archivo de la versión de esquema anterior se abre, migra y conserva todas
sus filas. · **B-41**

### REQ-HIS-004 `[MUST]` — El histórico está acotado en tamaño *(por estado)*
MIENTRAS el histórico supere la retención configurada, EL SISTEMA DEBERÁ eliminar las entradas más
antiguas.

*Criterio verificable:* con retención reducida a un día, las entradas anteriores desaparecen tras la
poda. **La retención es configurable y su valor por defecto se declara.**
*Racional: se registran también los descartes, que en un flujo global son bastantes más que las
alertas. El orden de magnitud está estimado en el modelo de datos y debe medirse en el primer
uso.* · **B-41**

### REQ-HIS-005 `[MUST]` — El histórico se consulta por los criterios que importan *(por evento)*
CUANDO el usuario consulte el histórico, EL SISTEMA DEBERÁ permitir filtrar por rango de fechas,
magnitud, distancia, veredicto y red de origen, y ordenar por cualquiera de ellos.

*Criterio verificable:* una consulta por magnitud mínima y rango de fechas devuelve exactamente las
entradas que cumplen ambas. · **B-42**

### REQ-HIS-006 `[MUST]` — El histórico no sale del equipo *(ubicuo)*
EL SISTEMA NO DEBERÁ transmitir el contenido del histórico a ningún destino externo.

*Criterio verificable:* ninguna petición saliente contiene datos del histórico.
*Racional: es un archivo local. Sin sincronización, sin respaldo remoto, sin telemetría —
[E-06](00-ENMIENDAS-CONSTITUCION.md).* · **B-41**

---

## 10. REQ-MAP — Vista geográfica *(área nueva)*

### REQ-MAP-001 `[MUST]` — Las teselas se piden solo con el mapa abierto *(por estado)*
MIENTRAS el mapa no esté abierto, EL SISTEMA NO DEBERÁ realizar ninguna petición al proveedor de
teselas.

*Criterio verificable:* un agente en funcionamiento con el mapa cerrado no genera tráfico hacia el
proveedor de teselas.
*Consecuencia declarada, no oculta:* mientras el mapa está abierto, **el proveedor puede inferir
aproximadamente qué zona mira el usuario**. La caché lo reduce y el carácter bajo demanda lo acota;
no lo elimina. Declarado en [E-06](00-ENMIENDAS-CONSTITUCION.md). · **B-43**

### REQ-MAP-002 `[MUST]` — Sin teselas, el histórico sigue consultable *(no deseado)*
SI no hay red ni teselas en caché, ENTONCES EL SISTEMA DEBERÁ indicar que el mapa no está disponible
y **el listado DEBERÁ seguir funcionando**.

*Criterio verificable:* sin conectividad, la vista de listado responde con normalidad.
*Racional: Art. 3. El histórico es la funcionalidad; el mapa es una vista sobre él.* · **B-43**

### REQ-MAP-003 `[MUST]` — La magnitud se lee de un vistazo *(ubicuo)*
EL SISTEMA DEBERÁ representar cada sismo del mapa con un símbolo cuyo tamaño refleje su magnitud y
cuyo aspecto distinga los alertados de los descartados.

*Criterio verificable:* dos sismos de magnitud 3 y 6 producen símbolos de tamaño distinto y
ordenado. · **B-43**

### REQ-MAP-004 `[MUST]` — Los filtros valen para las dos vistas *(por evento)*
CUANDO el usuario aplique un filtro, EL SISTEMA DEBERÁ aplicarlo simultáneamente al listado y al
mapa.

*Criterio verificable:* filtrar por magnitud mínima reduce las filas del listado y los símbolos del
mapa al mismo conjunto. · **B-42, B-43**

### REQ-MAP-005 `[MUST]` — La procedencia de los datos del mapa está a la vista *(ubicuo)*
EL SISTEMA DEBERÁ mostrar la atribución **"© OpenStreetMap contributors"** de forma visible mientras
el mapa esté en pantalla, e identificarse ante el proveedor con el nombre y la versión de la
aplicación.

*Criterio verificable:* la atribución es visible en el mapa; las peticiones llevan un identificador
de cliente propio.
*Racional: lo exigen la licencia de los datos y la política de uso de las teselas.* · **B-43**

---

## 11. Cobertura y trazabilidad

### 11.1 Requisito → ítem del backlog

Los **37 ítems en alcance** están cubiertos. Ninguno queda sin requisito, y ningún requisito carece
de ítem que lo origine.

| Requisitos | Ítems |
|---|---|
| REQ-DEP-001..008 | B-01, B-02, B-03, B-04, B-05, B-13, B-16, B-17 |
| REQ-OBS-003, OBS-004, OBS-006, OBS-007 | B-09, B-11, B-10, B-12 + B-25, B-26 |
| REQ-OBS-005, OBS-008, OPS-002, OPS-003 | B-06, B-27 + B-28, B-07 + B-08, B-24 |
| REQ-ING-009 | B-18, B-21 |
| REQ-OBS-002 | B-22 |
| REQ-ALE-003, ALE-004 | B-19, B-20 |
| REQ-OPS-007, OPS-008, OPS-009 | B-14, B-15, B-23 |
| REQ-CFG-009..012, REQ-GUI-001..007 | B-35, B-36, B-37, B-38 |
| REQ-DEV-001..004 | B-34 |
| REQ-ING-011, REQ-PIP-010, REQ-GUI-008 | B-40 |
| REQ-HIS-001, REQ-HIS-002, REQ-HIS-003, REQ-HIS-004, REQ-HIS-006 | B-41 |
| REQ-HIS-005, REQ-MAP-004 | B-42 |
| REQ-MAP-001, REQ-MAP-002, REQ-MAP-003, REQ-MAP-005 | B-43 |

### 11.2 Reparto

| Área | Requisitos | MUST | SHOULD |
|---|---|---|---|
| DEP (nueva) | 8 | 8 | 0 |
| **HIS (nueva)** | **6** | **6** | 0 |
| GUI (nueva) | 8 | 6 | 2 |
| **MAP (nueva)** | **5** | **5** | 0 |
| DEV (nueva) | 4 | 4 | 0 |
| CFG (extiende) | 4 | 4 | 0 |
| OBS (extiende) | 3 | 3 | 0 |
| OPS (extiende) | 1 | 1 | 0 |
| **ING (extiende)** | **1** | **1** | 0 |
| **PIP (extiende)** | **1** | **1** | 0 |
| Heredados | 11 | 11 | 0 |
| **Total** | **52** | **50** | **2** |

Los dos `[SHOULD]` —REQ-GUI-006 y REQ-GUI-007— quedan **explícitamente diferidos** fuera del corte
de la v1.0, con su razón en [01-FUNCIONALIDADES §EP-8](01-FUNCIONALIDADES.md).

### 11.3 Criterios Gherkin

Los 41 requisitos nuevos llevan sus criterios de aceptación en las Historias de Usuario:
**86 escenarios** en [HU-101..HU-112](HU/INDICE-HU.md). Los 11 heredados llevan los suyos en el PRD
base o en las HU de reverse-sdd, enlazados desde cada uno.

---

## 12. Constitution check

| Artículo | Cómo lo cumple este delta |
|---|---|
| Art. 1 (la alerta es el producto) | REQ-ALE-003 y ALE-004 cierran la única brecha entre la promesa y lo que se cumple |
| Art. 3 (fail-safe) | REQ-CFG-012: ninguna escritura puede dejar el agente sin arrancar |
| Art. 5 (fronteras ejecutables) | REQ-OBS-005 |
| Art. 6 (estado compartido) | REQ-OPS-002 reforzado, REQ-OPS-003 |
| Art. 8 (gate de ocho dimensiones) | REQ-OBS-003, 004, 006, 007 completan las que faltaban; REQ-DEP-003, 006, 008 cierran la dimensión de composición |
| Art. 9 (spec y código a la vez) | REQ-OBS-008 lo convierte en un lint en lugar de una buena intención |
| Art. 1 (la alerta es el producto) | **REQ-HIS-002 y REQ-MAP-001**: ni el histórico ni las teselas se interponen entre un evento y su alerta |
| Art. 3 (fail-safe) | **REQ-MAP-002**: sin mapa, el listado sigue funcionando |

**Enmiendas que este delta requiere:** seis, en
[00-ENMIENDAS-CONSTITUCION.md](00-ENMIENDAS-CONSTITUCION.md). Cinco están aprobadas; **E-01 espera a
D-3** y bloquea REQ-DEP-004.

**Sobre la privacidad, dicha en voz alta.** REQ-MAP-001 introduce el primer caso en que un tercero
que no es una fuente sísmica recibe una señal de lo que el usuario hace. No es telemetría —el
producto no envía nada sobre el usuario— pero pedir teselas de una zona **revela aproximadamente qué
zona es**. Está acotado (solo con el mapa abierto, con caché) y declarado como requisito en lugar de
quedar enterrado en el código. REQ-HIS-006 cierra la otra mitad: el histórico en sí no sale del
equipo.

**Excepciones solicitadas: una.** REQ-DEP-005 exime a `tzdata` de la regla de techos superiores, con
su justificación escrita en E-04.
