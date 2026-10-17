# ADR-021: `config.py` como fuente única de verdad del esquema de configuración

> **Estado**: propuesto · **Fecha**: 2026-08-16 · **Debilidad que ataca**: DEB-03
> **Numeración**: continúa la serie de `docs/TECHNICAL-DESIGN.md`, que llega hasta ADR-018.

## Contexto

Cada clave de configuración vive hoy en hasta **seis artefactos**: el modelo pydantic
`config.py`, la plantilla `config.toml.example` que se siembra en el primer arranque, y
descrita en `PRD.md`, `TECHNICAL-DESIGN.md`, `DATA-MODEL.md`, `IMPLEMENTATION-PLAN.md` y/o
`README.md`. Verificado clave por clave: `today_only`, `timezone` y `country_filter`
aparecen en seis sitios cada una.

El historial lo confirma: `[METRIC: arch_signals → config.toml.example ↔
IMPLEMENTATION-PLAN.md 3 co-cambios (confianza 0.6); ↔ PRD.md 3 (0.6); ↔
TECHNICAL-DESIGN.md 3 (0.6)]`, y `config.py` es el hotspot de código #3
`[METRIC: 10 toques, churn 505]`.

La divergencia ya empezó, en silencio: `radius_km` y `min_magnitude` **no** están en
`PRD.md` aunque sí en `DATA-MODEL.md` y `README.md`; `language` no está en
`TECHNICAL-DESIGN.md`. Nadie lo ha notado porque nada lo verifica.

Restricción de contexto: este es un proyecto **spec-driven**. Los documentos no son
adorno — son el artefacto primario del método. Cualquier propuesta que diga "borra la
documentación" está atacando el valor del proyecto, no el problema.

## Decisión

Hacer de `config.py` la fuente única de verdad **del esquema** (claves, tipos, defaults,
validaciones) y derivar de ahí lo mecánico, dejando que los documentos conserven lo que
solo ellos aportan: el *porqué*.

1. **Generar `config.toml.example` desde el modelo pydantic**, con un script en
   `packaging/` que emita cada clave con su default y su docstring como comentario. El
   patrón ya existe en el repo: `packaging/build_countries_geojson.py` genera un asset
   embebido igual `[VERIFY: packaging/build_countries_geojson.py:1]`.
2. **Verificar en CI que la plantilla está sincronizada**: regenerar y comparar; si difiere,
   el build falla. Es el mismo patrón que `makemigrations --check`.
3. **Sustituir las tablas de claves de los documentos por una tabla generada e incluida**,
   o por un enlace a la plantilla. Los documentos conservan las decisiones —por qué
   `today_only` viene en `true` y `country_filter` en `false`, por qué el día es local y no
   UTC—, que es exactamente lo que un generador no puede producir.

## Alternativas consideradas

### Alternativa A: generar la plantilla y verificarla en CI (la propuesta)

- **Ventajas**: elimina la divergencia posible entre código y plantilla, que es la pareja
  que de verdad hace daño (un usuario con una plantilla desfasada configura algo que el
  modelo ignora). Deja la documentación para lo que la documentación hace bien. Barato y
  encaja con hábitos ya presentes.
- **Desventajas**: la plantilla actual tiene comentarios excelentes escritos a mano —
  explican, por ejemplo, por qué FUNVISIS va por HTTP plano
  `[VERIFY: src/vigia_eew/config.toml.example:59]`. Un generador ingenuo los perdería, así
  que las docstrings de los campos deben absorber ese contenido primero. **Ese es el
  trabajo real de este ADR**, no el script.
- **Costo**: ~1 día, la mayor parte en migrar los comentarios a docstrings sin perder matiz.

### Alternativa B: solo un test de paridad, sin generar nada

Un test que compare las claves de `Settings` con las de `config.toml.example` y falle si
divergen; los documentos se quedan como están.

- **Ventajas**: mucho más barato, cero riesgo de perder los comentarios artesanales, y
  ataca directamente la pareja peligrosa (código ↔ plantilla). Encaja con la cultura de
  tests del repo.
- **Desventajas**: detecta la divergencia pero no la evita — hay que arreglarla a mano cada
  vez. Y no toca la duplicación en los cuatro documentos.
- **Costo**: ~2 horas.

### Alternativa C: no hacer nada

- **Qué cuesta convivir con el problema**: el autor ha mantenido seis artefactos
  sincronizados durante 15 releases y las divergencias detectadas son **menores**: claves
  ausentes de algún documento, ninguna contradicción de comportamiento. No hay un solo bug
  reportado por esto. Con un autor y un ritmo de una release por semana, es sostenible.
- **Cuándo sería razonable elegirla**: si la configuración se estabiliza. La mayor parte de
  las claves llegaron entre las eras 3 y 5 (`country_filter`, `today_only`, fuentes nuevas);
  si el producto ya tiene las fuentes y filtros que quería, la presión desaparece. **Si se
  elige C, adoptar la Alternativa B**: dos horas para que una divergencia real no llegue
  nunca al usuario es una compra evidente.

## Consecuencias

- **Positivas**: el costo de añadir una clave baja de seis sitios a dos (el modelo y, si
  merece explicación, un documento). `[METRIC]` verificable: los pares de co-cambio
  `config.toml.example ↔ docs/*` deberían caer a 0 en la siguiente ejecución de
  `arch_signals.py` tras unas cuantas releases.
- **Negativas**: una plantilla generada es menos expresiva que una escrita a mano, salvo
  que se invierta el esfuerzo en las docstrings. Se añade un paso de generación al proceso
  de release, que es un sitio más donde algo puede fallar.
- **Neutrales**: `config.toml.example` pasa de artefacto editado a artefacto generado; hay
  que decirlo en su cabecera para que nadie lo edite a mano.

## Reversibilidad

**Reversible con una asimetría**: quitar el generador y volver a editar la plantilla a mano
es trivial. Lo que no se recupera solo es la calidad de los comentarios si se degradaron al
migrarlos a docstrings — por eso ese paso debe hacerse con revisión, no automáticamente.

## Guardas anti-sobreingeniería

- [x] **No introduce una capa/abstracción**: un script de generación, del mismo tipo que el
      que ya genera `countries.geojson`.
- [x] **No extrae servicios**.
- [x] **Existe una versión más aburrida y se explicó**: la Alternativa B (test de paridad,
      2 horas). Es la que recomiendo si hay que elegir una sola cosa de este ADR — cubre el
      riesgo que llega al usuario y deja intacta la plantilla artesanal.
- [x] **Declara qué NO se toca**: el modelo `Settings` no cambia de forma; `load_config`
      sigue siendo puro; los ADRs y las secciones de *decisión* de los documentos se quedan
      donde están — solo se derivan las **tablas de claves**, nunca el razonamiento.
