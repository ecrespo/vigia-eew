# Enmiendas a la constitución — para la v1.0

> Artefacto 00 del kit v1.0 · Documento enmendado:
> [`docs/sdd/specs/00-CONSTITUTION.md`](../sdd/specs/00-CONSTITUTION.md)
>
> La propia constitución exige que **cambiar una restricción de stack pase por una enmienda con
> changelog**, y que *"una excepción sin justificación escrita es una violación"*. Este documento
> existe porque **ocho ítems del backlog** cambian restricciones vigentes: B-04, B-05, B-23, B-34,
> B-35, B-36 y B-41 a B-43. Sin él, serían violaciones de la constitución, no mejoras.

## Resumen

| ID | Qué cambia | Habilita | Decisión que lo aprueba |
|---|---|---|---|
| **E-01** | Piso de Python: ≥ 3.12 → **≥ 3.13** | B-04, B-16, B-34 | **D-3**, pendiente |
| **E-02** | La configuración deja de ser de solo lectura | B-35, B-36, B-37, B-38 | Petición del mantenedor, tomada |
| **E-03** | "Contenedores: ninguno" se acota a **el producto**, no al desarrollo ni al build | B-34, B-23 | Decisión del mantenedor, tomada |
| **E-04** | Excepción a la regla de techos: `tzdata` | B-05 | Técnica, sin decisión pendiente |
| **E-05** | "Sin base de datos" se acota al **estado operativo** | B-41, B-42, B-43 | Petición del mantenedor, tomada |
| **E-06** | **Regla nueva**: los destinos de red del agente se declaran | B-43 | Consecuencia de E-05 y del mapa |

**Cinco de las seis ya están decididas.** Solo E-01 espera a D-3, y su contenido técnico ya está
argumentado abajo para que la decisión sea un sí o un no, no una investigación.

**E-06 es la única que *añade* una restricción en vez de relajarla.** Las otras cinco amplían lo que
el proyecto puede hacer; esa lo estrecha, y existe precisamente porque el mapa abre una puerta que
conviene dejar acotada antes de que la cruce algo más.

---

## E-01 · El piso del lenguaje sube a Python 3.13

**Fila afectada:** `| Lenguaje | Python | ≥ 3.12 (el piso 3.11 existía solo por tomllib) |`
**Queda:** `| Lenguaje | Python | ≥ 3.13 |`

**Razón.** La constitución fijó 3.12 y el calendario oficial la desmiente: **3.11 y 3.12 están
ambas en fase security-only**, es decir, ya no reciben correcciones de errores. Un 1.0.0 que se
publica hoy sobre 3.12 nace sobre una versión con dos años de vida restante y sin arreglos de
comportamiento. 3.13 está en fase *bugfix* hasta octubre de 2027 y soportada hasta octubre de 2029.

El coste es nulo: la única razón del piso 3.11 era `tomllib`, disponible desde entonces, y la
evidencia está medida en [`docs/PAQUETERIA-VERSIONADO.md` §2](../PAQUETERIA-VERSIONADO.md).

**Lo que arrastra.** El cambio no es solo `requires-python`: son cinco sitios, y tres de ellos están
en un archivo que nadie mira al editar `pyproject.toml`.

| Archivo | Valor hoy |
|---|---|
| `pyproject.toml:14` | `requires-python = ">=3.11"` |
| `pyproject.toml:87` | `target-version = "py311"` (ruff) |
| `pyproject.toml:93` | `python_version = "3.11"` (mypy) |
| `.github/workflows/build.yml:39, 54, 69` | `python-version: "3.11"` — **tres veces** |

**Consecuencia que hay que aceptar por escrito:** es un cambio incompatible para quien esté en 3.11
o 3.12. En un proyecto que aún no ha publicado su 1.0.0 eso es exactamente el momento de hacerlo;
después del 1.0.0 exigiría una mayor.

**Estado:** pendiente de **D-3**. Mientras no se apruebe, la Fase 1 del plan no arranca.

---

## E-02 · La configuración pasa de solo lectura a escribible

**Fila afectada:** `| Validación y config | pydantic sobre tomllib (config de solo lectura) | ... |`
**Queda:** `| Validación y config | pydantic sobre tomllib para leer; tomlkit para escribir | pydantic ≥ 2.13, tomlkit ≥ 0.15 |`

**Razón.** El panel gráfico de configuración (B-36) **guarda cambios**, y eso contradice una
decisión vigente y deliberada: ADR-007 eligió `tomllib` —el lector de la biblioteca estándar, que
no tiene escritor— y registró la consecuencia con estas palabras: *"writing config isn't needed in
v1"*. Esa frase era correcta cuando se escribió; deja de serlo en el momento en que el producto
ofrece una interfaz para editar.

**Lo que la enmienda NO cambia**, y conviene que quede escrito porque es lo que evita que la
funcionalidad se desmadre:

1. **El archivo TOML sigue siendo la fuente de verdad.** El panel es otra vía de acceso, no un
   reemplazo. Es lo que permite versionar la configuración, copiarla entre máquinas y editarla por
   SSH.
2. **Sigue sin haber base de datos.** La fila de persistencia no se toca.
3. **La lectura sigue siendo `tomllib`.** `tomlkit` entra solo en la ruta de escritura, que es la
   única que necesita preservar comentarios.

**Dependencia nueva que introduce:** `tomlkit`, una sola. Se elige sobre `tomli-w` porque
**preserva los comentarios y el formato**, y la plantilla de configuración lleva **46 líneas de
comentarios** que hoy son la ayuda en línea del usuario. Un escritor que no los preserve los borra
en el primer guardado.

**Estado:** aprobada. La decisión de ofrecer configuración gráfica ya está tomada; esta enmienda es
su consecuencia formal, no una pregunta abierta. El diseño está en
[ADR-019](04-TECHNICAL-DESIGN-DELTA.md).

---

## E-03 · "Contenedores: ninguno" se acota al producto

**Fila afectada:** `| Contenedores | Ninguno. Es un agente de escritorio | — |`
**Queda:** `| Contenedores | Ninguno para el producto. Permitidos para desarrollo y construcción | — |`

**Razón.** Dos ítems del backlog usan contenedores y, tal como está redactada la fila, **ambos son
violaciones de la constitución**:

- **B-34** — devcontainer para colaboradores.
- **B-23** — construir el binario de Linux en una imagen con base fijada, en lugar de heredar la
  glibc de `ubuntu-latest`.

La restricción original apuntaba a algo real y **sigue siendo válida en su intención**: contenerizar
el producto es lo que no tiene sentido, porque el agente necesita sesión gráfica, audio y bus del
usuario, y exponerlos desmonta el aislamiento que justificaría el contenedor. Eso no cambia — sigue
listado como descartado en el backlog §7.

Lo que la redacción no distinguía es que **un contenedor de desarrollo y uno de build no ejecutan el
producto para nadie**: uno prepara un entorno de trabajo reproducible, el otro produce un binario
con una glibc conocida. Ninguno de los dos toca la razón por la que el producto no se contenedoriza.

| Uso | ¿Permitido? | Por qué |
|---|---|---|
| Ejecutar el agente en producción | **No** | Necesita sesión gráfica, audio y bus del usuario |
| Entorno de desarrollo (devcontainer) | **Sí** | No ejecuta el producto para un usuario final; con Xvfb incluso amplía lo que se puede probar |
| Construcción del binario de Linux | **Sí** | Fija la glibc en vez de heredar la del runner del CI |

**Estado:** aprobada. Es una precisión de redacción, no un cambio de criterio: la intención original
se conserva íntegra y se limita a lo que de verdad quería prohibir.

---

## E-04 · Excepción a la regla de techos superiores: `tzdata`

**Regla afectada:** *"todo rango de dependencia DEBERÁ llevar techo superior (`>=X,<Y`)"*.
**Queda:** igual, con **una excepción nombrada**: `tzdata`.

**Razón.** `tzdata` no publica una API: publica **la base de datos de zonas horarias de la IANA**.
Sus versiones son fechas (`2026.2`, `2026.3`) y cada una corrige husos que cambiaron por decisión
de algún gobierno. Ponerle techo significa quedarse con datos de zonas caducados, que es
precisamente el fallo que el proyecto no puede permitirse: la hora local de la alerta se calcula
con esos datos (Art. 4 y REQ-PIP-004).

Es la única de las nueve dependencias de runtime donde "no saltar de mayor sin revisarlo" trabaja
en contra del producto. Las otras ocho llevan techo.

**Estado:** aprobada. Sin decisión pendiente — es una consecuencia técnica, y dejarla implícita
convertiría B-05 en un incumplimiento aparente de la regla cada vez que alguien la auditara.

---

## E-05 · "Sin base de datos" se acota al estado operativo

**Fila afectada:** `| Persistencia | JSON atómico en disco vía platformdirs. **Sin base de datos** | — |`
**Queda:** `| Persistencia | Estado operativo: JSON atómico vía platformdirs. Histórico: SQLite (stdlib), mismo directorio | — |`

**Razón.** El histórico de sismos (B-41) necesita responder preguntas que un JSON no responde sin
cargarse entero en memoria: *"sismos de más de magnitud 4 en los últimos seis meses a menos de 200
km"*. La restricción original protegía algo real y **sigue protegiéndolo**; lo que no distinguía es
que hay dos problemas de persistencia distintos bajo el mismo techo.

| | Estado operativo | Histórico |
|---|---|---|
| Para qué | No repetir una alerta ya presentada | Consultar el pasado |
| Tamaño | Unos KB, podado a 24 h | Decenas de miles de filas al año |
| Consulta | Pertenencia: *¿ya alerté esto?* | Rango de fechas, magnitud, distancia, región, red |
| Cuándo se lee | En cada evento, en la ruta caliente | Cuando el usuario abre la vista |
| Coste de equivocarse | Una alerta repetida o perdida | Una consulta lenta |

**El argumento de la restricción original —"son unos KB en memoria consultados por pertenencia"— es
literalmente cierto de la columna izquierda y literalmente falso de la derecha.** Por eso la enmienda
acota en lugar de derogar: **el estado operativo sigue en JSON**, sin excepción.

**Lo que hace la enmienda defendible: SQLite es biblioteca estándar.**

| Preocupación razonable | Por qué no aplica aquí |
|---|---|
| "Añade una dependencia" | `sqlite3` viene con Python. Cero dependencias nuevas |
| "Añade un servicio que administrar" | Es un archivo. Sin proceso, sin puerto, sin credenciales |
| "Complica el empaquetado" | Ya viaja dentro del intérprete que PyInstaller empaqueta |
| "Complica el respaldo del usuario" | Un archivo más junto al que ya existe, en el mismo directorio por plataforma |

**Lo que la enmienda NO autoriza**, y conviene escribirlo para que nadie lo extienda por analogía:

1. **No** mover la configuración a base de datos — sigue descartado, perdería los comentarios.
2. **No** mover el estado operativo — la ruta caliente de la alerta no toca SQLite.
3. **No** un motor cliente-servidor. Si algún día hiciera falta, es otra enmienda con otro debate.

**Estado:** aprobada. El histórico y el mapa entran en el corte de la v1.0 por decisión del
mantenedor. El diseño está en [ADR-025](04-TECHNICAL-DESIGN-DELTA.md) y el esquema en
[05-DATA-MODEL-DELTA §3](05-DATA-MODEL-DELTA.md).

---

## E-06 · Los destinos de red del agente se declaran *(regla nueva)*

**No hay fila que enmendar: esta regla no existía.** Se añade a las restricciones del stack:

> **Destinos de red.** El agente contacta únicamente con: (a) las fuentes sísmicas declaradas en su
> configuración, (b) el servicio de geolocalización por IP, una sola vez y solo si no hay referencia
> manual, y (c) **el proveedor de teselas del mapa, solo mientras el usuario tiene el mapa abierto**.
> Cualquier destino nuevo exige una enmienda. Ninguna petición saliente lleva datos del usuario más
> allá de lo que la propia consulta requiere.

**Razón.** Hasta la v1.0, el agente hablaba con fuentes sísmicas y, una única vez, con un servicio de
geolocalización. El mapa (B-43) introduce **un tipo de destino nuevo: un proveedor de teselas**. Es
un cambio pequeño en código y grande en propiedad del producto — y es exactamente el tipo de cambio
que se acumula sin que nadie lo decida si no queda escrito.

**Qué se decidió sobre el mapa, y por qué así:**

| Decisión | Razón |
|---|---|
| **OpenStreetMap** como proveedor | Datos abiertos, sin clave de API, sin cuenta que registrar |
| Teselas **solo con el mapa abierto** | Nunca en segundo plano. El agente en reposo sigue sin hablar con nadie salvo sus fuentes |
| **Caché local** de teselas | Reduce peticiones repetidas y hace el mapa utilizable sin red tras el primer uso |
| **Atribución visible**: "© OpenStreetMap contributors" | Lo exige la licencia de los datos |
| Cliente **identificado** por nombre y versión, sin descargas masivas | Lo exige la política de uso de las teselas |
| **Sin mapa → el listado sigue funcionando** | Art. 3. El histórico es la funcionalidad; el mapa es una vista sobre él |

**La consecuencia honesta que hay que aceptar:** pedir una tesela revela al proveedor,
aproximadamente, qué zona está mirando el usuario. La caché lo reduce y el carácter bajo demanda lo
acota, pero **no lo elimina**. Es información que hoy no sale del equipo y a partir de la v1.0 sí,
mientras el mapa esté abierto. Queda declarado en REQ-MAP-001 en lugar de descubrirse leyendo el
código.

**Lo que esta regla protege hacia adelante:** que la próxima funcionalidad que quiera "solo consultar
un servicio rápido" tenga que pasar por una enmienda en vez de por un `import`.

**Estado:** aprobada.

---

## Registro de enmiendas — para copiar a la constitución al aprobarse

Esta tabla es el contenido que sustituye a la fila `| — | — | Ratificación inicial v1.0 | — |
pendiente |` de la sección **Enmiendas** cuando D-3 se resuelva.

| Fecha | Artículo | Cambio | Razón | Aprobado por |
|---|---|---|---|---|
| 2026-09-06 | Ratificación | Ratificación inicial | — | *pendiente* |
| *(fecha de D-3)* | Stack · Lenguaje | Piso Python ≥ 3.12 → **≥ 3.13** | 3.12 en security-only; ver `PAQUETERIA-VERSIONADO.md` §2 | *pendiente (D-3)* |
| 2026-09-06 | Stack · Config | Config de solo lectura → **escribible** con `tomlkit` | Panel gráfico de configuración; enmienda ADR-007 | Mantenedor |
| 2026-09-06 | Stack · Contenedores | "Ninguno" → **ninguno para el producto**; permitidos en desarrollo y build | Devcontainer (B-34) y build con glibc fijada (B-23) | Mantenedor |
| 2026-09-06 | Regla de versiones | Excepción nombrada: `tzdata` sin techo superior | Son datos IANA, no una API | Mantenedor |
| 2026-09-06 | Stack · Persistencia | "Sin base de datos" → **solo para el estado operativo**; SQLite para el histórico | El histórico exige consultas por rango que un JSON no da; SQLite es stdlib | Mantenedor |
| 2026-09-06 | Stack · **Destinos de red** *(regla nueva)* | Los destinos externos se declaran; uno nuevo exige enmienda | El mapa introduce un proveedor de teselas | Mantenedor |

## Constitution check de este documento

| Artículo | Cómo lo cumple |
|---|---|
| Art. 1 (la alerta es el producto) | E-05 y E-06 no tocan la ruta caliente: ni SQLite ni las teselas se interponen entre un evento y su alerta |
| Art. 3 (fail-safe) | E-02 exige validar antes de escribir; E-06 exige que sin mapa el listado siga funcionando |
| Art. 8 (gate de ocho dimensiones) | E-03 no relaja ninguna dimensión: el devcontainer **instala** el gate, no lo evita |
| Art. 9 (spec y código en el mismo cambio) | Este documento se escribe **antes** que el código que lo necesita, no después |

**Excepciones solicitadas: una** — E-04, con su justificación escrita arriba.

**Dirección de las enmiendas.** Cinco amplían lo que el proyecto puede hacer y una lo estrecha. Esa
proporción es la esperada cuando un producto pasa de 0.6.0 a 1.0.0 —se añade capacidad— pero conviene
mirarla: **una constitución que solo se relaja deja de restringir**. E-06 existe porque el mapa abrió
una puerta, y cerrarla parcialmente en el mismo movimiento es lo que evita que la próxima
funcionalidad la cruce sin que nadie lo note.
