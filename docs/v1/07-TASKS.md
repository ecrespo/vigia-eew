# Tasks — Vigía-eew v1.0

> Artefacto 07 del kit v1.0 · Specs de origen: [02-PRD-DELTA](02-PRD-DELTA.md) ·
> [03-API-SPEC-DELTA](03-API-SPEC-DELTA.md) · [04-TECHNICAL-DESIGN-DELTA](04-TECHNICAL-DESIGN-DELTA.md) ·
> [05-DATA-MODEL-DELTA](05-DATA-MODEL-DELTA.md) · [06-IMPLEMENTATION-PLAN](06-IMPLEMENTATION-PLAN.md)
> **49 tareas** cubriendo las 9 fases · Commit base `c3a2c29`

## Convenciones

- **Orden = orden de ejecución**, salvo las marcadas `[P]`, que no comparten archivos ni dependencia.
- **Estados:** `[ ]` pendiente · `[~]` en curso · `[x] fecha` hecha · `[!]` bloqueada, con nota.
- **Done** es un comando o una observación concreta, nunca "terminado".
- Cada tarea cita el requisito que implementa. Una tarea sin requisito significa que falta el
  requisito o que sobra la tarea.
- **El progreso se marca en este archivo**, para que cualquier sesión pueda retomar.
- Convención de commits del proyecto: uno por tarea o grupo coherente, `feat:`/`fix:`/`chore:`/`docs:`,
  cuerpo que explica qué y por qué.

> **Primera tanda: T-101 a T-105.** Ejecutar, revisar, ajustar y solo entonces escalar. Soltar las 49
> de golpe es el anti-patrón que este método existe para evitar.

---

## Fase 0 · Base verificable

### [ ] T-101 · Versionar el lockfile
- **Qué**: sacar `uv.lock` de `.gitignore:29`, confirmarlo, y devolver la caché de CI a
  `cache-dependency-glob: uv.lock`, retirando el comentario que declaraba el rodeo.
- **REQ**: REQ-DEP-001 · **CA**: CA-101.1, CA-101.2
- **Archivos**: `.gitignore`, `uv.lock`, `.github/actions/setup-python-env/action.yml`
- **Depende de**: —
- **Done**: `git ls-files uv.lock` devuelve el archivo; `uv sync --frozen` reproduce el entorno en un
  clon limpio.
- **Nota**: a partir de aquí cada actualización de dependencia aparece en el diff. Es el efecto
  buscado; los PRs de dependencias se vuelven más ruidosos y más informativos a la vez.

### [ ] T-102 · Contratos de fronteras **[P]**
- **Qué**: declarar los cuatro contratos de importación derivados del grafo actual y añadir su
  verificación al gate.
- **REQ**: REQ-OBS-005 · **CA**: CA-103.4, CA-103.5
- **Archivos**: `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`
- **Depende de**: —
- **Done**: una importación que cruce una frontera declarada hace fallar el gate; el código actual
  pasa sin cambios.
- **Nota**: el grafo a nivel de archivo dio **0 ciclos**. Los contratos no arreglan un ciclo — impiden
  el primero.

### [ ] T-103 · Test de la carrera de apagado — **debe fallar** **[P]**
- **Qué**: prueba que solicita la parada antes de que el hilo trabajador publique su bucle y su
  supervisor, y comprueba que la cancelación ocurre.
- **REQ**: REQ-OPS-002 · **CA**: CA-103.1
- **Archivos**: `tests/test_app_shutdown_race.py`
- **Depende de**: —
- **Done**: **el test falla** contra `c3a2c29`, y el fallo describe la cancelación omitida, no un
  tiempo de espera agotado.
- **Nota**: esta tarea entrega un test rojo, a propósito. Escribirlo después del arreglo no
  demostraría que el problema existía.

### [ ] T-104 · Marcadores de tipo de prueba **[P]**
- **Qué**: marcadores `integration` y `gui` declarados y aplicados a las pruebas que corresponden.
- **REQ**: REQ-OBS-004 · **CA**: CA-102.5
- **Archivos**: `pyproject.toml`, `tests/`
- **Depende de**: —
- **Done**: `pytest -m "not integration and not gui"` ejecuta solo las unitarias y termina en tiempo
  apto para el gate de commit.

### [ ] T-105 · Activar la regla de formato **[P]**
- **Qué**: `ruff format --check` en el gate de pre-commit y en el CI. **Sin reformatear todavía.**
- **REQ**: REQ-OBS-006 · **CA**: CA-102.3
- **Archivos**: `.pre-commit-config.yaml`, `.github/workflows/ci.yml`
- **Depende de**: —
- **Done**: el gate falla sobre el código actual, señalando los 19 archivos.

### [ ] T-106 · Reformatear los 19 archivos
- **Qué**: ejecutar el formateador sobre todo el código, **en un commit que no contiene nada más**.
- **REQ**: REQ-OBS-006 · **CA**: CA-102.4
- **Depende de**: T-105
- **Done**: el gate de T-105 pasa; el commit no toca ninguna línea de lógica.
- **Nota**: separado de T-105 a propósito. Mezclarlos produce un diff donde el cambio real es
  imposible de encontrar.

### [ ] T-107 · Umbral de cobertura que muerde
- **Qué**: cobertura de líneas y ramas con umbral por criticidad —85 % en pipeline y estado, 70 % en
  ingesta, 40 % en adaptadores— que hace fallar el CI.
- **REQ**: REQ-OBS-003 · **CA**: CA-102.1, CA-102.2
- **Archivos**: `pyproject.toml`, `.github/workflows/ci.yml`
- **Depende de**: T-104
- **Done**: bajar deliberadamente la cobertura de un módulo del pipeline hace fallar el CI nombrando
  el módulo.

### [ ] T-108 · Validación de recursos de empaquetado **[P]**
- **Qué**: comprobar formato y dimensiones de cada recurso requerido por el empaquetador, **antes**
  de invocarlo.
- **REQ**: REQ-OPS-007 · **CA**: CA-107.1, CA-107.2
- **Archivos**: script de validación, `.github/workflows/build.yml`
- **Depende de**: —
- **Done**: un recurso deliberadamente inválido hace fallar el build antes del empaquetador; los
  recursos actuales pasan.
- **Nota**: rompió dos releases consecutivas (`7b1c71c`, `c38d9f6`).

### [ ] T-109 · Auditar las dependencias de macOS y Windows **[P]**
- **Qué**: extender la auditoría de composición a los 6 paquetes específicos de plataforma, en los
  ejecutores que ya existen.
- **REQ**: REQ-DEP-008 · **CA**: CA-101.8
- **Archivos**: `.github/workflows/security.yml`
- **Depende de**: T-101
- **Done**: el informe cubre 15 paquetes, no 9.

### [ ] T-110 · ADR de configuración escribible y enmiendas **[P]**
- **Qué**: publicar ADR-019 y ADR-025, y **las seis enmiendas** a la constitución en el repositorio, con su
  changelog.
- **REQ**: habilita REQ-CFG-009, REQ-CFG-010, REQ-CFG-011, REQ-CFG-012 y toda el área REQ-HIS · **CA**: —
- **Archivos**: `docs/TECHNICAL-DESIGN.md`, `docs/sdd/specs/00-CONSTITUTION.md`
- **Depende de**: —
- **Done**: la tabla de enmiendas de la constitución contiene las seis filas de
  [00-ENMIENDAS §Registro](00-ENMIENDAS-CONSTITUCION.md); ADR-007 y ADR-010 quedan marcados como
  enmendados.
- **Nota**: es documentación, y **bloquea las Fases 5 y 6**. Sin E-02 el panel contradice ADR-007; sin
  E-05 el histórico contradice la restricción "sin base de datos".

---

## Fase 1 · Runtime y contribución

### [ ] T-111 · Subir el runtime a Python 3.13 `[!]`
- **Qué**: `requires-python`, `target-version` de ruff, `python_version` de mypy y **los tres sitios**
  de `build.yml`; retirar los clasificadores de 3.11 y 3.12.
- **REQ**: REQ-DEP-004 · **CA**: CA-101.5
- **Archivos**: `pyproject.toml:14,87,93`, `.github/workflows/build.yml:39,54,69`, `CHANGELOG.md`
- **Depende de**: T-101 · **Bloqueada por D-3 y la enmienda E-01**
- **Done**: `pytest`, `ruff check .` y `mypy src` en verde; los tres jobs producen binario; el
  changelog declara el cambio de requisito.
- **Vuelta atrás**: `git revert`. Al ser metadatos y CI, sin lógica, lo deshace por completo.

### [ ] T-112 · Matriz de versiones en integración
- **Qué**: matriz con 3.13 y 3.14 en `ci.yml`, que hoy no fija ninguna versión.
- **REQ**: REQ-DEP-007 · **CA**: CA-101.6
- **Archivos**: `.github/workflows/ci.yml`
- **Depende de**: T-111
- **Done**: la suite completa pasa en ambas versiones.

### [ ] T-113 · Entorno de desarrollo en contenedor
- **Qué**: definición de contenedor con el intérprete exigido, el gestor, **las bibliotecas de
  sistema de Tk** y un display virtual; comando posterior a la creación que sincroniza dependencias
  e instala los hooks.
- **REQ**: REQ-DEV-001, REQ-DEV-002, REQ-DEV-003 · **CA**: CA-109.1..109.4
- **Archivos**: `.devcontainer/devcontainer.json`
- **Depende de**: T-111
- **Done**: en un contenedor recién creado, `uv run vigia-eew --check-config` funciona sin instalar
  nada; un commit que viola el gate se rechaza; `VIGIA_GUI_TESTS=1 pytest` ejecuta y pasa las 3
  pruebas de interfaz real.

### [ ] T-114 · Guía de contribución **[P]**
- **Qué**: el gate de tres comandos, la convención de commits y **el enlace a la constitución**.
- **REQ**: REQ-DEV-004 · **CA**: CA-109.5
- **Archivos**: `CONTRIBUTING.md`, `README.md`
- **Depende de**: T-113
- **Done**: la guía existe, está enlazada desde el README y su enlace a la constitución resuelve.

---

## Fase 2 · Cadena de suministro y gate completo

### [ ] T-115 · Piso de seguridad de Pillow
- **Qué**: `Pillow>=12.3.0,<13`. El piso pasa a ser el piso de seguridad real.
- **REQ**: REQ-DEP-002 · **CA**: CA-101.3
- **Archivos**: `pyproject.toml`, `uv.lock`
- **Depende de**: T-111
- **Done**: `uv sync --resolution lowest-direct` resuelve Pillow sin avisos.

### [ ] T-116 · Actualizar `pip` por CVE-2026-13346 **[P]**
- **Qué**: re-bloquear con `pip` ≥ 26.2.
- **REQ**: REQ-DEP-003 · **CA**: CA-101.3
- **Depende de**: T-111
- **Done**: la auditoría no reporta `CVE-2026-13346`.
- **Nota**: es la misma acción que A-4 del plan de paquetería y R-05 del de remediación. **Se ejecuta
  aquí una sola vez**; allí quedan como referencia cruzada.

### [ ] T-117 · Techos superiores en los rangos
- **Qué**: techo `<X+1` en 8 de los 9 rangos de runtime. **`tzdata` queda exento**, por E-04.
- **REQ**: REQ-DEP-005 · **CA**: CA-101.7
- **Archivos**: `pyproject.toml`, `uv.lock`
- **Depende de**: T-111
- **Done**: 8 de 9 rangos con techo; un `uv lock` no adopta una mayor nueva sin cambio explícito.

### [ ] T-118 · Gate de resolución mínima
- **Qué**: resolver también con la versión mínima que cada rango permite, y auditar ese árbol en CI.
- **REQ**: REQ-DEP-006 · **CA**: CA-101.4
- **Archivos**: `.github/workflows/security.yml`
- **Depende de**: T-115, T-117
- **Done**: rebajar deliberadamente un piso hace fallar el pipeline nombrando el paquete.
- **Nota**: es lo que impide que el hallazgo de Pillow vuelva sin que nadie lo note.

### [ ] T-119 · Sincronizar el estado compartido de la aplicación
- **Qué**: lock más evento de "runtime listo" para `_loop` y `_sup`, siguiendo el patrón que el
  proyecto ya usa en `agent_state.py:18`.
- **REQ**: REQ-OPS-002 · **CA**: CA-103.2, CA-103.3
- **Archivos**: `src/vigia_eew/app.py:420,431,443`
- **Depende de**: **T-103** (su test debe existir y fallar antes)
- **Done**: el test de T-103 pasa; la suite completa sigue verde.

### [ ] T-120 · Gate de duplicación y complejidad
- **Qué**: detección de duplicación y medición de complejidad cognitiva en el gate, con umbrales
  declarados.
- **REQ**: REQ-OBS-007 · **CA**: CA-102.6
- **Archivos**: `.pre-commit-config.yaml`, `.github/workflows/ci.yml`
- **Depende de**: T-106
- **Done**: duplicación introducida deliberadamente hace fallar el gate señalando ambas ubicaciones.

---

## Fase 3 · Estructura interna

### [ ] T-121 · Contrato `SourceSpec` y registro de las cuatro fuentes
- **Qué**: el registro declarativo que sustituye a la escalera del normalizador y a las cuatro
  fábricas.
- **REQ**: REQ-ING-009 · **CA**: CA-104.2, CA-104.3, CA-104.5, CA-104.6
- **Archivos**: `src/vigia_eew/ingest/registry.py` *(nuevo)*, `src/vigia_eew/pipeline/normalize.py:55`
- **Depende de**: T-102
- **Done**: sin escaleras por tipo de fuente en el pipeline; la suite de ingesta pasa sin
  modificarse.

### [ ] T-122 · Separar el cableado de la orquestación
- **Qué**: `wiring.py` con la construcción de dependencias que hoy vive en `Application`.
- **REQ**: REQ-ING-009 · **CA**: CA-104.1, CA-104.4
- **Archivos**: `src/vigia_eew/wiring.py` *(nuevo)*, `src/vigia_eew/app.py`
- **Depende de**: T-121
- **Done**: fan-out del módulo de aplicación ≤ 8 y su tamaño por debajo de 300 líneas; añadir una
  fuente de prueba toca tres archivos.
- **Nota**: cierra el hallazgo P1-1 de la evaluación de arquitectura — fan-out 25 sobre 40 módulos.

### [ ] T-123 · Identificador de correlación en el contrato interno
- **Qué**: campo de correlación generado en la ingesta y propagado por normalización y filtro.
- **REQ**: REQ-OBS-002 · **CA**: CA-105.1, CA-105.3
- **Archivos**: `src/vigia_eew/models.py`, `src/vigia_eew/ingest/`, `src/vigia_eew/pipeline/`
- **Depende de**: T-121
- **Done**: una búsqueda por el identificador devuelve ingesta, normalización y veredicto de filtro.

### [ ] T-124 · Correlación a través de la deduplicación y la presentación
- **Qué**: el deduplicador **enlaza** el identificador de la llegada descartada con el de la
  superviviente; la presentación lo registra.
- **REQ**: REQ-OBS-002 · **CA**: CA-105.2, CA-105.4, CA-105.5
- **Archivos**: `src/vigia_eew/pipeline/dedup.py`, `src/vigia_eew/notify/`
- **Depende de**: T-123
- **Done**: un sismo por dos fuentes se recupera como un solo recorrido de cinco etapas; ninguna
  petición saliente contiene el identificador.
- **Nota**: el enlace en la deduplicación es **el punto de la tarea**. Sin él queda justo el hueco que
  se quería cubrir.

### [ ] T-125 · Contrato de hilos documentado **[P]**
- **Qué**: tabla que declara, por cada dato mutable accedido por más de un hilo, a qué hilo pertenece
  y con qué primitiva se sincroniza.
- **REQ**: REQ-OPS-003 · **CA**: CA-103.6
- **Archivos**: `lat.md/conventions.md`
- **Depende de**: T-119
- **Done**: la tabla existe y el estado compartido de la aplicación aparece en ella.

### [ ] T-126 · Lote de calidad agrupado
- **Qué**: los nueve ítems P3 en un PR: duplicación entre los dos lectores FDSN, acceso al estado,
  fixture repetido, espera en un test, tres pruebas sin aserción y el `assert` del modelo.
- **REQ**: REQ-OBS-007 · **CA**: CA-102.6
- **Depende de**: T-120
- **Done**: el gate de duplicación pasa; las tres pruebas sin aserción la tienen.

### [ ] T-127 · Bajar la complejidad de dos funciones **[P]**
- **Qué**: extraer la lectura de fila del poller de GEOFON; simplificar la ramificación de la CLI.
- **REQ**: REQ-OBS-007 · **CA**: CA-102.7
- **Archivos**: `src/vigia_eew/ingest/rest_geofon.py`, `src/vigia_eew/cli.py:56`
- **Depende de**: T-120
- **Done**: ninguna función supera el umbral declarado de complejidad cognitiva.

### [ ] T-128 · Verificación de la capa de intención en el gate **[P]**
- **Qué**: la comprobación de coherencia entre decisiones y código como hook.
- **REQ**: REQ-OBS-008 · **CA**: CA-103.7
- **Archivos**: `.pre-commit-config.yaml`
- **Depende de**: T-102
- **Done**: un enlace roto hace fallar el gate igual que un error de estilo.

### [ ] T-129 · Backlinks en los tres puntos de mayor valor
- **Qué**: enlace desde el código a la decisión que lo explica en el veredicto de deduplicación, la
  aceptación del filtro y la resolución de la referencia automática.
- **REQ**: REQ-OBS-008 · **CA**: CA-103.7
- **Archivos**: `src/vigia_eew/pipeline/dedup.py`, `src/vigia_eew/pipeline/filter.py`,
  `src/vigia_eew/geoloc.py`
- **Depende de**: T-128
- **Done**: los tres enlaces resuelven y el gate los verifica.
- **Nota**: es el ítem que ninguna ola del backlog había situado. Va aquí por su dependencia de
  T-128.

---

## Fase 4 · La promesa del producto

### [ ] T-130 · Declarar el alcance de la garantía de alerta
- **Qué**: matriz de entornos —dónde la presentación por encima de todo está garantizada y dónde
  no— en la documentación **y en el estado del agente**, con detección de entorno degradable.
- **REQ**: REQ-ALE-003 · **CA**: CA-106.1, CA-106.2, CA-106.3
- **Archivos**: `README.md`, `src/vigia_eew/agent_state.py`, `src/vigia_eew/tray.py`
- **Depende de**: **D-1**
- **Done**: la matriz está publicada; un entorno no reconocido se trata como no confirmado y el
  agente arranca igual.
- **Nota**: **es independiente del resultado del spike.** Si T-131 concluye que no es viable, esta
  tarea sigue siendo obligatoria — es lo único que impide que el producto siga prometiendo de más.

### [ ] T-131 · Spike de presentación bajo Wayland
- **Qué**: verificar experimentalmente si la presentación garantizada es alcanzable por el camino de
  ADR-010, con un veredicto escrito: viable, viable con condiciones, o no viable.
- **REQ**: prepara REQ-ALE-004 · **CA**: —
- **Depende de**: T-130
- **Done**: documento de veredicto con la evidencia que lo sostiene.
- **Nota**: **tiene derecho a decir que no.** Un spike que solo puede concluir que sí no es un spike.

### [ ] T-132 · Presentación bajo Wayland `[!]`
- **Qué**: el frontend de presentación con caída automática al camino existente.
- **REQ**: REQ-ALE-004 · **CA**: CA-106.4, CA-106.5, CA-106.6, CA-106.7
- **Depende de**: T-131 con veredicto favorable, y **D-1**
- **Done**: la alerta se presenta por encima de las demás ventanas en Wayland; el fallo del servicio
  cae al camino existente sin perder el evento.
- **Estado**: **bloqueada** hasta que existan D-1 y el veredicto de T-131.

### [ ] T-133 · Smoke del binario producido
- **Qué**: el pipeline ejecuta cada binario en modo simulación y comprueba que presenta y acusa una
  alerta antes de publicar.
- **REQ**: REQ-OPS-008 · **CA**: CA-107.3, CA-107.4
- **Archivos**: `.github/workflows/build.yml`
- **Depende de**: T-108
- **Done**: un binario al que le falta un recurso detiene la publicación.

### [ ] T-134 · Construcción de Linux sobre base fijada **[P]**
- **Qué**: declarar la imagen base con versión para el binario de Linux.
- **REQ**: REQ-OPS-009 · **CA**: CA-107.5, CA-107.6
- **Archivos**: `.github/workflows/build.yml`
- **Depende de**: T-111
- **Done**: la construcción declara su base; actualizar el ejecutor no altera la glibc del binario
  publicado.

---

## Fase 5 · Configuración gráfica y prioridad de redes

### [ ] T-135 · Escritor de configuración
- **Qué**: cargar con huella, validar, comparar huella, escribir por temporal y renombrado
  preservando comentarios, con respaldo. Sin interfaz todavía.
- **REQ**: REQ-CFG-009, REQ-CFG-010, REQ-CFG-011, REQ-CFG-012 · **CA**: CA-108.5, CA-108.6, CA-108.7, CA-108.8
- **Archivos**: `src/vigia_eew/config_writer.py` *(nuevo)*
- **Depende de**: **T-110**
- **Done**: guardar un campo conserva las 46 líneas de comentarios; una interrupción deja el original
  intacto y sin temporales; una edición externa produce conflicto en lugar de sobrescritura.
- **Nota**: probado sobre archivo temporal real. La atomicidad **es** una operación de sistema de
  archivos; simularla no probaría nada.

### [ ] T-136 · Panel de configuración generado desde el esquema
- **Qué**: panel con secciones plegables cubriendo los 39 campos, validación en vivo y restaurar
  valores por defecto.
- **REQ**: REQ-GUI-001, REQ-GUI-002, REQ-GUI-003, REQ-GUI-004 · **CA**: CA-108.1..108.4, CA-108.9
- **Archivos**: `src/vigia_eew/notify/config_panel.py` *(nuevo)*
- **Depende de**: T-135
- **Done**: la prueba que recorre el esquema pasa, y **falla** si se añade un campo al modelo sin
  control en el panel.

### [ ] T-137 · Integrar el panel en la bandeja
- **Qué**: la entrada de menú abre el panel, conservando la que abre el archivo.
- **REQ**: REQ-GUI-005 · **CA**: CA-108.10
- **Archivos**: `src/vigia_eew/tray.py:52`
- **Depende de**: T-136
- **Done**: el menú ofrece las dos entradas y ambas funcionan.

### [ ] T-139 · Prioridad en la especificación de fuente **[P]**
- **Qué**: campo de prioridad en `SourceSpec` y en el esquema de configuración, con valor por defecto
  para archivos que no lo traen.
- **REQ**: REQ-ING-011 · **CA**: CA-110.5, CA-110.6
- **Archivos**: `src/vigia_eew/ingest/registry.py`, `src/vigia_eew/config.py`
- **Depende de**: T-121
- **Done**: un `config.toml` de la v0.6.0 carga sin error y sus fuentes quedan ordenadas al final.

### [ ] T-140 · El deduplicador resuelve por prioridad
- **Qué**: al unir dos llegadas, prevalecen los datos de la fuente de mayor prioridad; la distancia
  se recalcula con la ubicación que prevalece.
- **REQ**: REQ-PIP-010 · **CA**: CA-110.1, 110.2, 110.3, 110.4, 110.7
- **Archivos**: `src/vigia_eew/pipeline/dedup.py`
- **Depende de**: T-139, T-124
- **Done**: **invertir el orden de dos redes invierte la magnitud presentada** para un sismo que
  llegó por ambas; un sismo reportado solo por la red de menor prioridad sigue alertando.
- **Nota**: la prioridad **no decide si se alerta** — eso sigue siendo del filtro. CA-110.4 es el
  criterio que lo protege.

### [ ] T-141 · Lista de redes en el panel
- **Qué**: las cuatro fuentes como lista con casilla de habilitación y reordenación.
- **REQ**: REQ-GUI-008 · **CA**: CA-110.8
- **Archivos**: `src/vigia_eew/notify/config_panel.py`
- **Depende de**: T-136, T-139
- **Done**: reordenar y guardar produce un archivo cuyo orden coincide con el de la interfaz.

---

## Fase 6 · Histórico persistente

### [ ] T-142 · Esquema y almacén del histórico
- **Qué**: tabla `events` con sus cinco índices, versión en `PRAGMA user_version` y migración
  aplicada en transacción al abrir.
- **REQ**: REQ-HIS-003 · **CA**: CA-111.6
- **Archivos**: `src/vigia_eew/history.py` *(nuevo)*
- **Depende de**: **T-110** (la enmienda E-05 debe estar publicada)
- **Done**: un archivo de la versión de esquema anterior se abre, migra y conserva todas sus filas;
  un archivo de versión posterior no se toca y se explica.
- **Nota**: probado sobre archivo SQLite real. Las migraciones fallan en los detalles del motor, no
  en la lógica.

### [ ] T-143 · Registro de veredictos desde el pipeline
- **Qué**: cada evento evaluado se registra con su veredicto y, si fue descartado, su motivo; los
  duplicados quedan enlazados con la fila que prevaleció.
- **REQ**: REQ-HIS-001, REQ-HIS-002, REQ-HIS-006 · **CA**: CA-111.1, 111.2, 111.3, 111.4, 111.5, 111.9
- **Archivos**: `src/vigia_eew/pipeline/processor.py`, `src/vigia_eew/history.py`
- **Depende de**: T-142, T-124
- **Done**: con el archivo del histórico **en solo lectura, la alerta se presenta igual** y el fallo
  queda anotado; el registro no forma parte del camino entre llegada y presentación.
- **Nota**: es el criterio que protege el Art. 1. Si esta tarea puede hacer fallar una alerta, está
  mal hecha.

### [ ] T-144 · Retención y poda **[P]**
- **Qué**: retención configurable con valor por defecto declarado, y poda de lo anterior.
- **REQ**: REQ-HIS-004 · **CA**: CA-111.7
- **Archivos**: `src/vigia_eew/history.py`, `src/vigia_eew/config.py`
- **Depende de**: T-142
- **Done**: con retención de un día, las entradas anteriores desaparecen y las posteriores
  permanecen.
- **Nota**: el volumen estimado —decenas de miles de filas al año— es **una estimación, no una
  medición**. Medir en el primer uso real y ajustar el valor por defecto con el dato.

---

## Fase 7 · Listado y mapa del histórico

### [ ] T-145 · Consulta del histórico
- **Qué**: filtros por rango de fechas, magnitud, distancia, veredicto y red, con orden y paginación.
- **REQ**: REQ-HIS-005 · **CA**: CA-111.8
- **Archivos**: `src/vigia_eew/history.py`
- **Depende de**: T-143
- **Done**: una consulta por magnitud mínima y rango de fechas devuelve exactamente las entradas que
  cumplen ambos criterios.

### [ ] T-146 · Vista de listado
- **Qué**: tabla con los sismos del histórico, ordenable y filtrable, con el motivo de descarte
  visible.
- **REQ**: REQ-HIS-005 · **CA**: CA-111.8
- **Archivos**: `src/vigia_eew/notify/history_view.py` *(nuevo)*
- **Depende de**: T-145
- **Done**: un sismo descartado aparece con su motivo; la vista responde sin conectividad.
- **Nota**: **esta tarea entrega el valor completo del histórico.** El mapa añade lectura geográfica
  encima; si hubiera que recortar alcance, se recorta el mapa, no esto.

### [ ] T-147 · Cliente de teselas con caché
- **Qué**: descarga bajo demanda desde OpenStreetMap, caché en el directorio de caché por plataforma
  con desalojo, cliente identificado y proveedor inyectable.
- **REQ**: REQ-MAP-001, REQ-MAP-005 · **CA**: CA-112.1, 112.3, 112.8
- **Archivos**: `src/vigia_eew/tiles.py` *(nuevo)*
- **Depende de**: T-133 *(el smoke del binario debe existir antes de meter Pillow↔Tk en el empaquetado)*
- **Done**: **con el mapa cerrado no hay una sola petición** al proveedor; una zona ya visitada no se
  vuelve a solicitar; las pruebas corren sin red con el proveedor simulado.

### [ ] T-148 · Mapa sobre lienzo Tk
- **Qué**: composición de teselas, símbolos escalados por magnitud, distinción entre alertados y
  descartados, leyenda y **atribución visible**.
- **REQ**: REQ-MAP-002, REQ-MAP-003, REQ-MAP-005 · **CA**: CA-112.2, 112.4, 112.5, 112.7
- **Archivos**: `src/vigia_eew/notify/history_map.py` *(nuevo)*
- **Depende de**: T-146, T-147
- **Done**: sin red y sin caché el mapa se declara no disponible **y el listado sigue funcionando**;
  la atribución "© OpenStreetMap contributors" es visible.

### [ ] T-149 · Filtros compartidos entre listado y mapa
- **Qué**: un solo conjunto de filtros que gobierna las dos vistas.
- **REQ**: REQ-MAP-004 · **CA**: CA-112.6
- **Depende de**: T-148
- **Done**: filtrar por magnitud mínima reduce filas y símbolos al mismo conjunto.

---

## Fase 8 · Corte de la v1.0.0

### [ ] T-138 · Publicar la v1.0.0
- **Qué**: changelog, etiqueta, release.
- **REQ**: — · **Depende de**: la lista de corte de
  [06-IMPLEMENTATION-PLAN §5](06-IMPLEMENTATION-PLAN.md)
- **Done**: las 10 condiciones de corte marcadas; los tres binarios publicados y verificados por
  T-133.
- **Nota**: conserva el número T-138 por continuidad con las referencias ya escritas, aunque se
  ejecute la última. **El orden lo da la fase, no el número.**

---

## Matriz de trazabilidad

Todo requisito en alcance tiene al menos una tarea. Toda tarea cita al menos un requisito.

| Requisito | Tareas | Criterios que lo verifican |
|---|---|---|
| REQ-DEP-001 | T-101 | CA-101.1, CA-101.2 |
| REQ-DEP-002 | T-115 | CA-101.3 |
| REQ-DEP-003 | T-116 | CA-101.3 |
| REQ-DEP-004 | T-111 | CA-101.5 |
| REQ-DEP-005 | T-117 | CA-101.7 |
| REQ-DEP-006 | T-118 | CA-101.4 |
| REQ-DEP-007 | T-112 | CA-101.6 |
| REQ-DEP-008 | T-109 | CA-101.8 |
| REQ-OBS-002 | T-123, T-124 | CA-105.1..105.5 |
| REQ-OBS-003 | T-107 | CA-102.1, CA-102.2 |
| REQ-OBS-004 | T-104 | CA-102.5 |
| REQ-OBS-005 | T-102 | CA-103.4, CA-103.5 |
| REQ-OBS-006 | T-105, T-106 | CA-102.3, CA-102.4 |
| REQ-OBS-007 | T-120, T-126, T-127 | CA-102.6, CA-102.7 |
| REQ-OBS-008 | T-128, T-129 | CA-103.7 |
| REQ-OPS-002 | T-103, T-119 | CA-103.1, 103.2, 103.3 |
| REQ-OPS-003 | T-125 | CA-103.6 |
| REQ-OPS-007 | T-108 | CA-107.1, CA-107.2 |
| REQ-OPS-008 | T-133 | CA-107.3, CA-107.4 |
| REQ-OPS-009 | T-134 | CA-107.5, CA-107.6 |
| REQ-ING-009 | T-121, T-122 | CA-104.1..104.6 |
| REQ-ALE-003 | T-130 | CA-106.1, 106.2, 106.3 |
| REQ-ALE-004 | T-131, T-132 | CA-106.4..106.7 |
| REQ-CFG-009, REQ-CFG-010, REQ-CFG-011, REQ-CFG-012 | T-135 | CA-108.5..108.8 |
| REQ-GUI-001, REQ-GUI-002, REQ-GUI-003, REQ-GUI-004 | T-136 | CA-108.1..108.4, CA-108.9 |
| REQ-GUI-005 | T-137 | CA-108.10 |
| REQ-DEV-001, REQ-DEV-002, REQ-DEV-003 | T-113 | CA-109.1..109.4 |
| REQ-DEV-004 | T-114 | CA-109.5 |
| REQ-ING-011 | T-139 | CA-110.5, CA-110.6 |
| REQ-PIP-010 | T-140 | CA-110.1, 110.2, 110.3, 110.4, 110.7 |
| REQ-GUI-008 | T-141 | CA-110.8 |
| REQ-HIS-001 | T-143 | CA-111.1, 111.2, 111.3 |
| REQ-HIS-002 | T-143 | CA-111.4, CA-111.5 |
| REQ-HIS-003 | T-142 | CA-111.6 |
| REQ-HIS-004 | T-144 | CA-111.7 |
| REQ-HIS-005 | T-145, T-146 | CA-111.8 |
| REQ-HIS-006 | T-143 | CA-111.9 |
| REQ-MAP-001 | T-147 | CA-112.1, CA-112.3 |
| REQ-MAP-002 | T-148 | CA-112.2 |
| REQ-MAP-003 | T-148 | CA-112.4, CA-112.5 |
| REQ-MAP-004 | T-149 | CA-112.6 |
| REQ-MAP-005 | T-147, T-148 | CA-112.7, CA-112.8 |

**Diferidos sin tarea, declarados explícitamente:** REQ-GUI-006 (B-37) y REQ-GUI-007 (B-38), los dos
`[SHOULD]` que quedan fuera del corte de la v1.0.

**Tareas sin requisito: dos, ambas justificadas.** T-110 es documentación que habilita una fase, y
T-138 es el corte del release.

---

## Registro de ejecución

| Fecha | Tareas | Resultado | Notas |
|---|---|---|---|
| — | — | — | Sin ejecutar. Base: `c3a2c29` |

**Si al implementar se descubre que la especificación estaba mal: parar, actualizar la
especificación —o abrir una propuesta de cambio en [`docs/sdd/changes/`](../sdd/changes/README.md)—
y solo entonces seguir.** Nunca dejar que el código y la especificación diverjan en silencio; es lo
que el Art. 9 pide y lo que T-128 convierte en un lint.
